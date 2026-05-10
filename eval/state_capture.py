"""
T-041：从 LangGraph 终态组装可 JSON 序列化的原始采集（开发计划 §5.0 步骤 2）。

§5.1～5.4 的指标计算在 T-042；此处仅保留证据字段，便于 runner 落盘与后续对比。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional


def _message_to_dict(m: Any) -> Dict[str, Any]:
    if m is None:
        return {}
    t = getattr(m, "type", None) or getattr(m, "_type", None) or type(m).__name__
    content = getattr(m, "content", None)
    if content is None:
        content = str(m)
    out: Dict[str, Any] = {"type": str(t), "content": content}
    # token 用量：若适配器写入 response_metadata，则一并采集（§5.4）
    rm = getattr(m, "response_metadata", None) or {}
    if isinstance(rm, dict) and rm:
        out["response_metadata"] = rm
    return out


def serialize_messages(messages: Optional[List[Any]], max_tail: int = 30) -> List[Dict[str, Any]]:
    if not messages:
        return []
    tail = messages[-max_tail:] if len(messages) > max_tail else messages
    return [_message_to_dict(m) for m in tail]


def _infer_mcp_calls(bundle: Mapping[str, Any], expert: Mapping[str, Any]) -> Dict[str, Any]:
    """图中未显式计数 MCP 时，由终态反推最小调用集合（§5.4 工具次数粗算；软重试次数见日志 T-042）。"""
    calls: List[str] = []
    if expert.get("search_results") is not None or bundle.get("recipe_candidates"):
        calls.append("search_recipes")
    if expert.get("recipe_detail") or bundle.get("recipe_requirements"):
        calls.append("get_recipe_source")
        calls.append("parse_recipe_content")
    seen: set[str] = set()
    deduped: List[str] = []
    for c in calls:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return {"inferred_sequence": deduped, "inferred_total": len(deduped)}


def build_e2e_snapshot(state: Mapping[str, Any]) -> Dict[str, Any]:
    """从单轮 invoke 后的完整 state.values 构建快照。"""
    from src.agent.core.state_accessors import get_runtime_bundle

    bundle = get_runtime_bundle(state)
    ctrl = dict(state.get("control_state") or {})
    rs = dict(state.get("recipe_state") or {})
    inv = dict(state.get("inventory_state") or {})
    err = dict(state.get("error_state") or {}) if isinstance(state.get("error_state"), dict) else {}
    mem = dict(state.get("memory_state") or {})
    resp = dict(state.get("response_state") or {})
    expert = dict(state.get("expert_payloads") or {})

    reply = state.get("final_response") or resp.get("final_response")
    if not reply:
        msgs = state.get("messages") or []
        for m in reversed(msgs):
            t = getattr(m, "type", None)
            if t == "ai":
                reply = getattr(m, "content", "") or ""
                break

    snap: Dict[str, Any] = {
        "final_response": reply,
        "task_stack": list(state.get("task_stack") or []),
        "current_task": state.get("current_task"),
        "primary_intent": state.get("primary_intent") or ctrl.get("primary_intent"),
        "intents": list(state.get("intents") or ctrl.get("intents") or []),
        "confidence": state.get("confidence", ctrl.get("confidence")),
        "needs_clarification": state.get("needs_clarification", ctrl.get("needs_clarification")),
        "slots": dict(state.get("slots") or ctrl.get("slots") or {}),
        "missing_slots": list(state.get("missing_slots") or ctrl.get("missing_slots") or []),
        "control_state": ctrl,
        "recipe_state": rs,
        "runtime_bundle": dict(bundle),
        "inventory_state_excerpt": {
            "inventory_snapshot_keys": list((inv.get("inventory_snapshot") or {}).keys())[:80],
            "cached_shopping_gap_present": inv.get("cached_shopping_gap") is not None,
            "gap_basis": inv.get("gap_basis"),
            "recipe_use_confirmed": inv.get("recipe_use_confirmed"),
        },
        "memory_state_excerpt": {
            "short_term_constraints": list(mem.get("short_term_constraints") or [])[:20],
            "conversation_summary_len": len(str(mem.get("conversation_summary") or "")),
        },
        "error_state": err,
        "expert_payloads": copy.deepcopy(expert),
        "research_results_legacy": state.get("research_results"),
        "messages_tail": serialize_messages(state.get("messages")),
        "mcp_evidence": _infer_mcp_calls(bundle, expert),
    }
    return snap


def extract_assistant_reply(state: Mapping[str, Any]) -> str:
    r = state.get("final_response")
    if isinstance(r, str) and r.strip():
        return r
    for m in reversed(state.get("messages") or []):
        if getattr(m, "type", None) == "ai":
            c = getattr(m, "content", None)
            return str(c) if c is not None else ""
    return ""
