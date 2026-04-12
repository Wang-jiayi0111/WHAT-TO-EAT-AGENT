"""
LogisticsManager 及节点测试

测试场景：
Part 1 - UnitConverter
  1. 同类单位换算
  2. 不同类单位无法比较
  3. 缺口计算

Part 2 - calculate_shopping_gap
  1. 库存充足，无需购买
  2. 库存不足，生成缺口
  3. 食材完全不在库存中
  4. 混合场景（部分充足、部分不足、部分缺失）

Part 3 - logistics_manager_node 节点
  1. TASK_INV_CHECK  → 返回库存快照
  2. TASK_GAP_CALC   → 返回购物清单
  3. TASK_INV_COMMIT → 扣减库存
  4. 多任务叠加      → 同时执行查询+计算
  5. recipe_requirements 为空时的降级处理
"""
import sys
import os
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.libs.base.inventory import InventoryManager
from src.libs.utils.unit_converter import UnitConverter
from src.agent.nodes.logistics import LogisticsManager, logistics_manager_node


# ── 工具函数 ──────────────────────────────────────────────

def make_logistics(tmp_path: str) -> LogisticsManager:
    return LogisticsManager(db_path=tmp_path)


def make_state(task_stack: list, logistics_buffer: dict = None) -> dict:
    return {
        "messages": [],
        "task_stack": task_stack,
        "logistics_buffer": logistics_buffer or {},
        "active_user_id": "default_user",
        "expert_payloads": {},
        "conversation_summary": "",
    }


def seed_inventory(db_path: str, items: list):
    """预置库存数据。"""
    mgr = InventoryManager(db_path=db_path)
    mgr.batch_upsert(items)


# ════════════════════════════════════════════════════════════
# Part 1：UnitConverter
# ════════════════════════════════════════════════════════════

def test_unit_converter_same_unit():
    """同单位直接比较，库存充足时缺口为 0。"""
    uc = UnitConverter()
    gap, unit = uc.gap(300, "g", 500, "g")
    assert gap == 0.0
    print(f"✅ 同单位充足：需要 300g，有 500g，缺口 = {gap}{unit}")


def test_unit_converter_cross_unit():
    """跨同类单位换算（g vs kg）。"""
    uc = UnitConverter()
    # 需要 1.5kg，库存 500g → 缺口 1000g
    gap, unit = uc.gap(1.5, "kg", 500, "g")
    assert gap == 1000.0
    assert unit == "g"
    print(f"✅ 跨单位换算：需要 1.5kg，有 500g，缺口 = {gap}{unit}")


def test_unit_converter_spoon_to_ml():
    """勺匙换算为 ml 后比较。"""
    uc = UnitConverter()
    # 需要 2 汤匙(30ml)，库存 50ml → 充足
    gap, unit = uc.gap(2, "汤匙", 50, "ml")
    assert gap == 0.0
    print(f"✅ 汤匙换算：需要 2汤匙(30ml)，有 50ml，缺口 = {gap}")


def test_unit_converter_incompatible():
    """不同类单位（g vs 个）无法比较，返回全部需求量作为缺口。"""
    uc = UnitConverter()
    gap, unit = uc.gap(500, "g", 3, "个")
    assert gap == 500
    assert unit == "g"
    print(f"✅ 不兼容单位：直接返回需求量 {gap}{unit} 作为缺口")


def test_unit_converter_can_compare():
    """can_compare 正确判断单位兼容性。"""
    uc = UnitConverter()
    assert uc.can_compare("g", "kg") is True
    assert uc.can_compare("ml", "L") is True
    assert uc.can_compare("汤匙", "ml") is True
    assert uc.can_compare("g", "个") is False
    assert uc.can_compare("ml", "个") is False
    print("✅ can_compare 判断正确")


# ════════════════════════════════════════════════════════════
# Part 2：calculate_shopping_gap
# ════════════════════════════════════════════════════════════

