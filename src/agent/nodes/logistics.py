"""
Logistics Manager Node for WHAT-TO-EAT-AGENT
 
职责：
  TASK_INV_CHECK   → 查询当前库存快照
  TASK_GAP_CALC    → 对比菜谱需求与库存，生成购物清单
  TASK_INV_COMMIT  → 用户确认烹饪后，扣减食材库存
 
数据流：
  输入  state["logistics_buffer"]["recipe_requirements"]
        [{"name": "五花肉", "amount": 500, "unit": "g"}, ...]
  输出  state["logistics_buffer"]["inventory_snapshot"]   当前库存
        state["logistics_buffer"]["shopping_list"]        购物缺口
        state["logistics_buffer"]["sufficient_items"]     库存充足的食材
"""

from typing import Dict, Any, List
import logging
from ...libs.base.inventory import InventoryManager
from ...libs.utils.unit_converter import UnitConverter
from ..state import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
    logistics_buffer: Dict = state.get("logistics_buffer", {})
    manager = LogisticsManager()
    updates: Dict[str, Any] = {}

    # ── TASK_INV_CHECK：查询库存快照 ──────────────────────
    if "TASK_INV_CHECK" in task_stack:
        logger.info("[Logistics] 执行库存查询")
        snapshot = manager.get_inventory_snapshot()
        updates["inventory_snapshot"] = snapshot
        logger.info(f"[Logistics] 库存快照: {len(snapshot)} 种食材")
        # task_stack.remove("TASK_INV_CHECK")  # 查询完成后移除任务
 
   # ── TASK_GAP_CALC：计算购物缺口 ──────────────────────
    if "TASK_GAP_CALC" in task_stack:
        recipe_requirements: List[Dict] = logistics_buffer.get("recipe_requirements", [])
 
        if not recipe_requirements:
            logger.warning("[Logistics] recipe_requirements 为空，跳过缺口计算")
            updates["shopping_list"] = []
            updates["sufficient_items"] = []
        else:
            snapshot = updates.get(
                "inventory_snapshot",
                manager.get_inventory_snapshot()
            )
            result = manager.calculate_shopping_gap(recipe_requirements, snapshot)
 
            updates["shopping_list"] = result["shopping_list"]
            updates["sufficient_items"] = result["sufficient_items"]
            updates["missing_items"] = result["missing_items"]
 
            logger.info(
                f"[Logistics] 购物清单: {len(result['shopping_list'])} 种需购买，"
                f"{len(result['sufficient_items'])} 种库存充足"
            )
        # task_stack.remove("TASK_GAP_CALC")  # 计算完成后移除任务

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
    
    new_logistics_buffer = {**logistics_buffer, **updates}
    return {
        "logistics_buffer": new_logistics_buffer,
        "task_stack": task_stack
        }
