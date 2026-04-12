"""
UnitConverter - 食材单位换算工具
 
支持：
- 重量：g / kg
- 体积：ml / L
- 个数：个 / 只 / 颗 / 根 / 片 / 块
- 勺匙：勺 / 茶匙 / 汤匙
 
换算策略：
  同类单位之间直接换算为基准单位（g、ml、个、ml）后再比较。
  不同类单位（如 g vs 个）无法换算，视为"不可比较"，直接要求购买。
"""
from typing import Optional, Tuple

 
# ── 基准单位 ──────────────────────────────────────────────
BASE_UNIT = {
    "weight": "g",
    "volume": "ml",
    "count":  "个",
    "spoon":  "ml",   # 勺匙统一换算为 ml
}

# ── 各单位到基准单位的换算系数 ─────────────────────────────
CONVERSION = {
    # 重量 → g
    "g":   ("weight", 1.0),
    "克":  ("weight", 1.0),
    "kg":  ("weight", 1000.0),
    "千克": ("weight", 1000.0),
    "斤":  ("weight", 500.0),
    "两":  ("weight", 50.0),
 
    # 体积 → ml
    "ml":  ("volume", 1.0),
    "毫升": ("volume", 1.0),
    "l":   ("volume", 1000.0),
    "L":   ("volume", 1000.0),
    "升":  ("volume", 1000.0),
 
    # 勺匙 → ml
    "茶匙": ("spoon", 5.0),
    "tsp": ("spoon", 5.0),
    "汤匙": ("spoon", 15.0),
    "tbsp": ("spoon", 15.0),
    "勺":  ("spoon", 15.0),
    "小勺":  ("spoon", 5.0),   # 等同于茶匙
    "大勺":  ("spoon", 15.0),  # 等同于汤匙
    "匙":    ("spoon", 15.0),
    "少许":  ("count", 1.0),   # 无法精确换算，按 1 个处理
    "适量":  ("count", 1.0),
 
    # 个数 → 个（系数都是 1，只做同类判断）
    "个":  ("count", 1.0),
    "只":  ("count", 1.0),
    "颗":  ("count", 1.0),
    "根":  ("count", 1.0),
    "片":  ("count", 1.0),
    "块":  ("count", 1.0),
    "条":  ("count", 1.0),
    "头":  ("count", 1.0),
    "瓣":  ("count", 1.0),
}

class UnitConverter:
    """食材单位换算，核心方法是 to_base 和 can_compare。"""
 
    def to_base(self, amount: float, unit: str) -> Tuple[Optional[float], Optional[str]]:
        """
        将 (amount, unit) 换算为基准量。
 
        Returns:
            (base_amount, category) 或 (None, None) 表示单位未知
        """
        unit = unit.strip()
        entry = CONVERSION.get(unit)
        if entry is None:
            return None, None
        category, factor = entry
        return amount * factor, category
 
    def can_compare(self, unit_a: str, unit_b: str) -> bool:
        """判断两个单位是否可以比较（同类）。"""
        entry_a = CONVERSION.get(unit_a.strip())
        entry_b = CONVERSION.get(unit_b.strip())
        if entry_a is None or entry_b is None:
            return False
        # spoon 和 volume 都换算为 ml，可以比较
        cat_a = "volume" if entry_a[0] == "spoon" else entry_a[0]
        cat_b = "volume" if entry_b[0] == "spoon" else entry_b[0]
        return cat_a == cat_b
 
    def gap(self, required: float, req_unit: str,
            available: float, avail_unit: str) -> Tuple[float, str]:
        """
        计算缺口：max(0, required_in_base - available_in_base)
 
        Returns:
            (gap_amount, base_unit_str)
            gap_amount == 0 表示库存充足
        """
        if not self.can_compare(req_unit, avail_unit):
            # 单位不同类，无法比较，返回全部需求量作为缺口
            return required, req_unit
 
        req_base, category = self.to_base(required, req_unit)
        avail_base, _ = self.to_base(available, avail_unit)
 
        gap_val = max(0.0, req_base - avail_base)
 
        # 返回基准单位
        base_unit_map = {
            "weight": "g",
            "volume": "ml",
            "count": "个",
            "spoon": "ml",
        }
        return gap_val, base_unit_map.get(category, req_unit)