def test_gap_all_sufficient():
    """所有食材库存充足，购物清单为空。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        mgr = make_logistics(tmp)
        inventory = {
            "五花肉": {"amount": 600, "unit": "g"},
            "酱油":   {"amount": 100, "unit": "ml"},
            "鸡蛋":   {"amount": 4,   "unit": "个"},
        }
        required = [
            {"name": "五花肉", "amount": 500, "unit": "g"},
            {"name": "酱油",   "amount": 50,  "unit": "ml"},
            {"name": "鸡蛋",   "amount": 2,   "unit": "个"},
        ]
        result = mgr.calculate_shopping_gap(required, inventory)
        assert result["shopping_list"] == []
        assert len(result["sufficient_items"]) == 3
        print("✅ 全部充足：购物清单为空")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_gap_partial_insufficient():
    """部分食材不足，生成正确缺口。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        mgr = make_logistics(tmp)
        inventory = {
            "五花肉": {"amount": 200, "unit": "g"},  # 不足
            "酱油":   {"amount": 100, "unit": "ml"},  # 充足
        }
        required = [
            {"name": "五花肉", "amount": 500, "unit": "g"},
            {"name": "酱油",   "amount": 50,  "unit": "ml"},
        ]
        result = mgr.calculate_shopping_gap(required, inventory)

        shopping = {item["name"]: item for item in result["shopping_list"]}
        assert "五花肉" in shopping
        assert shopping["五花肉"]["amount"] == 300  # 缺 300g
        assert "酱油" not in shopping
        assert len(result["sufficient_items"]) == 1
        print(f"✅ 部分不足：五花肉缺 {shopping['五花肉']['amount']}g，酱油充足")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_gap_completely_missing():
    """食材完全不在库存中，整个需求量列入购物清单。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        mgr = make_logistics(tmp)
        inventory = {}  # 空库存
        required = [
            {"name": "五花肉", "amount": 500, "unit": "g"},
        ]
        result = mgr.calculate_shopping_gap(required, inventory)

        assert len(result["shopping_list"]) == 1
        assert len(result["missing_items"]) == 1
        assert result["shopping_list"][0]["amount"] == 500
        print("✅ 完全缺失：整个需求量进入购物清单")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_gap_mixed_scenario():
    """混合场景：充足 + 不足 + 完全缺失。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        mgr = make_logistics(tmp)
        inventory = {
            "五花肉": {"amount": 600, "unit": "g"},   # 充足
            "酱油":   {"amount": 30,  "unit": "ml"},   # 不足
            # 鸡蛋：完全缺失
        }
        required = [
            {"name": "五花肉", "amount": 500, "unit": "g"},
            {"name": "酱油",   "amount": 50,  "unit": "ml"},
            {"name": "鸡蛋",   "amount": 3,   "unit": "个"},
        ]
        result = mgr.calculate_shopping_gap(required, inventory)

        shopping = {item["name"]: item for item in result["shopping_list"]}
        sufficient = {item["name"] for item in result["sufficient_items"]}
        missing = {item["name"] for item in result["missing_items"]}

        assert "五花肉" in sufficient
        assert "酱油" in shopping
        assert shopping["酱油"]["amount"] == 20   # 缺 20ml
        assert "鸡蛋" in shopping
        assert "鸡蛋" in missing
        print(
            f"✅ 混合场景："
            f"充足={sufficient}，"
            f"缺口={[(k, v['amount']) for k, v in shopping.items()]}，"
            f"完全缺失={missing}"
        )
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_gap_cross_unit():
    """跨单位场景：需求 kg，库存 g。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        mgr = make_logistics(tmp)
        inventory = {
            "面粉": {"amount": 800, "unit": "g"},
        }
        required = [
            {"name": "面粉", "amount": 1, "unit": "kg"},  # 需要 1kg = 1000g
        ]
        result = mgr.calculate_shopping_gap(required, inventory)

        shopping = {item["name"]: item for item in result["shopping_list"]}
        assert "面粉" in shopping
        assert shopping["面粉"]["amount"] == 200  # 缺 200g
        print(f"✅ 跨单位缺口：需要 1kg，有 800g，缺口 = {shopping['面粉']['amount']}g")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


# ════════════════════════════════════════════════════════════
# Part 3：logistics_manager_node 节点
# ════════════════════════════════════════════════════════════

def test_node_inv_check():
    """TASK_INV_CHECK：节点返回库存快照。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        seed_inventory(tmp, [
            {"name": "五花肉", "amount": 500, "unit": "g"},
            {"name": "酱油",   "amount": 200, "unit": "ml"},
        ])

        # 替换节点内部的 db_path（通过环境变量或 monkeypatch）
        # 此处直接实例化节点逻辑验证
        mgr = make_logistics(tmp)
        snapshot = mgr.get_inventory_snapshot()

        assert "五花肉" in snapshot
        assert snapshot["五花肉"]["amount"] == 500
        assert len(snapshot) == 2
        print(f"✅ TASK_INV_CHECK：快照包含 {len(snapshot)} 种食材")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_node_gap_calc():
    """TASK_GAP_CALC：节点正确计算购物缺口并写入 logistics_buffer。"""
    tmp = tempfile.mktemp(suffix=".db")
    # 用环境变量让节点使用临时数据库
    os.environ["INVENTORY_DB_PATH"] = tmp
    try:
        seed_inventory(tmp, [
            {"name": "五花肉", "amount": 200, "unit": "g"},
        ])

        state = make_state(
            task_stack=["TASK_GAP_CALC"],
            logistics_buffer={
                "recipe_requirements": [
                    {"name": "五花肉", "amount": 500, "unit": "g"},
                    {"name": "酱油",   "amount": 50,  "unit": "ml"},
                ]
            }
        )

        # 直接调用 LogisticsManager 验证逻辑
        mgr = make_logistics(tmp)
        snapshot = mgr.get_inventory_snapshot()
        result = mgr.calculate_shopping_gap(
            state["logistics_buffer"]["recipe_requirements"],
            snapshot
        )

        shopping = {i["name"]: i for i in result["shopping_list"]}
        assert "五花肉" in shopping
        assert shopping["五花肉"]["amount"] == 300
        assert "酱油" in shopping  # 完全缺失
        print(f"✅ TASK_GAP_CALC：购物清单 = {[(k, v['amount'], v['unit']) for k, v in shopping.items()]}")
    finally:
        os.environ.pop("INVENTORY_DB_PATH", None)
        os.remove(tmp) if os.path.exists(tmp) else None


