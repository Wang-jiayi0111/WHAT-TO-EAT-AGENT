"""
Logistics Manager Node for WHAT-TO-EAT-AGENT
 
职责：
  TASK_INV_CHECK   → 查询当前库存快照
  TASK_GAP_CALC    → 显式清单意图（仍依赖文末统一缺口计算写入缓存，避免重复）
  TASK_INV_COMMIT  → 用户确认烹饪后，扣减食材库存
 
  **规格 §1.3 步 5 / §7.1～§7.3**：**R** 非空时拉取 **I**；`gap_basis` 与当前 **R**/**I** 指纹一致则
  **不重算**（显式 `TASK_GAP_CALC` 与静默路径共用）；否则 §7.2 写入 `cached_shopping_gap`。
  不要求用户本轮含清单意图（FR-42）。
 
数据流：
  输入  state["logistics_buffer"]["recipe_requirements"]
        [{"name": "五花肉", "amount": 500, "unit": "g"}, ...]
  输出  runtime_bundle / ``inventory_state.inventory_snapshot``（§1.2.1 **I**）
        state["logistics_buffer"]["shopping_list"]        购物缺口（兼容字段）
        state["logistics_buffer"]["cached_shopping_gap"]  缺口缓存（§7.2）
        state["logistics_buffer"]["gap_basis"]              指纹（§7.1）
        state["logistics_buffer"]["sufficient_items"]     库存充足的食材
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from ...libs.base.inventory import InventoryManager
from ...libs.base.settings import Settings
from ...libs.utils.ingredient_normalize import normalize_name as normalize_ingredient_name
from ...libs.utils.unit_converter import UnitConverter
from ..core.state import AgentState
from ..core.state_accessors import get_runtime_bundle
from ..core.state_sync import CLEAR_ERROR_STATE, runtime_bundle_to_slice_patches

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _stable_r_fingerprint(requirements: List[Dict[str, Any]]) -> str:
    """对 R 做稳定序列化后取短 hash（§7.1 gap_basis.r_fingerprint）。"""
    rows = []
    for r in requirements:
        name = (r.get("name") or "").strip()
        try:
            amt = float(r.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        unit = (r.get("unit") or "").strip()
        rows.append((name, amt, unit))
    rows.sort()
    payload = json.dumps(rows, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _inventory_fingerprint(inv: Dict[str, Any]) -> str:
    """对 I 快照做稳定序列化后取短 hash（§7.1 gap_basis.inventory_fingerprint）。"""
    items = sorted(inv.items(), key=lambda kv: kv[0])
    payload = json.dumps(items, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _gap_cache_valid(merged_lb: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    """
    规格 §7.3：`gap_basis` 与当前 **R**、**I** 指纹一致且 `cached_shopping_gap` 可用 → 命中缓存。
    """
    req: List[Dict[str, Any]] = merged_lb.get("recipe_requirements") or []
    if not req:
        return False
    gb = merged_lb.get("gap_basis")
    if not isinstance(gb, dict):
        return False
    r_fp = gb.get("r_fingerprint")
    i_fp = gb.get("inventory_fingerprint")
    if not r_fp or not i_fp:
        return False
    if r_fp != _stable_r_fingerprint(req):
        return False
    if i_fp != _inventory_fingerprint(snapshot):
        return False
    cache = merged_lb.get("cached_shopping_gap")
    if not isinstance(cache, dict):
        return False
    if "shopping_list" not in cache:
        return False
    return True


def _row_display_key(row: Dict[str, Any]) -> str:
    return normalize_ingredient_name(str(row.get("name") or ""))


def _row_matches_remove_key(row: Dict[str, Any], key_raw: str) -> bool:
    """remove 的 key 可为规范化食材名或行 `line_id`。"""
    k = str(key_raw or "").strip()
    if not k:
        return False
    nk = normalize_ingredient_name(k)
    if row.get("line_id") is not None and str(row.get("line_id")) == k:
        return True
    return _row_display_key(row) == nk or nk in _row_display_key(row)


def _merge_shopping_gap_overlay(
    cached_gap: Dict[str, Any], overlay_raw: Any
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    规格 §7.3 / §7.4：底 = `pending_manual` + `shopping_list`，按 overlay **顺序**应用
    remove / adjust_note / add；`sufficient_items` 仍取自缓存。
    """
    rows: List[Dict[str, Any]] = []
    for pm in cached_gap.get("pending_manual") or []:
        if isinstance(pm, str) and pm.strip():
            rows.append(
                {
                    "name": pm.strip(),
                    "amount": 0.0,
                    "unit": "待确认",
                    "pending_manual": True,
                }
            )
        elif isinstance(pm, dict):
            rows.append(copy.deepcopy(pm))

    rows.extend(copy.deepcopy(list(cached_gap.get("shopping_list") or [])))
    sufficient: List[Dict[str, Any]] = copy.deepcopy(
        list(cached_gap.get("sufficient_items") or [])
    )
    if not isinstance(overlay_raw, list) or not overlay_raw:
        return rows, sufficient

    for op in overlay_raw:
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or op.get("action") or op.get("type") or "").strip().lower()
        if kind == "remove":
            key = op.get("key") or op.get("ingredient") or op.get("name") or op.get("remove")
            if key is None:
                continue
            rows = [r for r in rows if not _row_matches_remove_key(r, str(key))]
        elif kind in ("adjust_note", "note"):
            key = op.get("key") or op.get("ingredient") or op.get("name")
            note = str(op.get("note") or op.get("display_note") or "").strip()
            if not key or not note:
                continue
            nk = normalize_ingredient_name(str(key))
            for r in rows:
                if _row_display_key(r) == nk or nk in _row_display_key(r):
                    r["note"] = note
                    break
        elif kind == "add":
            disp = str(op.get("display") or op.get("text") or "").strip()
            if disp:
                rows.append(
                    {
                        "name": disp,
                        "amount": float(op.get("amount") or 0.0),
                        "unit": str(op.get("unit") or "项").strip() or "项",
                        "source": "user",
                        "line_id": op.get("line_id"),
                    }
                )

    return rows, sufficient


