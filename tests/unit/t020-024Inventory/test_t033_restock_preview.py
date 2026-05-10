"""
T-033 补货预览 / 确认 / §6.5（`add_preview`、`add_status`、`INVENTORY_ADD_UNPARSED`）
===========================================================================

**任务**：T-033  
**规格**：§6.5、§7.5（名称规范化）、§9（`INVENTORY_ADD_UNPARSED`、`INVENTORY_WRITE_FAILED`）  
**开发记录**：`docs/dev_log.md` [DEV-024]

【测试计划】
-----------
=========  ================================================================  ======
  编号      场景                                                                依据
=========  ================================================================  ======
  TC-001    `_build_add_preview_from_restock_rows` 合法行 → items             §6.5.3
  TC-002    无法解析任何行 → `INVENTORY_ADD_UNPARSED`                           §9
  TC-003    部分 unresolved → `pending`，不写库                               §6.5.3
  TC-004    `confirm_required=True` → `pending` + 保留 preview                §6.5.3
  TC-005    `confirm_required=False` 且单条合法 → 自动写库                     §6.5.3
  TC-006    先 pending → `restock_confirm` 后写库                             §6.5.3
  TC-007    `apply_restock`：`add` 累加 / `set` 覆盖                           §6.5.2
  TC-008    `router` 待确认短句 → 规则路由                                   §6.5.3
=========  ================================================================  ======

执行记录见 **`docs/test_report.md`** [TR-029]。
"""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_sync import runtime_bundle_to_slice_patches
from src.libs.base.inventory import InventoryManager
from src.libs.base.settings import Settings
from src.agent.nodes.logistics import (
    LogisticsManager,
    _build_add_preview_from_restock_rows,
    logistics_manager_node,
)
from src.agent.nodes.router import _restock_pending_confirm_shortcut
from tests.conftest import make_logistics_buffer


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def _make_inv_add_state(
    *,
    task_stack: list[str],
    slots: dict | None = None,
    inventory_patch: dict | None = None,
    messages: list | None = None,
) -> dict:
    lb = make_logistics_buffer(recipe_requirements=[])
    base = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": task_stack,
        "slots": slots or {},
        "messages": messages or [],
        "expert_payloads": {},
        "intents": [],
        "primary_intent": "",
    }
    if inventory_patch:
        inv = dict(base.get("inventory_state") or {})
        inv.update(inventory_patch)
        base["inventory_state"] = inv
    return base


def test_t033_tc001_build_preview_valid_row() -> None:
    """TC-001：合法 restock 行 → preview.items 含 normalize 后名称与 merge_mode。"""
    prev = _build_add_preview_from_restock_rows(
        [{"name": " 牛奶 ", "amount": 1, "unit": "L", "merge_mode": "set"}],
        "随便买点",
    )
    assert prev["source"] == "utterance"
    assert not prev["unresolved"]
    assert len(prev["items"]) == 1
    it = prev["items"][0]
    assert it["name"] == "牛奶"
    assert it["delta_or_value"] == 1.0
    assert it["unit"] == "L"
    assert it["merge_mode"] == "set"


def test_t033_tc002_unparsed_only_inventory_add_unparsed() -> None:
    """TC-002：仅含糊行 → items 空且 unresolved 非空 → `add_status=failed`（§9 `INVENTORY_ADD_UNPARSED` 语义）。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t033")
    state = _make_inv_add_state(
        task_stack=["TASK_INV_ADD"],
        slots={"restock_items": [{"name": "鸡蛋"}]},
    )
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("add_status") == "failed"
    preview = inv.get("add_preview") or {}
    assert not preview.get("items") and preview.get("unresolved")
    err = out.get("error_state") or {}
    assert err.get("error_code") == "INVENTORY_ADD_UNPARSED"
    assert err.get("recoverable") is True


def test_t033_tc003_partial_unresolved_pending() -> None:
    """TC-003：一行合法 + 一行缺单位 → pending，有 items 也有 unresolved。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t033")
    rows = [
        {"name": "糖", "amount": 100, "unit": "g"},
        {"name": "盐", "amount": 1},
    ]
    state = _make_inv_add_state(
        task_stack=["TASK_INV_ADD"],
        slots={"restock_items": rows},
    )
    with patch.object(
        Settings, "get_inventory_restock_confirm_required", return_value=True
    ):
        with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
            out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("add_status") == "pending"
    preview = inv.get("add_preview") or {}
    assert preview.get("items")
    assert preview.get("unresolved")