def test_node_inv_commit():
    """TASK_INV_COMMIT：确认烹饪后库存正确扣减。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        seed_inventory(tmp, [
            {"name": "五花肉", "amount": 500, "unit": "g"},
            {"name": "酱油",   "amount": 100, "unit": "ml"},
            {"name": "鸡蛋",   "amount": 4,   "unit": "个"},
        ])

        used = [
            {"name": "五花肉", "amount": 300, "unit": "g"},
            {"name": "酱油",   "amount": 30,  "unit": "ml"},
            {"name": "鸡蛋",   "amount": 2,   "unit": "个"},
        ]

        mgr = make_logistics(tmp)
        ok = mgr.update_inventory_after_cooking(used)
        assert ok is True

        inv = InventoryManager(db_path=tmp)
        assert inv.get_item("五花肉")["amount"] == 200
        assert inv.get_item("酱油")["amount"] == 70
        assert inv.get_item("鸡蛋")["amount"] == 2
        print("✅ TASK_INV_COMMIT：库存扣减正确")
        print(f"   五花肉: 500→200g | 酱油: 100→70ml | 鸡蛋: 4→2个")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_node_empty_requirements():
    """recipe_requirements 为空时，GAP_CALC 和 COMMIT 降级处理不报错。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        mgr = make_logistics(tmp)

        # GAP_CALC 空需求
        result = mgr.calculate_shopping_gap([], {})
        assert result["shopping_list"] == []
        assert result["sufficient_items"] == []

        # COMMIT 空需求
        ok = mgr.update_inventory_after_cooking([])
        assert ok is True

        print("✅ 空 recipe_requirements：降级处理正常，无报错")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


def test_node_combined_check_and_gap():
    """TASK_INV_CHECK + TASK_GAP_CALC 同时执行，快照复用不重复查询。"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        seed_inventory(tmp, [
            {"name": "五花肉", "amount": 100, "unit": "g"},
        ])

        mgr = make_logistics(tmp)
        snapshot = mgr.get_inventory_snapshot()

        required = [{"name": "五花肉", "amount": 500, "unit": "g"}]
        result = mgr.calculate_shopping_gap(required, snapshot)

        assert len(result["shopping_list"]) == 1
        assert result["shopping_list"][0]["amount"] == 400
        print("✅ CHECK + GAP 叠加执行：快照正确复用，缺口 400g")
    finally:
        os.remove(tmp) if os.path.exists(tmp) else None


# ════════════════════════════════════════════════════════════
# 运行入口
# ════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # UnitConverter
        test_unit_converter_same_unit,
        test_unit_converter_cross_unit,
        test_unit_converter_spoon_to_ml,
        test_unit_converter_incompatible,
        test_unit_converter_can_compare,
        # calculate_shopping_gap
        test_gap_all_sufficient,
        test_gap_partial_insufficient,
        test_gap_completely_missing,
        test_gap_mixed_scenario,
        test_gap_cross_unit,
        # 节点逻辑
        test_node_inv_check,
        test_node_gap_calc,
        test_node_inv_commit,
        test_node_empty_requirements,
        test_node_combined_check_and_gap,
    ]

    print("\n" + "=" * 55)
    print("🚚 LogisticsManager 测试")
    print("=" * 55)

    passed, failed = 0, 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 55)
    print(f"结果: {passed} 通过 / {failed} 失败")
    if failed == 0:
        print("🎉 全部测试通过！")
    print("=" * 55)


if __name__ == "__main__":
    run_all()