def _coerce_list_edit_ops(raw: Any) -> List[Dict[str, Any]]:
    """将 LLM `list_edit_ops` 多样形状收敛为 §7.4 canonical overlay 操作。"""
    out: List[Dict[str, Any]] = []
    if raw is None:
        return out
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            continue
        if not isinstance(item, dict):
            continue
        op = item.get("op") or item.get("action") or item.get("type")
        op_s = str(op or "").strip().lower()
        if op_s == "remove" or item.get("remove") is not None:
            key = item.get("key") or item.get("ingredient") or item.get("name") or item.get(
                "remove"
            )
            if key is not None and str(key).strip():
                out.append({"op": "remove", "key": str(key).strip()})
        elif op_s in ("adjust_note", "note") or item.get("note"):
            key = item.get("key") or item.get("ingredient") or item.get("name")
            note = item.get("note") or item.get("display_note")
            if key is not None and note is not None and str(note).strip():
                out.append(
                    {
                        "op": "adjust_note",
                        "key": str(key).strip(),
                        "note": str(note).strip(),
                    }
                )
        elif op_s == "add" or item.get("display"):
            disp = item.get("display") or item.get("text") or item.get("name")
            if disp is not None and str(disp).strip():
                row: Dict[str, Any] = {
                    "op": "add",
                    "display": str(disp).strip(),
                }
                if item.get("amount") is not None:
                    try:
                        row["amount"] = float(item["amount"])
                    except (TypeError, ValueError):
                        pass
                if item.get("unit"):
                    row["unit"] = str(item["unit"])
                if item.get("note"):
                    row["note"] = str(item["note"])
                out.append(row)
    return out


