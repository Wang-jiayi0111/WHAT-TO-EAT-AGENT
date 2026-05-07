"""
L3 当轮短期约束（规格 §4.3）：从最新用户句做规则抽取，写入 memory_state.short_term_constraints；
并向检索 query 注入约束摘要（FR-17；完整 EffectiveConstraint **C** 见 T-011）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from langchain_core.messages import BaseMessage, HumanMessage

from ..libs.base.settings import Settings
from .state import AgentState
from .state_accessors import get_runtime_bundle

# 规格 §4.3 示例关键词；无配置时回退
_DEFAULT_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("肠胃", "胃不舒服", "胃疼", "胃炎", "拉肚子", "腹泻"), "短期：肠胃不适，宜清淡易消化"),
    (("感冒", "发烧", "咳嗽", "嗓子疼", "喉咙痛"), "短期：感冒/呼吸道不适"),
    (("清淡", "少油", "少盐", "低油", "低盐"), "口味：清淡饮食"),
    (("忌口", "不能吃", "不吃", "禁食"), "医嘱/自我约束：忌口需遵守"),
    (("牙疼", "拔牙", "口腔"), "短期：口腔不适期"),
    (("孕妇", "怀孕", "孕期", "月子", "产后"), "特殊阶段：孕产期饮食需谨慎"),
    (("术后", "刚做完手术", "手术恢复"), "短期：术后恢复期"),
    (("过敏", "过敏原", "不耐受"), "安全：过敏相关表述需结合画像核对"),
)


def _load_rules_from_settings() -> List[Tuple[Tuple[str, ...], str]]:
    settings = Settings()
    mem = settings.get("memory") or {}
    if not isinstance(mem, dict):
        return list(_DEFAULT_RULES)
    l3 = mem.get("l3") or {}
    if not isinstance(l3, dict):
        return list(_DEFAULT_RULES)
    raw = l3.get("keyword_rules")
    if not isinstance(raw, list) or not raw:
        return list(_DEFAULT_RULES)
    out: List[Tuple[Tuple[str, ...], str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        kws = row.get("keywords") or row.get("keys")
        label = row.get("constraint") or row.get("label")
        if not label or not isinstance(label, str):
            continue
        if isinstance(kws, str):
            keys = tuple(x.strip() for x in kws.split("|") if x.strip())
        elif isinstance(kws, list):
            keys = tuple(str(x).strip() for x in kws if str(x).strip())
        else:
            continue
        if keys:
            out.append((keys, label.strip()))
    return out if out else list(_DEFAULT_RULES)


def latest_user_text(messages: Sequence[BaseMessage]) -> str:
    """取最近一条用户（Human）文本；无则空串。"""
    for msg in reversed(list(messages or [])):
        if isinstance(msg, HumanMessage):
            c = msg.content
            return c if isinstance(c, str) else str(c)
    return ""


def extract_short_term_lines(user_text: str, *, rules: Sequence[Tuple[Tuple[str, ...], str]] | None = None) -> List[str]:
    """
    基于关键词命中抽取约束行（可配置 + 默认表）。
    命中规则：任一关键词子串出现在 user_text 中（大小写不敏感，中文按原样）。
    """
    if not user_text or not user_text.strip():
        return []
    text = user_text.strip()
    use_rules = list(rules) if rules is not None else _load_rules_from_settings()
    seen: set[str] = set()
    out: List[str] = []
    for keys, label in use_rules:
        if label in seen:
            continue
        for kw in keys:
            if not kw:
                continue
            if kw in text:
                out.append(label)
                seen.add(label)
                break
    return out


def merge_short_term_constraints(prior: Sequence[str] | None, new_lines: Sequence[str]) -> List[str]:
    """去重合并，保持先旧后新顺序。"""
    merged: List[str] = []
    seen: set[str] = set()
    for block in (prior or (), new_lines or ()):
        for line in block:
            s = (line or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            merged.append(s)
    return merged


def augment_query_for_search(base_query: str, state: Mapping[str, Any]) -> str:
    """
    将 L3（memory_state.short_term_constraints）与顶层 active_constraints 并入检索 query，
    供 MCP search_recipes 做语义增强（FR-17；规格 §3.5 完整 **C** 由 T-011 收敛）。
    """
    q = (base_query or "").strip()
    lb = get_runtime_bundle(state)
    hints: List[str] = []
    for x in lb.get("short_term_constraints") or []:
        if isinstance(x, str) and x.strip():
            hints.append(x.strip())
    ac = state.get("active_constraints") or {}
    if isinstance(ac, dict):
        for k, v in ac.items():
            if v is None:
                continue
            line = f"{k}: {v}".strip()
            if line:
                hints.append(line)
    if not hints:
        return q
    tail = "；".join(hints[:12])
    if not q:
        return f"[饮食约束] {tail}"
    return f"{q} [饮食约束] {tail}"


def build_l3_memory_patch(state: AgentState) -> Dict[str, Any]:
    """
    计算本节点应写入的 memory_state 补丁（仅 short_term_constraints / memory_confidence）。
    无新信息时返回 {}。
    """
    messages = state.get("messages") or []
    user_text = latest_user_text(messages)
    new_lines = extract_short_term_lines(user_text)
    mem = state.get("memory_state") or {}
    prior = mem.get("short_term_constraints") or []
    if not isinstance(prior, list):
        prior = []
    prior_strs = [str(x) for x in prior if str(x).strip()]
    merged = merge_short_term_constraints(prior_strs, new_lines)
    if merged == prior_strs:
        return {}
    patch: Dict[str, Any] = {"short_term_constraints": merged}
    if new_lines:
        patch["memory_confidence"] = 0.85
    return {"memory_state": patch}
