"""
Logistics Manager Node for WHAT-TO-EAT-AGENT
 
职责：
  TASK_INV_CHECK   → 查询当前库存快照
  TASK_GAP_CALC    → 显式清单意图（仍依赖文末统一缺口计算写入缓存，避免重复）
  TASK_INV_COMMIT  → 用户确认烹饪后，扣减食材库存
 
  **规格 §1.3 步 5 / §7.1**：只要 **R**（recipe_requirements）非空，节点结束前 **静默**
  拉取 **I** 并执行 §7.2，写入 `cached_shopping_gap` 与 `gap_basis`；不要求用户本轮含清单意图，
  也不要求 generator 展开全文（FR-42）。
 
数据流：
  输入  state["logistics_buffer"]["recipe_requirements"]
        [{"name": "五花肉", "amount": 500, "unit": "g"}, ...]
  输出  state["logistics_buffer"]["inventory_snapshot"]   当前库存
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
from typing import Dict, Any, List
from ...libs.base.inventory import InventoryManager
from ...libs.utils.unit_converter import UnitConverter
from ..state import AgentState
from ..state_accessors import get_runtime_bundle
from ..state_sync import runtime_bundle_to_slice_patches

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
    规格 §1.3 步 5 / §7.1：R 非空则拉取最新 I 并写入 cached_shopping_gap、gap_basis。
    须在 TASK_INV_COMMIT / TASK_INV_ADD 等可能改动库存的分支之后调用。
    """
    merged = {**logistics_buffer, **updates}
    recipe_req: List[Dict[str, Any]] = merged.get("recipe_requirements") or []
    if not recipe_req:
        return

    snapshot = manager.get_inventory_snapshot()
    updates["inventory_snapshot"] = snapshot

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
    # 兼容旧 generator：保留顶层 shopping_list / sufficient_items / missing_items
    updates["shopping_list"] = result["shopping_list"]
    updates["sufficient_items"] = result["sufficient_items"]
    updates["missing_items"] = result.get("missing_items", [])

    logger.info(
        "[Logistics] 静默缺口预计算完成（§7.1）：需购 %d 项，库存充足 %d 项",
        len(result["shopping_list"]),
        len(result["sufficient_items"]),
    )


class LogisticsManager:

    def __init__(self, db_path: str = "data/db/inventory.db"):
        self.inventory_manager = InventoryManager(db_path=db_path)
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
        """获取当前全部库存。"""
        return self.inventory_manager.get_all()


    def update_inventory_after_cooking(self, used_ingredients: List[Dict[str, Any]]) -> bool:
        """
        用户确认烹饪后，批量扣减库存。
 
        Args:
            used_ingredients: 本次使用的食材
              [{"name": "五花肉", "amount": 500, "unit": "g"}, ...]
        """
        try:
            ok = self.inventory_manager.batch_deduct(used_ingredients)
            if ok:
                logger.info(f"库存扣减完成，共 {len(used_ingredients)} 种食材")
            else:
                logger.warning("库存扣减部分失败")
            return ok
        except Exception as e:
            logger.error(f"库存扣减异常: {e}")
            return False


    def add_to_inventory(self, items: List[Dict[str, Any]]) -> bool:
        """
        补货/手动添加食材到库存。
 
        Args:
            items: [{"name": "五花肉", "amount": 500, "unit": "g"}, ...]
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

    # ── TASK_INV_CHECK：查询库存快照 ──────────────────────
    if "TASK_INV_CHECK" in task_stack:
        logger.info("[Logistics] 执行库存查询")
        snapshot = manager.get_inventory_snapshot()
        updates["inventory_snapshot"] = snapshot
        logger.info(f"[Logistics] 库存快照: {len(snapshot)} 种食材")
        # task_stack.remove("TASK_INV_CHECK")  # 查询完成后移除任务
 
    # ── TASK_GAP_CALC：显式索要清单（缺口数值由文末 §7.1 静默预计算统一写入） ──
    if "TASK_GAP_CALC" in task_stack:
        recipe_requirements = logistics_buffer.get("recipe_requirements") or []
        if not recipe_requirements:
            logger.warning("[Logistics] TASK_GAP_CALC 但 recipe_requirements 为空，跳过")
            updates["shopping_list"] = []
            updates["sufficient_items"] = []
        else:
            logger.info("[Logistics] TASK_GAP_CALC：将与静默预计算共用同一 §7.2 结果")

    # ── TASK_INV_COMMIT：烹饪确认，扣减库存 ──────────────
    if "TASK_INV_COMMIT" in task_stack:
        recipe_requirements: List[Dict] = logistics_buffer.get("recipe_requirements", [])
 
        if not recipe_requirements:
            logger.warning("[Logistics] recipe_requirements 为空，跳过库存扣减")
            updates["commit_status"] = "skipped"
        else:
            ok = manager.update_inventory_after_cooking(recipe_requirements)
            updates["commit_status"] = "success" if ok else "failed"
            logger.info(f"[Logistics] 库存扣减状态: {updates['commit_status']}")
        # task_stack.remove("TASK_INV_COMMIT")  # 扣减完成后移除任务

    # ── TASK_INV_ADD：补货操作 ──────────────────────
    if "TASK_INV_ADD" in task_stack:
        print(f"🔍 [Logistics] TASK_INV_ADD 触发")
        print(f"🔍 [Logistics] extracted_entities: {logistics_buffer.get('extracted_entities', {})}")
    
        entities = logistics_buffer.get("extracted_entities", {})
        ingredients = entities.get("ingredients", [])
        amounts = entities.get("amounts", {})
        print(f"🔍 [Logistics] ingredients: {ingredients}, amounts: {amounts}")

        if not ingredients:
            updates["add_status"] = "skipped"
        else:
            items = []
            for name in ingredients:
                amount_str = amounts.get(name, "")
                if amount_str:
                    # router 提取到了数量，解析它
                    import re
                    m = re.match(r"([\d.]+)\s*(\S+)", amount_str)
                    if m:
                        amount_val = float(m.group(1))
                        unit_val = m.group(2)
                    else:
                        amount_val, unit_val = 1.0, "个"
                else:
                    # router 没有提取到数量，用默认值并记录警告
                    logger.warning(f"[Logistics-log] 食材 {name} 未提取到数量，使用默认值")
                    amount_val, unit_val = 1.0, "个"
                
                items.append({"name": name, "amount": amount_val, "unit": unit_val})

            ok = manager.add_to_inventory(items)
            updates["add_status"] = "success" if ok else "failed"
            updates["added_items"] = items  # 供 generator 展示
            logger.info(f"[Logistics] 补货完成: {items}")
        # task_stack.remove("TASK_INV_ADD")  # 补货完成后移除任务

    # 规格 §1.3 步 5 / §7.1：R 非空则静默预计算（须在可能改写库存的分支之后）
    _apply_silent_gap_precalc(manager, state, logistics_buffer, updates)

    new_logistics_buffer = {**logistics_buffer, **updates}
    out = {"task_stack": task_stack, **runtime_bundle_to_slice_patches(new_logistics_buffer)}
    return out