def _apply_list_action_to_overlay_updates(
    logistics_buffer: Dict[str, Any],
    updates: Dict[str, Any],
    slots: Dict[str, Any],
) -> None:
    """
    规格 §7.4 项 3、§12.2：`list_action` / `list_edit_ops` → 持久化 `shopping_list_overlay`；
    `refresh_gap` 清空 overlay 并失效 `gap_basis` 以强制 §7.2 重算。
    """
    prior = list(logistics_buffer.get("shopping_list_overlay") or [])
    action = str(slots.get("list_action") or "show").strip().lower()
    edits = _coerce_list_edit_ops(slots.get("list_edit_ops"))
    if action not in ("refresh_gap", "mark_bought", "edit_overlay"):
        action = "show"

    if action == "refresh_gap":
        updates["shopping_list_overlay"] = []
        updates["gap_basis"] = {}
        logger.info("[Logistics] §7.4 list_action=refresh_gap：已清空 overlay 并失效 gap_basis")
        return

    if action == "mark_bought":
        keys_raw = slots.get("mark_bought_items") or []
        if isinstance(keys_raw, str):
            keys_raw = [keys_raw]
        extra: List[Dict[str, Any]] = []
        if isinstance(keys_raw, list):
            for k in keys_raw:
                if k is not None and str(k).strip():
                    extra.append({"op": "remove", "key": str(k).strip()})
        if not extra and not edits:
            return
        updates["shopping_list_overlay"] = prior + edits + extra
        logger.info("[Logistics] §7.4 list_action=mark_bought：追加 remove 操作 %d 条", len(extra))
        return

    if action == "edit_overlay" and not edits:
        return

    if edits:
        updates["shopping_list_overlay"] = prior + edits
        logger.info("[Logistics] §7.4 合并 list_edit_ops：+%d 条 overlay 操作", len(edits))


def _global_set_merge_intent(user_text: str) -> bool:
    """§6.5.3：整表式「一共/总共/现在有多少」→ merge_mode=set（整句粗粒度）。"""
    t = (user_text or "").strip()
    return any(
        k in t for k in ("一共", "总共", "一共是", "现在是", "家里现在", "库存现在")
    )


def _build_add_preview_from_restock_rows(
    restock_rows: List[Any],
    user_text: str,
) -> Dict[str, Any]:
    """§6.5.3：解析 restock_items → add_preview（含 unresolved；禁止对含糊行猜测写库）。"""
    merge_default: str = "set" if _global_set_merge_intent(user_text) else "add"
    items: List[Dict[str, Any]] = []
    unresolved: List[str] = []
    for row in restock_rows or []:
        if not isinstance(row, dict):
            unresolved.append(str(row))
            continue
        raw_name = row.get("name") or row.get("ingredient") or ""
        name = normalize_ingredient_name(str(raw_name))
        if not name:
            unresolved.append(str(raw_name or "（空名）"))
            continue
        amt = row.get("amount")
        unit = str(row.get("unit") or "").strip()
        if amt is None:
            unresolved.append(name)
            continue
        try:
            amt_f = float(amt)
        except (TypeError, ValueError):
            unresolved.append(name)
            continue
        if amt_f <= 0:
            unresolved.append(name)
            continue
        if not unit:
            unresolved.append(f"{name}（缺少单位）")
            continue
        row_mode = row.get("merge_mode")
        mode = row_mode if row_mode in ("add", "set") else merge_default
        items.append(
            {
                "name": name,
                "delta_or_value": amt_f,
                "unit": unit,
                "merge_mode": mode,
            }
        )
    return {"items": items, "unresolved": unresolved, "source": "utterance"}


def _restock_auto_commit_without_user_ok(
    preview: Dict[str, Any], settings: Settings
) -> bool:
    """§6.5.3：confirm_required=false 时仅允许单条、正数、有单位且无 unresolved。"""
    if settings.get_inventory_restock_confirm_required():
        return False
    if preview.get("unresolved"):
        return False
    items = preview.get("items") or []
    if len(items) != 1:
        return False
    it = items[0]
    try:
        if float(it.get("delta_or_value") or 0) <= 0:
            return False
    except (TypeError, ValueError):
        return False
    return bool(str(it.get("unit") or "").strip())


def _restock_success_failed_lists(
    items: List[Dict[str, Any]], failed_names: List[str]
) -> Tuple[List[str], List[str]]:
    """§6.5.6 / FR-32：逐条成功与失败名单（用于话术，禁止整体成功措辞）。"""
    fs = set(failed_names)
    succ: List[str] = []
    fail: List[str] = []
    for it in items:
        n = str(it.get("name") or "").strip()
        if not n:
            continue
        (fail if n in fs else succ).append(n)
    return succ, fail


