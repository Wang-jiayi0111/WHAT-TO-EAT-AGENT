"""
InventoryManager 测试

测试场景：
1. 基础 CRUD  - 新增、查询、更新、删除
2. UPSERT     - 重复写入覆盖而非报错
3. 批量操作   - batch_upsert / batch_deduct
4. 扣减边界   - 扣减后不低于 0
5. 不存在食材  - 扣减/查询不存在的食材
6. add_amount  - 增量累加
"""
import sys
import asyncio
import tempfile
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.libs.base.inventory import InventoryManager


# ── fixture：每个测试用独立的临时数据库 ───────────────────
def make_manager() -> tuple[InventoryManager, str]:
    """返回 (manager, tmp_path)，测试结束后手动删除。"""
    tmp = tempfile.mktemp(suffix=".db")
    return InventoryManager(db_path=tmp), tmp


def cleanup(path: str):
    try:
        os.remove(path)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
# 1. 基础 CRUD
# ════════════════════════════════════════════════════════════

def test_upsert_and_get_item():
    """写入后能正确查询到。"""
    mgr, tmp = make_manager()
    try:
        ok = mgr.upsert("五花肉", 500, "g")
        assert ok is True

        item = mgr.get_item("五花肉")
        assert item is not None
        assert item["amount"] == 500
        assert item["unit"] == "g"
        print("✅ upsert + get_item 正常")
    finally:
        cleanup(tmp)


def test_get_item_not_exist():
    """查询不存在的食材返回 None。"""
    mgr, tmp = make_manager()
    try:
        result = mgr.get_item("不存在的食材")
        assert result is None
        print("✅ 不存在食材返回 None")
    finally:
        cleanup(tmp)


def test_get_all_empty():
    """空库存返回空字典。"""
    mgr, tmp = make_manager()
    try:
        result = mgr.get_all()
        assert result == {}
        print("✅ 空库存返回空字典")
    finally:
        cleanup(tmp)


def test_get_all_multiple():
    """多个食材全部能查到。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 500, "g")
        mgr.upsert("酱油", 200, "ml")
        mgr.upsert("鸡蛋", 6, "个")

        result = mgr.get_all()
        assert len(result) == 3
        assert "五花肉" in result
        assert "酱油" in result
        assert "鸡蛋" in result
        print(f"✅ get_all 返回 {len(result)} 种食材")
    finally:
        cleanup(tmp)


def test_delete_item():
    """删除后查询返回 None。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 500, "g")
        ok = mgr.delete_item("五花肉")
        assert ok is True

        item = mgr.get_item("五花肉")
        assert item is None
        print("✅ delete_item 正常")
    finally:
        cleanup(tmp)


def test_delete_nonexistent():
    """删除不存在的食材返回 False。"""
    mgr, tmp = make_manager()
    try:
        ok = mgr.delete_item("不存在")
        assert ok is False
        print("✅ 删除不存在食材返回 False")
    finally:
        cleanup(tmp)


# ════════════════════════════════════════════════════════════
# 2. UPSERT 覆盖
# ════════════════════════════════════════════════════════════

def test_upsert_overwrites():
    """同一食材二次写入应覆盖，不新增记录。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 500, "g")
        mgr.upsert("五花肉", 300, "g")  # 覆盖

        item = mgr.get_item("五花肉")
        assert item["amount"] == 300

        all_items = mgr.get_all()
        assert len(all_items) == 1  # 只有一条记录
        print("✅ UPSERT 覆盖正常，无重复记录")
    finally:
        cleanup(tmp)


def test_upsert_changes_unit():
    """UPSERT 可以更新单位。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("盐", 100, "g")
        mgr.upsert("盐", 0.1, "kg")

        item = mgr.get_item("盐")
        assert item["unit"] == "kg"
        assert item["amount"] == 0.1
        print("✅ UPSERT 更新单位正常")
    finally:
        cleanup(tmp)


# ════════════════════════════════════════════════════════════
# 3. 扣减逻辑
# ════════════════════════════════════════════════════════════

def test_deduct_normal():
    """正常扣减后数量正确。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 500, "g")
        ok = mgr.deduct("五花肉", 200, "g")
        assert ok is True

        item = mgr.get_item("五花肉")
        assert item["amount"] == 300
        print("✅ 正常扣减：500g - 200g = 300g")
    finally:
        cleanup(tmp)


def test_deduct_below_zero():
    """扣减量超过库存时，结果置为 0，不变为负数。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("酱油", 100, "ml")
        mgr.deduct("酱油", 300, "ml")  # 扣 300，只有 100

        item = mgr.get_item("酱油")
        assert item["amount"] == 0
        print("✅ 扣减超量后置为 0，不出现负值")
    finally:
        cleanup(tmp)


