"""
槽位归一与必填校验（规格 §11.2、§11.5；T-031）。

将 LLM `entities` 与可选 `slots` 收敛到全局槽位命名空间，并计算 `missing_slots`、
按缺口裁剪意图后再展开 task_stack。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from .state import AgentState
from .state_accessors import get_runtime_bundle

# §11.5 OR 组未满足时的代表缺失码（用于 missing_slots 与裁剪映射）
MISSING_RECIPE_SEARCH_ANCHOR = "recipe_search_anchor"
MISSING_SHOPPING_LIST_CONTEXT = "shopping_list_context"
MISSING_RECIPE_ADOPTION_CONTEXT = "recipe_adoption_context"

_MISSING_TO_BLOCKED_INTENTS: Dict[str, Set[str]] = {
    MISSING_RECIPE_SEARCH_ANCHOR: {"recipe_search"},
    "recipe_name_for_commit": {"inventory_commit"},
    "profile_fragments": {"profile_sync"},
    "restock_items": {"inventory_add"},
    MISSING_SHOPPING_LIST_CONTEXT: {"shopping_list"},
    MISSING_RECIPE_ADOPTION_CONTEXT: {"recipe_adopt"},
}


def _split_amount_unit(raw: str) -> Tuple[Any, str]:
    s = str(raw).strip()
    m = re.match(r"^([\d.]+)\s*([a-zA-Z\u4e00-\u9fff%盒袋瓶根个勺杯碗份]+)$", s)
    if m:
        try:
            return float(m.group(1)), m.group(2)
        except ValueError:
            return None, m.group(2)
    m2 = re.match(r"^([\d.]+)$", s)
    if m2:
        try:
            return float(m2.group(1)), ""
        except ValueError:
            return None, ""
    return None, s


def merge_slots(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if v is None and k in out:
            continue
        out[k] = v
    return out


def normalize_legacy_entities_to_slots(
    entities: Dict[str, Any], intents: List[str]
) -> Dict[str, Any]:
    """把历史 entities 形状收敛到 §11.2 键空间。"""
    slots: Dict[str, Any] = {}
    if not entities:
        return slots

    _copy_keys = (
        "recipe_query",
        "recipe_name",
        "ingredients",
        "diet_topic",
        "profile_explicit",
        "recipe_adoption",
        "deduct_confirm",
        "list_action",
        "list_edit_ops",
        "mark_bought_items",
        "inventory_query_targets",
        "restock_items",
        "restock_confirm",
        "recipe_name_for_commit",
        "profile_fragments",
    )
    for key in _copy_keys:
        if key in entities and entities[key] is not None:
            slots[key] = entities[key]

    ingredients = entities.get("ingredients")
    if isinstance(ingredients, str):
        ingredients = [ingredients]
    if ingredients is None:
        ingredients = []
    if ingredients:
        slots.setdefault("ingredients", list(ingredients))

    amounts = entities.get("amounts") or {}
    if amounts and not slots.get("restock_items"):
        rows = []
        for name, raw in amounts.items():
            amt, unit = _split_amount_unit(str(raw))
            rows.append({"name": name, "amount": amt, "unit": unit or ""})
        slots["restock_items"] = rows

    if entities.get("check_inventory"):
        if not slots.get("inventory_query_targets"):
            slots["inventory_query_targets"] = (
                list(slots.get("ingredients") or ingredients) or None
            )

    prefs = entities.get("preferences")
    if prefs is not None:
        fragments = list(slots.get("profile_fragments") or [])
        if isinstance(prefs, list):
            fragments.extend(str(p) for p in prefs)
        else:
            fragments.append(str(prefs))
        slots["profile_fragments"] = fragments

    rn = entities.get("recipe_name")
    if rn and not slots.get("recipe_name"):
        slots["recipe_name"] = rn

    if "inventory_commit" in intents:
        slots.setdefault("recipe_name_for_commit", slots.get("recipe_name") or rn)

    if entities.get("recipe_adoption") is True:
        slots["recipe_adoption"] = True

    return slots


def compute_missing_slots(
    intents: List[str], slots: Dict[str, Any], state: AgentState
) -> List[str]:
    """§11.5 最小必填集合；返回稳定排序后的缺失码列表。"""
    missing: Set[str] = set()
    lb = get_runtime_bundle(state)

    ing = slots.get("ingredients") or []
    if isinstance(ing, str):
        ing = [ing]

    for intent in intents:
        if intent == "recipe_search":
            if not (
                slots.get("recipe_query")
                or slots.get("recipe_name")
                or (isinstance(ing, list) and len(ing) > 0)
            ):
                missing.add(MISSING_RECIPE_SEARCH_ANCHOR)

        elif intent == "recipe_adopt":
            if not (
                lb.get("selected_recipe_id")
                or lb.get("recipe_candidates")
                or slots.get("recipe_name")
            ):
                missing.add(MISSING_RECIPE_ADOPTION_CONTEXT)

        elif intent == "inventory_add":
            rows = slots.get("restock_items") or []
            if not isinstance(rows, list) or len(rows) == 0:
                missing.add("restock_items")

        elif intent == "inventory_commit":
            # §6.3：会话已锁定菜名时，允许不显式报 recipe_name_for_commit
            has_locked_title = bool(
                lb.get("recipe_title_locked") or lb.get("selected_recipe_title")
            )
            if not has_locked_title and not (
                slots.get("recipe_name_for_commit") or slots.get("recipe_name")
            ):
                missing.add("recipe_name_for_commit")

        elif intent == "shopping_list":
            has_r = bool(lb.get("recipe_requirements")) or bool(
                lb.get("selected_recipe_id")
            )
            same_turn_search = "recipe_search" in intents
            has_anchor = bool(
                slots.get("recipe_name")
                or slots.get("recipe_query")
                or (isinstance(ing, list) and len(ing) > 0)
            )
            if not has_r and not (same_turn_search and has_anchor):
                missing.add(MISSING_SHOPPING_LIST_CONTEXT)

        elif intent == "profile_sync":
            frags = slots.get("profile_fragments") or []
            if not frags:
                missing.add("profile_fragments")

    return sorted(missing)


def intents_blocked_by_missing(missing: List[str]) -> Set[str]:
    blocked: Set[str] = set()
    for m in missing:
        b = _MISSING_TO_BLOCKED_INTENTS.get(m)
        if b:
            blocked |= b
    return blocked


def expand_task_stack_for_intents(
    intents: List[str], intent_task_mapping: Dict[str, List[str]]
) -> List[str]:
    final_tasks: List[str] = []
    for intent in intents:
        for t in intent_task_mapping.get(intent, ["TASK_DIRECT_REPLY"]):
            if t not in final_tasks:
                final_tasks.append(t)
    return final_tasks


def apply_slot_guards_to_task_stack(
    intents_ordered: List[str],
    intent_task_mapping: Dict[str, List[str]],
    missing_slots: List[str],
) -> List[str]:
    """去掉缺口绑定的意图对应的任务；若有缺失则在队首插入 TASK_CLARIFY。"""
    blocked = intents_blocked_by_missing(missing_slots)
    filtered = [i for i in intents_ordered if i not in blocked]
    tasks = expand_task_stack_for_intents(filtered, intent_task_mapping)
    if missing_slots:
        if "TASK_CLARIFY" not in tasks:
            tasks.insert(0, "TASK_CLARIFY")
    if not tasks:
        tasks = ["TASK_CLARIFY"] if missing_slots else ["TASK_DIRECT_REPLY"]
    return tasks