def _apply_restock_items(
    manager: "LogisticsManager", items: List[Dict[str, Any]]
) -> Tuple[str, List[str]]:
    """§6.5.3 批次写库：逐条 upsert/add，汇总 success | partial_success | failed。"""
    failed: List[str] = []
    for it in items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        try:
            val = float(it.get("delta_or_value") or 0)
        except (TypeError, ValueError):
            failed.append(name)
            continue
        ok = manager.inventory_manager.apply_restock(
            name,
            val,
            str(it.get("unit") or ""),
            str(it.get("merge_mode") or "add"),
        )
        if not ok:
            failed.append(name)
    n = len(items)
    if not failed:
        return "success", []
    if len(failed) < n:
        return "partial_success", failed
    return "failed", failed


def _locked_recipe_title_str(lb: Dict[str, Any]) -> str:
    t = lb.get("recipe_title_locked") or lb.get("selected_recipe_title") or ""
    return str(t).strip()


def _commit_recipe_matches_r_and_slots(
    lb: Dict[str, Any], slots: Dict[str, Any]
) -> bool:
    """
    规格 §6.3 条件 1：**R** 非空，且与当前锁定菜名一致（用户未报菜名时信任会话锁）。
    """
    req = lb.get("recipe_requirements") or []
    if not req:
        return False
    locked = _locked_recipe_title_str(lb)
    if not locked:
        return True
    anchor = (
        str(slots.get("recipe_name_for_commit") or slots.get("recipe_name") or "")
        .strip()
    )
    if not anchor:
        return True
    a = normalize_ingredient_name(anchor)
    b = normalize_ingredient_name(locked)
    if not a or not b:
        return True
    return a == b or a in b or b in a


def _recipe_title_for_gap_basis(state: AgentState, lb: Dict[str, Any]) -> str:
    """gap_basis.recipe_title：优先 buffer，其次 expert_payloads.recipe_detail.title。"""
    t = lb.get("recipe_title_locked") or lb.get("selected_recipe_title")
    if t:
        return str(t)
    detail = (state.get("expert_payloads") or {}).get("recipe_detail") or {}
    return str(detail.get("title") or "")


def _apply_silent_gap_precalc(
    manager: LogisticsManager,
    state: AgentState,
    logistics_buffer: Dict[str, Any],
    updates: Dict[str, Any],
) -> None:
    """
    规格 §1.3 步 5 / §7.1：R 非空则拉取最新 I；§7.3 指纹一致时**不重算**缺口，直接交付缓存 + overlay。
    须在 TASK_INV_COMMIT / TASK_INV_ADD 等可能改动库存的分支之后调用。
    """
    merged = {**logistics_buffer, **updates}
    recipe_req: List[Dict[str, Any]] = merged.get("recipe_requirements") or []
    if not recipe_req:
        return

    snapshot = manager.get_inventory_snapshot()
    updates["inventory_snapshot"] = snapshot

    if _gap_cache_valid(merged, snapshot):
        cache = merged.get("cached_shopping_gap") or {}
        overlay = merged.get("shopping_list_overlay") or []
        disp_sl, disp_suff = _merge_shopping_gap_overlay(cache, overlay)
        updates["cached_shopping_gap"] = copy.deepcopy(cache)
        updates["gap_basis"] = copy.deepcopy(merged.get("gap_basis") or {})
        updates["shopping_list"] = disp_sl
        updates["sufficient_items"] = disp_suff
        updates["missing_items"] = list(cache.get("missing_items") or [])
        updates["gap_delivery_mode"] = "cache"
        logger.info(
            "[Logistics] §7.3 缺口缓存命中（R+I 指纹一致），跳过 §7.2 全量重算；待购 %d 项",
            len(disp_sl),
        )
        return

    result = manager.calculate_shopping_gap(recipe_req, snapshot)
    computed_at = datetime.now(timezone.utc).isoformat()

    updates["cached_shopping_gap"] = {
        "shopping_list": result["shopping_list"],
        "sufficient_items": result["sufficient_items"],
        "missing_items": result.get("missing_items", []),
        "pending_manual": [],
        "computed_at": computed_at,
    }
    updates["gap_basis"] = {
        "recipe_title": _recipe_title_for_gap_basis(state, merged),
        "r_fingerprint": _stable_r_fingerprint(recipe_req),
        "inventory_fingerprint": _inventory_fingerprint(snapshot),
    }
    ov = merged.get("shopping_list_overlay") or []
    disp_sl, disp_suff = _merge_shopping_gap_overlay(updates["cached_shopping_gap"], ov)
    updates["shopping_list"] = disp_sl
    updates["sufficient_items"] = disp_suff
    updates["missing_items"] = result.get("missing_items", [])
    updates["gap_delivery_mode"] = "fresh"

    logger.info(
        "[Logistics] 静默缺口预计算完成（§7.1）：需购 %d 项，库存充足 %d 项",
        len(result["shopping_list"]),
        len(result["sufficient_items"]),
    )