def test_deduct_exact():
    """恰好扣完，结果为 0。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("生抽", 50, "ml")
        mgr.deduct("生抽", 50, "ml")

        item = mgr.get_item("生抽")
        assert item["amount"] == 0
        print("✅ 恰好扣完，结果为 0")
    finally:
        cleanup(tmp)


def test_deduct_nonexistent_skip():
    """扣减库存中不存在的食材，直接跳过不报错，返回 True。"""
    mgr, tmp = make_manager()
    try:
        ok = mgr.deduct("不存在的食材", 100, "g")
        assert ok is True
        print("✅ 扣减不存在食材：跳过，返回 True")
    finally:
        cleanup(tmp)


# ════════════════════════════════════════════════════════════
# 4. add_amount 累加
# ════════════════════════════════════════════════════════════

def test_add_amount_existing():
    """已有食材的累加。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 200, "g")
        mgr.add_amount("五花肉", 300, "g")

        item = mgr.get_item("五花肉")
        assert item["amount"] == 500
        print("✅ add_amount 累加：200g + 300g = 500g")
    finally:
        cleanup(tmp)


def test_add_amount_new_item():
    """不存在的食材调用 add_amount 应新建记录。"""
    mgr, tmp = make_manager()
    try:
        mgr.add_amount("新食材", 100, "g")

        item = mgr.get_item("新食材")
        assert item is not None
        assert item["amount"] == 100
        print("✅ add_amount 新食材：自动新建记录")
    finally:
        cleanup(tmp)


# ════════════════════════════════════════════════════════════
# 5. 批量操作
# ════════════════════════════════════════════════════════════

def test_batch_upsert():
    """批量写入多个食材。"""
    mgr, tmp = make_manager()
    try:
        items = [
            {"name": "五花肉", "amount": 500, "unit": "g"},
            {"name": "酱油",   "amount": 200, "unit": "ml"},
            {"name": "鸡蛋",   "amount": 6,   "unit": "个"},
            {"name": "盐",     "amount": 2,   "unit": "茶匙"},
        ]
        ok = mgr.batch_upsert(items)
        assert ok is True

        all_items = mgr.get_all()
        assert len(all_items) == 4
        assert all_items["五花肉"]["amount"] == 500
        assert all_items["鸡蛋"]["unit"] == "个"
        print(f"✅ batch_upsert 写入 {len(items)} 种食材")
    finally:
        cleanup(tmp)


def test_batch_deduct():
    """批量扣减。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 500, "g")
        mgr.upsert("酱油",   200, "ml")
        mgr.upsert("鸡蛋",   6,   "个")

        used = [
            {"name": "五花肉", "amount": 300, "unit": "g"},
            {"name": "酱油",   "amount": 50,  "unit": "ml"},
            {"name": "鸡蛋",   "amount": 2,   "unit": "个"},
        ]
        ok = mgr.batch_deduct(used)
        assert ok is True

        assert mgr.get_item("五花肉")["amount"] == 200
        assert mgr.get_item("酱油")["amount"] == 150
        assert mgr.get_item("鸡蛋")["amount"] == 4
        print("✅ batch_deduct 正常")
    finally:
        cleanup(tmp)


def test_batch_deduct_with_missing():
    """批量扣减时，库存中不存在的食材跳过，其余正常扣减。"""
    mgr, tmp = make_manager()
    try:
        mgr.upsert("五花肉", 500, "g")

        used = [
            {"name": "五花肉",  "amount": 200, "unit": "g"},
            {"name": "不存在的", "amount": 100, "unit": "g"},  # 跳过
        ]
        ok = mgr.batch_deduct(used)
        assert ok is True
        assert mgr.get_item("五花肉")["amount"] == 300
        print("✅ batch_deduct 含不存在食材：正常跳过")
    finally:
        cleanup(tmp)


# ════════════════════════════════════════════════════════════
# 运行入口
# ════════════════════════════════════════════════════════════

def run_all():
    tests = [
        test_upsert_and_get_item,
        test_get_item_not_exist,
        test_get_all_empty,
        test_get_all_multiple,
        test_delete_item,
        test_delete_nonexistent,
        test_upsert_overwrites,
        test_upsert_changes_unit,
        test_deduct_normal,
        test_deduct_below_zero,
        test_deduct_exact,
        test_deduct_nonexistent_skip,
        test_add_amount_existing,
        test_add_amount_new_item,
        test_batch_upsert,
        test_batch_deduct,
        test_batch_deduct_with_missing,
    ]

    print("\n" + "=" * 50)
    print("📦 InventoryManager 测试")
    print("=" * 50)

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

    print("\n" + "=" * 50)
    print(f"结果: {passed} 通过 / {failed} 失败")
    if failed == 0:
        print("🎉 全部测试通过！")
    print("=" * 50)


if __name__ == "__main__":
    run_all()