def test_t033_tc004_confirm_required_pending_no_write() -> None:
    """TC-004：单条完全可解析 + confirm_required → pending，DB 仍空。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t033")
    state = _make_inv_add_state(
        task_stack=["TASK_INV_ADD"],
        slots={
            "restock_items": [{"name": "面粉", "amount": 1, "unit": "kg"}]
        },
    )
    with patch.object(
        Settings, "get_inventory_restock_confirm_required", return_value=True
    ):
        with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
            out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("add_status") == "pending"
    assert inv.get("add_preview") is not None
    assert mgr.inventory_manager.get_all() == {}


def test_t033_tc005_auto_commit_single_when_confirm_off() -> None:
    """TC-005：confirm_required=False + 单条 → 直接 success，库存写入。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t033")
    state = _make_inv_add_state(
        task_stack=["TASK_INV_ADD"],
        slots={
            "restock_items": [{"name": "大米", "amount": 5, "unit": "kg"}]
        },
    )
    with patch.object(
        Settings, "get_inventory_restock_confirm_required", return_value=False
    ):
        with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
            out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("add_status") == "success"
    assert inv.get("add_preview") is None
    snap = mgr.inventory_manager.get_inventory_snapshot_i()
    assert snap.get("大米") == {"amount": 5.0, "unit": "kg"}


def test_t033_tc006_two_step_confirm_writes() -> None:
    """TC-006：第一轮 pending → 第二轮 restock_confirm → 写入。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t033")
    preview = {
        "items": [
            {
                "name": "酱油",
                "delta_or_value": 1.0,
                "unit": "瓶",
                "merge_mode": "add",
            }
        ],
        "unresolved": [],
        "source": "utterance",
    }
    state2 = _make_inv_add_state(
        task_stack=["TASK_INV_ADD"],
        slots={"restock_confirm": True},
        inventory_patch={
            "add_preview": preview,
            "add_status": "pending",
        },
    )
    with patch.object(
        Settings, "get_inventory_restock_confirm_required", return_value=True
    ):
        with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
            out = logistics_manager_node(state2)
    inv = out.get("inventory_state") or {}
    assert inv.get("add_status") == "success"
    assert inv.get("add_preview") is None
    assert mgr.inventory_manager.get_item("酱油") == {"amount": 1.0, "unit": "瓶"}


def test_t033_tc007_apply_restock_add_vs_set() -> None:
    """TC-007：`apply_restock` add 累加，set 覆盖。"""
    path = _temp_db_path()
    inv = InventoryManager(path, household_id="h")
    inv.upsert("葱", 10, "g")
    assert inv.apply_restock("葱", 5, "g", "add")
    assert inv.get_item("葱")["amount"] == 15.0
    assert inv.apply_restock("葱", 3, "g", "set")
    assert inv.get_item("葱")["amount"] == 3.0


def test_t033_tc008_router_pending_confirm_shortcut() -> None:
    """TC-008：pending + 无 unresolved + 用户「确认」→ 规则补丁含 TASK_INV_ADD。"""
    state = {
        "task_stack": [],
        "inventory_state": {
            "add_status": "pending",
            "add_preview": {
                "items": [{"name": "蒜", "delta_or_value": 2, "unit": "头"}],
                "unresolved": [],
            },
        },
        "messages": [SimpleNamespace(content="确认")],
    }
    patch_dict = _restock_pending_confirm_shortcut(state)
    assert patch_dict is not None
    assert patch_dict.get("task_stack") == ["TASK_INV_ADD"]
    assert patch_dict.get("slots", {}).get("restock_confirm") is True
