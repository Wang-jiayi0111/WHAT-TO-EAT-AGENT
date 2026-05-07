"""
方案 A 状态兼容层（规格 §1.2.0～1.2.1，T-030）。

阶段 3：`logistics_buffer` 已移除；运行时视图由 **切片** 经 `materialize_runtime_bundle_from_slices`
组装；遗留 checkpoint 若仅有 buffer，由 `get_runtime_bundle`（见 `state_accessors`）合并。
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

# 成功路径合并入 error_state，清空上一轮 fault（merge_slice 无法用「缺键」删除字段）
CLEAR_ERROR_STATE: Dict[str, Any] = {
    "error_code": None,
    "recoverable": True,
    "error_detail": None,
}


def _normalize_inventory_snapshot(raw: Any) -> Dict[str, Dict[str, Any]]:
    """§1.2.1：inventory_snapshot 最终形态为 Dict[name, {amount: float, unit: str}]。"""
    if isinstance(raw, dict):
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in raw.items():
            name = str(k).strip()
            if not name or not isinstance(v, dict):
                continue
            try:
                amt = float(v.get("amount", 0))
            except (TypeError, ValueError):
                amt = 0.0
            out[name] = {"amount": amt, "unit": str(v.get("unit") or "")}
        return out
    if isinstance(raw, list):
        out: Dict[str, Dict[str, Any]] = {}
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = (row.get("name") or "").strip()
            if not name:
                continue
            try:
                amt = float(row.get("amount") or 0)
            except (TypeError, ValueError):
                amt = 0.0
            out[name] = {"amount": amt, "unit": str(row.get("unit") or "")}
        return out
    return {}


def _normalize_recipe_candidates(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not raw:
        return out
    for item in raw:
        if isinstance(item, str):
            t = item.strip()
            if t:
                out.append({"title": t})
        elif isinstance(item, dict):
            out.append(dict(item))
        else:
            s = str(item).strip()
            if s:
                out.append({"title": s})
    return out


def _recipe_steps_from_buffer(lb: Dict[str, Any]) -> List[str]:
    steps = lb.get("recipe_cook_step")
    if steps is None:
        return []
    if isinstance(steps, list):
        return [str(s) for s in steps]
    return [str(steps)]


def recipe_state_from_logistics_buffer(lb: Dict[str, Any]) -> Dict[str, Any]:
    """由展平运行时 bundle（旧 buffer 形状）推导菜谱切片。"""
    sid = lb.get("selected_recipe_id")
    return {
        "recipe_file_ref": sid,
        "recipe_candidates": _normalize_recipe_candidates(lb.get("recipe_candidates")),
        "selected_recipe_title": lb.get("selected_recipe_title"),
        "selected_recipe_id": sid,
        "recipe_requirements": list(lb.get("recipe_requirements") or []),
        "recipe_steps": _recipe_steps_from_buffer(lb),
        "recipe_title_locked": lb.get("recipe_title_locked")
        or lb.get("selected_recipe_title"),
        "recipe_parser_version": lb.get("recipe_parser_version"),
    }


def inventory_state_from_logistics_buffer(lb: Dict[str, Any]) -> Dict[str, Any]:
    """库存 + 缺口缓存 + 清单编辑层（§1.2.1）；含 logistics 节点写入的展平键。"""
    inv: Dict[str, Any] = {
        "inventory_snapshot": _normalize_inventory_snapshot(
            lb.get("inventory_snapshot")
        ),
        "cached_shopping_gap": lb.get("cached_shopping_gap"),
        "gap_basis": lb.get("gap_basis"),
        "shopping_list_overlay": lb.get("shopping_list_overlay") or [],
        "recipe_use_confirmed": bool(lb.get("recipe_use_confirmed", False)),
        "commit_preview": lb.get("commit_preview"),
        "commit_status": lb.get("commit_status"),
        "add_preview": lb.get("add_preview"),
        "add_status": lb.get("add_status"),
    }
    if "gap_delivery_mode" in lb:
        inv["gap_delivery_mode"] = lb["gap_delivery_mode"]
    for k in (
        "shopping_list",
        "sufficient_items",
        "missing_items",
        "ingredient_gaps",
        "action_metadata",
        "added_items",
        "commit_failed_items",
        "commit_succeeded_items",
        "add_failed_items",
        "add_succeeded_items",
        "gap_delivery_mode",
    ):
        if k in lb:
            inv[k] = lb[k]
    return inv


def control_state_from_logistics_buffer(lb: Dict[str, Any]) -> Dict[str, Any]:
    """路由/降级/待办等进入 control_state 的展平域。"""
    out: Dict[str, Any] = {}
    if "extracted_entities" in lb:
        out["extracted_entities"] = lb["extracted_entities"]
    if "router_reasoning" in lb:
        out["router_reasoning"] = lb["router_reasoning"]
    if "pending_tasks" in lb:
        out["pending_tasks"] = list(lb["pending_tasks"])
    if "degraded_reply" in lb:
        out["degraded_reply"] = lb["degraded_reply"]
    if "clarification_kind" in lb:
        out["clarification_kind"] = lb["clarification_kind"]
    if "clarify_error" in lb:
        out["clarify_error"] = lb["clarify_error"]
    return out


def memory_patch_from_logistics_buffer(lb: Dict[str, Any]) -> Dict[str, Any]:
    """buffer 内短期约束并入 memory_state。"""
    st = lb.get("short_term_constraints")
    if not st:
        return {}
    return {"short_term_constraints": list(st)}


def error_state_from_expert_payloads(payloads: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """仅在确有 fault 载荷时填充（歧义 / 成功分支不产生 error_state 条目）。"""
    pl = payloads or {}
    err = pl.get("error")
    if err is None:
        return {}
    recoverable = pl.get("status") != "fatal_error"
    code = pl.get("error_code")
    if code is None:
        code = pl.get("status") or "unknown"
    return {
        "error_code": str(code),
        "recoverable": recoverable,
        "error_detail": str(err),
    }


def _recipe_candidates_to_legacy_shape(raw: Any) -> List[Any]:
    """recipe_state 候选 → clarify/researcher 使用的列表（多为 title 字符串或原始 dict）。"""
    if not raw:
        return []
    out: List[Any] = []
    for item in raw:
        if isinstance(item, dict):
            t = (item.get("title") or item.get("name") or "").strip()
            if t:
                out.append(t)
            else:
                out.append(dict(item))
        else:
            s = str(item).strip()
            if s:
                out.append(s)
    return out


def materialize_runtime_bundle_from_slices(state: Mapping[str, Any]) -> Dict[str, Any]:
    """由当前图中的切片组装「展平运行时 bundle」（语义等价于旧 logistics_buffer）。"""
    rs = dict(state.get("recipe_state") or {})
    inv = dict(state.get("inventory_state") or {})
    ctrl = dict(state.get("control_state") or {})
    mem = dict(state.get("memory_state") or {})
    err_slice = state.get("error_state")

    flat: Dict[str, Any] = {}
    if "extracted_entities" in ctrl:
        flat["extracted_entities"] = dict(ctrl["extracted_entities"])
    if ctrl.get("router_reasoning") is not None:
        flat["router_reasoning"] = str(ctrl.get("router_reasoning") or "")
    if ctrl.get("pending_tasks") is not None:
        flat["pending_tasks"] = list(ctrl.get("pending_tasks") or [])
    if "degraded_reply" in ctrl:
        flat["degraded_reply"] = ctrl["degraded_reply"]
    if "clarification_kind" in ctrl:
        flat["clarification_kind"] = ctrl.get("clarification_kind")
    if "clarify_error" in ctrl:
        flat["clarify_error"] = ctrl.get("clarify_error")

    flat["recipe_candidates"] = _recipe_candidates_to_legacy_shape(rs.get("recipe_candidates"))
    sid = rs.get("selected_recipe_id") or rs.get("recipe_file_ref")
    flat["selected_recipe_id"] = sid
    flat["selected_recipe_title"] = rs.get("selected_recipe_title")
    flat["recipe_requirements"] = list(rs.get("recipe_requirements") or [])
    flat["recipe_title_locked"] = rs.get("recipe_title_locked")
    if rs.get("recipe_parser_version") is not None:
        flat["recipe_parser_version"] = rs.get("recipe_parser_version")

    steps = rs.get("recipe_steps") or []
    if isinstance(steps, list) and steps:
        flat["recipe_cook_step"] = steps
    elif steps:
        flat["recipe_cook_step"] = steps
    else:
        flat["recipe_cook_step"] = None

    flat["inventory_snapshot"] = dict(inv.get("inventory_snapshot") or {})

    for key in (
        "cached_shopping_gap",
        "gap_basis",
        "shopping_list_overlay",
        "recipe_use_confirmed",
        "commit_preview",
        "commit_status",
        "add_preview",
        "add_status",
        "shopping_list",
        "sufficient_items",
        "missing_items",
        "ingredient_gaps",
        "action_metadata",
        "added_items",
        "commit_failed_items",
        "commit_succeeded_items",
        "add_failed_items",
        "add_succeeded_items",
        "gap_delivery_mode",
    ):
        if key in inv:
            flat[key] = inv[key]

    stc = mem.get("short_term_constraints")
    if stc:
        flat["short_term_constraints"] = list(stc)
    if mem.get("effective_constraint") is not None:
        flat["effective_constraint"] = mem["effective_constraint"]

    top_slots = state.get("slots")
    if isinstance(top_slots, dict) and top_slots:
        flat["slots"] = dict(top_slots)

    # §9：供 logistics / researcher 等节点读取上一轮 fault（BUG-002：须与切片往返）
    if isinstance(err_slice, dict):
        flat["error_state"] = dict(err_slice)

    return flat


def empty_runtime_bundle() -> Dict[str, Any]:
    """新轮次清空用的最小 bundle（再经 `runtime_bundle_to_slice_patches` 写回切片）。"""
    return {
        "extracted_entities": {},
        "router_reasoning": "",
        "recipe_candidates": [],
        "selected_recipe_id": None,
        "recipe_requirements": [],
        "recipe_cook_step": None,
        "inventory_snapshot": {},
        "pending_tasks": [],
    }


def runtime_bundle_to_slice_patches(lb: Dict[str, Any]) -> Dict[str, Any]:
    """展平 bundle → 各切片更新字典（供节点一次性 `return`）。"""
    patches: Dict[str, Any] = {
        "recipe_state": recipe_state_from_logistics_buffer(lb),
        "inventory_state": inventory_state_from_logistics_buffer(lb),
        "control_state": control_state_from_logistics_buffer(lb),
    }
    mp = memory_patch_from_logistics_buffer(lb)
    if mp:
        patches["memory_state"] = mp
    # BUG-002 / §9：logistics 等在 lb 顶层写入的 error_state 必须回到 error_state 切片
    if "error_state" in lb:
        es = lb.get("error_state")
        patches["error_state"] = dict(es) if isinstance(es, dict) else {
            "error_code": None,
            "recoverable": True,
            "error_detail": None,
        }
    return patches


def slices_carry_session_payload(state: Mapping[str, Any]) -> bool:
    """
    切片是否已承载会话业务数据（用于残留 checkpoint 仍以 buffer 为准）。
    排除仅有路由镜像字段的 control_state。
    """
    rs = state.get("recipe_state") or {}
    inv = state.get("inventory_state") or {}
    ctrl = state.get("control_state") or {}
    mem = state.get("memory_state") or {}
    if rs.get("recipe_requirements") or rs.get("recipe_candidates") or rs.get(
        "selected_recipe_title"
    ):
        return True
    if inv.get("inventory_snapshot") or inv.get("cached_shopping_gap"):
        return True
    ce = ctrl.get("extracted_entities")
    if isinstance(ce, dict) and ce:
        return True
    if ctrl.get("router_reasoning"):
        return True
    if ctrl.get("degraded_reply"):
        return True
    if ctrl.get("pending_tasks"):
        return True
    if mem.get("short_term_constraints"):
        return True
    return False


def memory_state_patch_from_summary_and_constraints(
    *,
    conversation_summary: str,
    active_constraints: Optional[Dict[str, Any]],
    prior_memory_state: Optional[Dict[str, Any]],
    logistics_short_term: Optional[List[str]],
) -> Dict[str, Any]:
    """
    合并摘要与各类短期约束线索 → memory_state 补丁。

    供 L3 / 路由后合并路径使用；**禁止**在 L2 摘要节点调用（规格 §4.2：L2 不得掺写 short_term / 业务字段）。
    """
    prior = dict(prior_memory_state or {})
    stc: List[str] = list(prior.get("short_term_constraints") or [])
    if logistics_short_term:
        for x in logistics_short_term:
            if x and x not in stc:
                stc.append(x)
    if active_constraints:
        for k, v in active_constraints.items():
            line = f"{k}: {v}"
            if line not in stc:
                stc.append(line)
    patch: Dict[str, Any] = {"conversation_summary": conversation_summary}
    if stc:
        patch["short_term_constraints"] = stc
    mc = prior.get("memory_confidence")
    if mc is not None:
        patch["memory_confidence"] = mc
    return patch