class LogisticsManager:

    def __init__(
        self,
        db_path: str | None = None,
        *,
        household_id: str | None = None,
    ):
        settings = Settings()
        resolved_path = db_path if db_path is not None else settings.get_inventory_db_path()
        self.inventory_manager = InventoryManager(
            resolved_path,
            household_id=household_id,
        )
        self.unit_converter = UnitConverter()

    def calculate_shopping_gap(
        self, 
        required_ingredients: List[Dict[str, Any]],
        available_inventory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        计算购物缺口：shopping_list = max(0, required - inventory)
 
        Args:
            required_ingredients: 菜谱所需食材
              [{"name": "五花肉", "amount": 500, "unit": "g"}, ...]
            available_inventory: 当前库存（来自 get_inventory_snapshot）
              {"五花肉": {"amount": 200, "unit": "g"}, ...}
 
        Returns:
            {
                "shopping_list":    [{"name":..., "amount":..., "unit":...}],
                "sufficient_items": [{"name":..., "amount":..., "unit":...}],
                "missing_items":    []   # 库存里完全没有的食材
            }
        """
        shopping_list = []
        sufficient_items = []
        missing_items = []
 
        for ingredient in required_ingredients:
            name = ingredient.get("name", "").strip()
            req_amount = float(ingredient.get("amount", 0))
            req_unit = ingredient.get("unit", "g").strip()
 
            if not name or req_amount <= 0:
                continue
 
            inv = available_inventory.get(name)
 
            if inv is None:
                # 库存里完全没有这个食材
                missing_items.append({
                    "name": name,
                    "amount": req_amount,
                    "unit": req_unit
                })
                shopping_list.append({
                    "name": name,
                    "amount": req_amount,
                    "unit": req_unit
                })
                continue
 
            avail_amount = float(inv.get("amount", 0))
            avail_unit = inv.get("unit", req_unit)
 
            gap_val, gap_unit = self.unit_converter.gap(
                req_amount, req_unit,
                avail_amount, avail_unit
            )
 
            if gap_val > 0:
                shopping_list.append({
                    "name": name,
                    "amount": round(gap_val, 2),
                    "unit": gap_unit
                })
            else:
                sufficient_items.append({
                    "name": name,
                    "amount": req_amount,
                    "unit": req_unit
                })
 
        return {
            "shopping_list": shopping_list,
            "sufficient_items": sufficient_items,
            "missing_items": missing_items,
        }

    def get_inventory_snapshot(self) -> Dict[str, Any]:
        """获取当前 SCOPE 下 **I**（FR-30）；形态见 ``InventoryManager.get_inventory_snapshot_i``。"""
        return self.inventory_manager.get_inventory_snapshot_i()


    def update_inventory_after_cooking_report(
        self, used_ingredients: List[Dict[str, Any]]
    ) -> Tuple[str, List[str]]:
        """
        §6.4 / FR-32：扣减逐条报告；不因 aggregate bool 掩盖部分失败。
        """
        try:
            status, failed = self.inventory_manager.batch_deduct_report(
                used_ingredients
            )
            if status == "success":
                logger.info(
                    "库存扣减完成（attempted），食材行数 %d",
                    len(used_ingredients),
                )
            elif status == "partial_success":
                logger.warning("库存扣减部分失败: %s", failed)
            else:
                logger.warning("库存扣减失败: %s", failed)
            return status, failed
        except Exception as e:
            logger.error(f"库存扣减异常: {e}")
            names = [
                str(x.get("name") or "").strip()
                for x in used_ingredients
                if str(x.get("name") or "").strip()
            ]
            return "failed", names or ["(unknown)"]


    def add_to_inventory(self, items: List[Dict[str, Any]]) -> bool:
        """
        兼容旧形态：``[{"name","amount","unit"},...]`` 视为 **set** 语义批量 upsert。
        新补货路径请用 ``apply_restock`` / §6.5 ``merge_mode``。
        """
        try:
            ok = self.inventory_manager.batch_upsert(items)
            if ok:
                logger.info(f"补货完成，共 {len(items)} 种食材")
            return ok
        except Exception as e:
            logger.error(f"补货异常: {e}")
            return False


def logistics_manager_node(state: AgentState) -> Dict[str, Any]:
    """
    后勤主管节点，根据 task_stack 执行对应操作。
 
    任务路由：
      TASK_INV_CHECK   → 查库存快照
      TASK_GAP_CALC    → 计算购物缺口
      TASK_INV_COMMIT  → 确认烹饪，扣减库存
    """
    task_stack: List[str] = state.get("task_stack", []).copy()
    logistics_buffer: Dict[str, Any] = copy.deepcopy(get_runtime_bundle(state))
    manager = LogisticsManager()
    updates: Dict[str, Any] = {}
    settings = Settings()
    last_user_text = ""
    msgs = state.get("messages") or []
    if msgs:
        last = msgs[-1]
        last_user_text = getattr(last, "content", str(last))

    # ── TASK_INV_CHECK：查询库存快照 ──────────────────────
    if "TASK_INV_CHECK" in task_stack:
        logger.info("[Logistics] 执行库存查询")
        snapshot = manager.get_inventory_snapshot()
        updates["inventory_snapshot"] = snapshot
        logger.info(f"[Logistics] 库存快照: {len(snapshot)} 种食材")
        # task_stack.remove("TASK_INV_CHECK")  # 查询完成后移除任务
 
    # ── TASK_GAP_CALC：显式索要清单（§7.3：优先缓存；无 **R** 则 §9 GAP_CACHE_MISS） ──
    if "TASK_GAP_CALC" in task_stack:
        recipe_requirements = logistics_buffer.get("recipe_requirements") or []
        if not recipe_requirements:
            logger.warning("[Logistics] TASK_GAP_CALC 但 recipe_requirements 为空（§9）")
            updates["shopping_list"] = []
            updates["sufficient_items"] = []
            updates["missing_items"] = []
            updates["gap_delivery_mode"] = "empty"
            updates["error_state"] = {
                "error_code": "GAP_CACHE_MISS",
                "recoverable": True,
                "error_detail": "索要购物清单但当前无菜谱用料 **R**，无法计算缺口",
            }
        else:
            logger.info("[Logistics] TASK_GAP_CALC：文末 §7.1/§7.3 统一缺口与缓存命中判定")

    # ── TASK_INV_COMMIT：§6.3 扣减（须 recipe_use_confirmed + R + 菜名一致） ─────────
    if "TASK_INV_COMMIT" in task_stack:
        updates["commit_failed_items"] = []
        updates["commit_succeeded_items"] = []
        slots = logistics_buffer.get("slots") or {}
        intents_list = list(state.get("intents") or [])
        primary = str(state.get("primary_intent") or "")
        prior_confirmed = bool(logistics_buffer.get("recipe_use_confirmed"))
        adopted_this_turn = (
            "recipe_adopt" in intents_list
            or primary == "recipe_adopt"
            or bool(slots.get("recipe_adoption"))
        )
        recipe_use_confirmed = prior_confirmed or adopted_this_turn
        if adopted_this_turn:
            updates["recipe_use_confirmed"] = True

        recipe_requirements = logistics_buffer.get("recipe_requirements") or []

        if not recipe_requirements:
            logger.warning("[Logistics] recipe_requirements 为空，跳过库存扣减（§6.3）")
            updates["commit_status"] = "skipped"
        elif not recipe_use_confirmed:
            updates["commit_status"] = "blocked_no_confirm"
            updates["error_state"] = dict(CLEAR_ERROR_STATE)
            logger.info("[Logistics] §6.3：recipe_use_confirmed 为假，禁止 batch_deduct")
        elif not _commit_recipe_matches_r_and_slots(logistics_buffer, slots):
            updates["commit_status"] = "blocked_recipe_mismatch"
            updates["error_state"] = {
                "error_code": "COMMIT_RECIPE_MISMATCH",
                "recoverable": True,
                "error_detail": "扣减所指菜名与当前锁定菜谱不一致",
            }
            logger.info("[Logistics] §6.3：菜名锚点与锁定菜谱不一致，禁止扣减")
        else:
            st_ded, failed_names = manager.update_inventory_after_cooking_report(
                recipe_requirements
            )
            updates["commit_status"] = st_ded
            updates["commit_failed_items"] = list(failed_names)
            updates["commit_succeeded_items"] = []
            updates["error_state"] = dict(CLEAR_ERROR_STATE)
            if st_ded == "success":
                updates["commit_failed_items"] = []
                updates["recipe_use_confirmed"] = False
            elif st_ded == "partial_success":
                fn_set = set(failed_names)
                updates["commit_succeeded_items"] = [
                    str(r.get("name") or "").strip()
                    for r in recipe_requirements
                    if str(r.get("name") or "").strip()
                    and str(r.get("name") or "").strip() not in fn_set
                ]
                updates["error_state"] = {
                    "error_code": "INVENTORY_WRITE_FAILED",
                    "recoverable": True,
                    "error_detail": "部分食材扣减写入失败: "
                    + "、".join(failed_names),
                }
            else:
                updates["error_state"] = {
                    "error_code": "INVENTORY_WRITE_FAILED",
                    "recoverable": True,
                    "error_detail": "扣减写库失败，以下食材未能更新: "
                    + "、".join(failed_names)
                    if failed_names
                    else "扣减写库失败",
                }
            logger.info("[Logistics] 库存扣减状态: %s", st_ded)
        # task_stack.remove("TASK_INV_COMMIT")  # 扣减完成后移除任务

    # ── TASK_INV_ADD：§6.5 补货（预览 / 确认 / 写库） ──────────────────────
    if "TASK_INV_ADD" in task_stack:
        updates["add_succeeded_items"] = []
        updates["add_failed_items"] = []
        slots = logistics_buffer.get("slots") or {}
        prior_preview = logistics_buffer.get("add_preview") or {}
        prior_status = logistics_buffer.get("add_status")
        restock_confirm = bool(slots.get("restock_confirm"))

        if (
            prior_status == "pending"
            and restock_confirm
            and prior_preview.get("items")
        ):
            st_write, failed_names = _apply_restock_items(
                manager, list(prior_preview["items"])
            )
            updates["add_status"] = st_write
            updates["added_items"] = list(prior_preview["items"])
            updates["add_preview"] = None
            succ_names, fail_names = _restock_success_failed_lists(
                list(prior_preview["items"]), failed_names
            )
            updates["add_succeeded_items"] = succ_names
            updates["add_failed_items"] = fail_names
            updates["error_state"] = dict(CLEAR_ERROR_STATE)
            if st_write == "failed":
                updates["error_state"] = {
                    "error_code": "INVENTORY_WRITE_FAILED",
                    "recoverable": True,
                    "error_detail": "补货写库失败，未能更新库存。"
                    + (
                        f" 未写入：{'、'.join(fail_names)}。"
                        if fail_names
                        else ""
                    ),
                }
            elif st_write == "partial_success":
                updates["error_state"] = {
                    "error_code": "INVENTORY_WRITE_FAILED",
                    "recoverable": True,
                    "error_detail": (
                        "部分食材补货写入失败。"
                        f"已成功：{'、'.join(succ_names)}；"
                        f"未写入：{'、'.join(fail_names)}。"
                    ),
                }
            logger.info("[Logistics] §6.5 补货已确认并写库: status=%s", st_write)
        else:
            rows = slots.get("restock_items")
            if not isinstance(rows, list) or not rows:
                updates["add_status"] = "skipped"
                updates["add_preview"] = None
            else:
                preview = _build_add_preview_from_restock_rows(rows, last_user_text)
                updates["add_preview"] = preview

                if not preview["items"] and preview["unresolved"]:
                    updates["add_status"] = "failed"
                    updates["error_state"] = {
                        "error_code": "INVENTORY_ADD_UNPARSED",
                        "recoverable": True,
                        "error_detail": "补货意图下食材/数量/单位无法稳定解析",
                    }
                elif preview["unresolved"]:
                    updates["add_status"] = "pending"
                    updates["error_state"] = dict(CLEAR_ERROR_STATE)
                elif _restock_auto_commit_without_user_ok(preview, settings):
                    st_write, failed_names = _apply_restock_items(
                        manager, list(preview["items"])
                    )
                    updates["add_status"] = st_write
                    updates["added_items"] = list(preview["items"])
                    updates["add_preview"] = None
                    updates["error_state"] = dict(CLEAR_ERROR_STATE)
                    sn, fn = _restock_success_failed_lists(
                        list(preview["items"]), failed_names
                    )
                    updates["add_succeeded_items"] = sn
                    updates["add_failed_items"] = fn
                    if st_write != "success":
                        updates["error_state"] = {
                            "error_code": "INVENTORY_WRITE_FAILED",
                            "recoverable": True,
                            "error_detail": (
                                "补货写库未全部成功。"
                                f"已成功：{'、'.join(sn)}；未写入：{'、'.join(fn)}。"
                                if st_write == "partial_success"
                                else "补货写库失败，未能更新库存。"
                                + (f" 未写入：{'、'.join(fn)}。" if fn else "")
                            ),
                        }
                elif settings.get_inventory_restock_confirm_required():
                    updates["add_status"] = "pending"
                    updates["error_state"] = dict(CLEAR_ERROR_STATE)
                else:
                    st_write, failed_names = _apply_restock_items(
                        manager, list(preview["items"])
                    )
                    updates["add_status"] = st_write
                    updates["added_items"] = list(preview["items"])
                    updates["add_preview"] = None
                    updates["error_state"] = dict(CLEAR_ERROR_STATE)
                    sn, fn = _restock_success_failed_lists(
                        list(preview["items"]), failed_names
                    )
                    updates["add_succeeded_items"] = sn
                    updates["add_failed_items"] = fn
                    if st_write != "success":
                        updates["error_state"] = {
                            "error_code": "INVENTORY_WRITE_FAILED",
                            "recoverable": True,
                            "error_detail": (
                                "补货写库未全部成功。"
                                f"已成功：{'、'.join(sn)}；未写入：{'、'.join(fn)}。"
                                if st_write == "partial_success"
                                else "补货写库失败，未能更新库存。"
                                + (f" 未写入：{'、'.join(fn)}。" if fn else "")
                            ),
                        }

    # §7.4 / T-024：本轮槽位中的清单编辑 → overlay / 失效缓存（须在 §7.2 静默预计算之前）
    merged_slots = {**(logistics_buffer.get("slots") or {}), **(state.get("slots") or {})}
    _apply_list_action_to_overlay_updates(logistics_buffer, updates, merged_slots)

    # 规格 §1.3 步 5 / §7.1：R 非空则静默预计算（须在可能改写库存的分支之后）
    _apply_silent_gap_precalc(manager, state, logistics_buffer, updates)

    # T-020 / FR-30 / §6.1：logistics 任一路径结束后，将 DB 当前 **I** 写入 bundle，
    # 经 runtime_bundle_to_slice_patches → inventory_state.inventory_snapshot（§1.2.1 Dict 形态）
    updates["inventory_snapshot"] = manager.get_inventory_snapshot()

    new_logistics_buffer = {**logistics_buffer, **updates}
    out = {"task_stack": task_stack, **runtime_bundle_to_slice_patches(new_logistics_buffer)}
    return out
