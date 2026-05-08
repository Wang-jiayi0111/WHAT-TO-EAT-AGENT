"""
T-022 库存写失败显式反馈（FR-32 / §6.4、§6.5.5）
==============================================

**任务**：T-022  
**规格**：FR-32；§6.4；§6.5.5～6.5.6  
**开发记录**：`docs/dev_log.md` [DEV-027]

【测试计划】
-----------
- TC-001：`InventoryManager.batch_deduct_report` 部分行失败 → `partial_success` + 失败名单  
- TC-002：`TASK_INV_COMMIT` + 报表 `partial_success` → `commit_*_items`、`INVENTORY_WRITE_FAILED`、**不清除** `recipe_use_confirmed`  
- TC-003：`TASK_INV_COMMIT` + `failed` → `error_state` 与失败名单  
- TC-004：`GeneratorNode.handle_inv_commit` / `handle_inv_add` 话术含「未全部」/ 错误码语义（禁止笼统成功）  
- TC-005：`TASK_INV_ADD` 确认分支 `partial_success` → `add_succeeded_items` / `add_failed_items`

验收记录见 **`docs/test_report.md`** [TR-034]。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from src.agent.state import empty_agent_slices
from src.agent.state_sync import runtime_bundle_to_slice_patches
from src.agent.nodes.logistics import logistics_manager_node
from src.agent.nodes.logistics import LogisticsManager
from src.agent.nodes.generator import GeneratorNode
from src.libs.base.inventory import InventoryManager

from tests.conftest import make_logistics_buffer


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def test_t022_tc001_batch_deduct_report_partial() -> None:
    """TC-001：逐条报表，一条非法数值 → partial_success。"""
    path = _temp_db_path()
    inv = InventoryManager(path, household_id="h")
    inv.upsert("黄瓜", 100, "g")
    st, failed = inv.batch_deduct_report(
        [
            {"name": "番茄", "amount": "x", "unit": "g"},
            {"name": "黄瓜", "amount": 10, "unit": "g"},
        ]
    )
    assert st == "partial_success"
    assert "番茄" in failed
    assert inv.get_item("黄瓜")["amount"] == 90.0


def _commit_state(*, lb: dict, task_stack: list[str]) -> dict:
    return {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": task_stack,
        "slots": {},
        "intents": [],
        "primary_intent": "",
        "expert_payloads": {},
        "messages": [],
    }


def test_t022_tc002_logistics_commit_partial_lists_and_error_state() -> None:
    """TC-002：扣减 partial → 成功/失败名单 + §9 码；不清理 recipe_use_confirmed。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="h")
    lb = make_logistics_buffer(
        recipe_requirements=[
            {"name": "洋葱", "amount": 1, "unit": "个"},
            {"name": "土豆", "amount": 2, "unit": "个"},
        ],
        recipe_use_confirmed=True,
    )
    state = _commit_state(lb=lb, task_stack=["TASK_INV_COMMIT"])

    def fake_report(*_args):
        return "partial_success", ["洋葱"]

    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        with patch.object(
            LogisticsManager,
            "update_inventory_after_cooking_report",
            side_effect=fake_report,
        ):
            out = logistics_manager_node(state)

    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "partial_success"
    assert inv.get("commit_failed_items") == ["洋葱"]
    assert inv.get("commit_succeeded_items") == ["土豆"]
    assert inv.get("recipe_use_confirmed") is True
    err = out.get("error_state") or {}
    assert err.get("error_code") == "INVENTORY_WRITE_FAILED"
    assert "洋葱" in str(err.get("error_detail") or "")


def test_t022_tc003_logistics_commit_failed_all() -> None:
    """TC-003：扣减全失败 → failed + INVENTORY_WRITE_FAILED。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="h")
    lb = make_logistics_buffer(
        recipe_requirements=[{"name": "牛肉", "amount": 1, "unit": "kg"}],
        recipe_use_confirmed=True,
    )
    state = _commit_state(lb=lb, task_stack=["TASK_INV_COMMIT"])

    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        with patch.object(
            LogisticsManager,
            "update_inventory_after_cooking_report",
            return_value=("failed", ["牛肉"]),
        ):
            out = logistics_manager_node(state)

    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "failed"
    assert inv.get("commit_failed_items") == ["牛肉"]
    err = out.get("error_state") or {}
    assert err.get("error_code") == "INVENTORY_WRITE_FAILED"


def test_t022_tc004_generator_commit_and_add_no_false_success_wording() -> None:
    """TC-004：话术不得笼统宣称已全部成功。"""
    gen = GeneratorNode()
    lb_commit = make_logistics_buffer(
        commit_status="partial_success",
        commit_succeeded_items=["土豆"],
        commit_failed_items=["洋葱"],
    )
    state_c = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_commit),
        "error_state": {
            "error_code": "INVENTORY_WRITE_FAILED",
            "recoverable": True,
            "error_detail": "部分",
        },
    }
    text_c = gen.handle_inv_commit(state_c)
    assert "未能全部写入" in text_c or "未能全部" in text_c
    assert "洋葱" in text_c

    lb_add = make_logistics_buffer(
        add_status="partial_success",
        add_succeeded_items=["米"],
        add_failed_items=["油"],
    )
    state_a = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_add),
        "error_state": {
            "error_code": "INVENTORY_WRITE_FAILED",
            "recoverable": True,
            "error_detail": "部分食材补货",
        },
    }
    text_a = gen.handle_inv_add(state_a)
    assert "未全部写入" in text_a or "未能写入" in text_a
    assert "油" in text_a

    lb_fail = make_logistics_buffer(add_status="failed")
    state_f = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_fail),
        "error_state": {
            "error_code": "INVENTORY_WRITE_FAILED",
            "recoverable": True,
            "error_detail": "测试详情",
        },
    }
    text_f = gen.handle_inv_add(state_f)
    assert (
        "补货入库" in text_f
        or "数据库" in text_f
        or "未能成功" in text_f
    )


def test_t022_tc005_logistics_add_confirm_partial_success_lists() -> None:
    """TC-005：确认写库 partial_success → add_succeeded_items / add_failed_items。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="h")
    preview = {
        "items": [
            {"name": "糖", "delta_or_value": 1.0, "unit": "袋", "merge_mode": "add"},
            {"name": "醋", "delta_or_value": 1.0, "unit": "瓶", "merge_mode": "add"},
        ],
        "unresolved": [],
        "source": "utterance",
    }
    lb = make_logistics_buffer(
        add_preview=preview,
        add_status="pending",
        recipe_requirements=[],
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_INV_ADD"],
        "slots": {"restock_confirm": True},
        "intents": [],
        "primary_intent": "",
        "expert_payloads": {},
        "messages": [],
    }

    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        with patch(
            "src.agent.nodes.logistics._apply_restock_items",
            return_value=("partial_success", ["醋"]),
        ):
            out = logistics_manager_node(state)

    inv = out.get("inventory_state") or {}
    assert inv.get("add_status") == "partial_success"
    assert "糖" in (inv.get("add_succeeded_items") or [])
    assert "醋" in (inv.get("add_failed_items") or [])
    err = out.get("error_state") or {}
    assert err.get("error_code") == "INVENTORY_WRITE_FAILED"
