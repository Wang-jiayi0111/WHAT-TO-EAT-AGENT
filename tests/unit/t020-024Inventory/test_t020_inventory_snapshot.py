"""
T-020 库存快照 **I** 与 `inventory_state.inventory_snapshot`（FR-30）
====================================================================

**任务**：T-020  
**规格**：FR-30；§6.1（**I**）；§1.2.1（`inventory_snapshot` 字典型）  
**开发记录**：`docs/dev_log.md` [DEV-023]

【测试计划】
-----------
**目标**：`get_inventory_snapshot_i` / `LogisticsManager.get_inventory_snapshot` 返回
``Dict[str, {"amount": float, "unit": str}]``；`state_sync._normalize_inventory_snapshot`
规范化 dict 与 legacy list；`logistics_manager_node` 结束时将当前 **I** 写入切片
`inventory_state.inventory_snapshot`。

=========  ======================================================  ==========
  编号      场景                                                  依据
=========  ======================================================  ==========
  TC-001    `get_inventory_snapshot_i` 类型与 household 读取      §6.1
  TC-002    `_normalize_inventory_snapshot` dict / list / 其它    §1.2.1
  TC-003    无 **R** 时节点仍写入最终 **I** 至 `inventory_state`    DEV-023
  TC-004    `TASK_INV_COMMIT` 扣减后文末快照与 DB 一致             FR-30
=========  ======================================================  ==========

**禁止行为**：库存键不为 `thread_id`；任务队列为 `task_stack`。

执行与每轮统计见 **`docs/test_report.md`** [TR-028]。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_sync import _normalize_inventory_snapshot, runtime_bundle_to_slice_patches
from src.agent.nodes.logistics import LogisticsManager, logistics_manager_node
from src.libs.base.inventory import InventoryManager
from tests.conftest import make_logistics_buffer


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def test_t020_tc001_get_inventory_snapshot_i_shape() -> None:
    """TC-001：**I** 为 float amount、str unit；与 `get_all` 同作用域一致。"""
    path = _temp_db_path()
    inv = InventoryManager(path, household_id="hh_t020")
    inv.upsert("五花肉", 500, "g")
    snap = inv.get_inventory_snapshot_i()
    assert snap == {"五花肉": {"amount": 500.0, "unit": "g"}}
    assert isinstance(snap["五花肉"]["amount"], float)
    assert isinstance(snap["五花肉"]["unit"], str)


def test_t020_tc002_normalize_inventory_snapshot() -> None:
    """TC-002：dict 逐项规范化；list  legacy；非法根类型 → 空 dict。"""
    d = _normalize_inventory_snapshot(
        {"  糖  ": {"amount": "12.5", "unit": None}, "bad": "x", "": {"amount": 1, "unit": "g"}}
    )
    assert d == {"糖": {"amount": 12.5, "unit": ""}}
    lst = _normalize_inventory_snapshot(
        [{"name": "奶", "amount": 1, "unit": "L"}, {"name": "", "amount": 9, "unit": "g"}]
    )
    assert lst == {"奶": {"amount": 1.0, "unit": "L"}}
    assert _normalize_inventory_snapshot(None) == {}
    assert _normalize_inventory_snapshot("nope") == {}


def test_t020_tc003_logistics_node_writes_final_i_without_recipe_requirements() -> None:
    """TC-003：无 **R** 时不跑静默缺口，但文末仍写入 `inventory_state.inventory_snapshot`。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="scope_final")
    mgr.inventory_manager.upsert("盐", 1, "勺")

    lb = make_logistics_buffer(recipe_requirements=[])
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": [],
        "expert_payloads": {},
    }
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)

    inv = out.get("inventory_state") or {}
    snap = inv.get("inventory_snapshot") or {}
    assert snap == {"盐": {"amount": 1.0, "unit": "勺"}}
    assert isinstance(snap["盐"]["amount"], float)


def test_t020_tc004_inv_commit_then_snapshot_reflects_deduction() -> None:
    """TC-004：扣减后文末快照为 DB 当前 **I**。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="h_commit")
    mgr.inventory_manager.upsert("五花肉", 500, "g")

    lb = make_logistics_buffer(
        recipe_requirements=[{"name": "五花肉", "amount": 200, "unit": "g"}],
        recipe_use_confirmed=True,
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_INV_COMMIT"],
        "expert_payloads": {},
    }
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)

    inv = out.get("inventory_state") or {}
    snap = inv.get("inventory_snapshot") or {}
    assert snap.get("五花肉") == {"amount": 300.0, "unit": "g"}
    assert inv.get("commit_status") == "success"
