"""
T-032 库存表迁移与 SCOPE 对齐 — 测试文档与自动化用例
====================================================

**任务**：T-032  
**规格**：§6.2（复合主键、`WHERE household_id`）、§8（`SCOPE_ID` / `household.default_id`）  
**开发记录**：`docs/dev_log.md` [DEV-022]

【测试计划】
-----------
**目标**：验证 `InventoryManager` 启动迁移、读写作用域隔离与 legacy 表形态映射符合规格。

**用例映射**（与 `docs/test_report.md` [TR-027] 同步）：

=========  ================================  ==================
  编号      场景                              规格 / 依据
=========  ================================  ==================
  TC-001    空库首次打开 → §6.2 表结构        §6.2
  TC-002    旧 `name` 主键表迁移绑定 SCOPE   §6.2 迁移
  TC-003    integrity 旧列映射              DEV-022
  TC-004    双 `household_id` 同库隔离      §8
=========  ================================  ==================

**禁止行为（例行）**：库存键不得为 `thread_id`；业务队列名为 `task_stack`。

**执行**：在仓库根 `python -m pytest tests/unit/test_t032_inventory_migration.py -v`；
全量回归见测试报告 [TR-027]「测试过程信息」节。

验收结论与每轮命令输出、用例统计以 **`docs/test_report.md`** 为准维护，本文件不重复粘贴历史输出。
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

from src.libs.base.inventory import InventoryManager, _migrate_to_v62


def _pragma_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table})")
    return [str(r[1]) for r in c.fetchall()]


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def test_t032_tc001_empty_db_creates_section62_schema() -> None:
    """TC-001：空库首次 `InventoryManager` → 存在 household_id 与复合主键。"""
    path = _temp_db_path()
    m = InventoryManager(path, household_id="scope_a")
    conn = sqlite3.connect(path)
    try:
        cols = _pragma_columns(conn, "inventory")
        assert "household_id" in cols
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='inventory'"
        ).fetchone()
        assert row and row[0]
        assert "PRIMARY KEY" in row[0] and "household_id" in row[0]
    finally:
        conn.close()
    assert m.get_all() == {}


def test_t032_tc002_legacy_name_pk_migrates_to_household_scope() -> None:
    """TC-002：旧 name 单列主键表迁移后，数据绑定传入的 household_id。"""
    path = _temp_db_path()
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE inventory (name TEXT PRIMARY KEY NOT NULL, "
        "amount REAL NOT NULL, unit TEXT NOT NULL)"
    )
    c.execute("INSERT INTO inventory VALUES (?,?,?)", ("egg", 3.0, "个"))
    conn.commit()
    conn.close()

    m = InventoryManager(path, household_id="hh_legacy")
    assert m.get_all() == {"egg": {"amount": 3.0, "unit": "个"}}
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT household_id, name FROM inventory").fetchall()
        assert rows == [("hh_legacy", "egg")]
    finally:
        conn.close()


def test_t032_tc003_legacy_integrity_shape_user_id_mapping() -> None:
    """TC-003：旧 integrity 形（user_id/item_name/quantity）；空 user_id 回落迁移参数。"""
    path = _temp_db_path()
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE inventory (user_id TEXT, item_name TEXT, quantity REAL, unit TEXT)"
    )
    c.execute("INSERT INTO inventory VALUES (?,?,?,?)", ("u1", "milk", 1.0, "L"))
    c.execute("INSERT INTO inventory VALUES (?,?,?,?)", ("", "water", 2.0, "L"))
    conn.commit()
    conn.close()

    c3 = sqlite3.connect(path)
    try:
        _migrate_to_v62(c3, household_id="fallback_scope")
    finally:
        c3.close()

    conn = sqlite3.connect(path)
    try:
        r = conn.execute(
            "SELECT household_id, name, amount FROM inventory ORDER BY name"
        ).fetchall()
        assert ("u1", "milk", 1.0) in r
        assert ("fallback_scope", "water", 2.0) in r
    finally:
        conn.close()


def test_t032_tc004_two_households_isolated_on_same_file() -> None:
    """TC-004：同一 DB 上不同 household_id 的 upsert 互不覆盖。"""
    path = _temp_db_path()
    m_a = InventoryManager(path, household_id="A")
    m_a.upsert("x", 1, "g")
    m_b = InventoryManager(path, household_id="B")
    m_b.upsert("x", 99, "kg")
    assert m_a.get_item("x") is not None
    assert m_a.get_item("x")["amount"] == 1
    assert m_b.get_item("x")["amount"] == 99
