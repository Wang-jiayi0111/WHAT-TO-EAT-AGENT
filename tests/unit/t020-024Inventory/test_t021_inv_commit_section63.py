"""
T-021 §6.3 扣减守卫：`TASK_INV_COMMIT`、`recipe_use_confirmed`、菜名锚点（FR-31）
============================================================================

**任务**：T-021  
**规格**：FR-31；**规格 §6.3**  
**开发记录**：`docs/dev_log.md` [DEV-025]

【测试计划】
-----------
=========  ==============================================================  ======
  编号      场景                                                           依据
=========  ==============================================================  ======
  TC-001    **R** 为空 → `commit_status=skipped`，不扣减                   §6.3
  TC-002    未确认且非采纳轮 → `blocked_no_confirm`，不调 `batch_deduct`     §6.3
  TC-003    `recipe_use_confirmed=True` → 扣减成功且清除确认标记             §6.3
  TC-004    当轮 `recipe_adopt` → 视同确认，允许扣减                         §6.3
  TC-005    锁定菜名与用户锚点菜名不一致 → `blocked_recipe_mismatch` + §9 码  §6.3
=========  ==============================================================  ======

过程与结论写入 **`docs/test_report.md`**（测试 Agent 维护）。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_sync import runtime_bundle_to_slice_patches
from src.agent.nodes.logistics import logistics_manager_node
from src.agent.nodes.logistics import LogisticsManager

from tests.conftest import make_logistics_buffer


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def _base_state(
    *,
    lb: dict,
    task_stack: list[str],
    slots: dict | None = None,
    intents: list[str] | None = None,
    primary_intent: str = "",
) -> dict:
    return {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": task_stack,
        "slots": dict(slots or {}),
        "intents": list(intents or []),
        "primary_intent": primary_intent,
        "expert_payloads": {},
        "messages": [],
    }


def test_t021_tc001_skipped_when_no_recipe_requirements() -> None:
    """TC-001：**R** 为空 → skipped。"""
    lb = make_logistics_buffer(
        recipe_requirements=[],
        recipe_use_confirmed=True,
    )
    state = _base_state(lb=lb, task_stack=["TASK_INV_COMMIT"])
    out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "skipped"


def test_t021_tc002_blocked_no_confirm_no_deduct() -> None:
    """TC-002：有 **R** 但未确认 → blocked_no_confirm；不写库。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t021")
    mgr.inventory_manager.upsert("鸡蛋", 10, "个")
    lb = make_logistics_buffer(
        recipe_requirements=[{"name": "鸡蛋", "amount": 2, "unit": "个"}],
        recipe_use_confirmed=False,
    )
    state = _base_state(lb=lb, task_stack=["TASK_INV_COMMIT"])
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "blocked_no_confirm"
    assert mgr.inventory_manager.get_item("鸡蛋")["amount"] == 10


def test_t021_tc003_success_clears_recipe_use_confirmed() -> None:
    """TC-003：会话已确认 → success；扣减后 `recipe_use_confirmed=False`。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t021")
    mgr.inventory_manager.upsert("鸡蛋", 10, "个")
    lb = make_logistics_buffer(
        recipe_requirements=[{"name": "鸡蛋", "amount": 2, "unit": "个"}],
        recipe_use_confirmed=True,
    )
    state = _base_state(lb=lb, task_stack=["TASK_INV_COMMIT"])
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "success"
    assert inv.get("recipe_use_confirmed") is False
    assert mgr.inventory_manager.get_item("鸡蛋")["amount"] == 8


def test_t021_tc004_recipe_adopt_this_turn_allows_commit() -> None:
    """TC-004：当轮采纳意图 → 无需上轮 `recipe_use_confirmed`。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t021")
    mgr.inventory_manager.upsert("五花肉", 500, "g")
    lb = make_logistics_buffer(
        recipe_requirements=[{"name": "五花肉", "amount": 100, "unit": "g"}],
        recipe_use_confirmed=False,
    )
    state = _base_state(
        lb=lb,
        task_stack=["TASK_INV_COMMIT"],
        intents=["recipe_adopt"],
        primary_intent="recipe_adopt",
    )
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "success"
    assert mgr.inventory_manager.get_item("五花肉")["amount"] == 400


def test_t021_tc005_blocked_recipe_mismatch_error_code() -> None:
    """TC-005：锁定菜名与槽位菜名不一致 → blocked + COMMIT_RECIPE_MISMATCH。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="t021")
    mgr.inventory_manager.upsert("牛肉", 200, "g")
    lb = make_logistics_buffer(
        recipe_title_locked="红烧牛肉",
        selected_recipe_title="红烧牛肉",
        recipe_requirements=[{"name": "牛肉", "amount": 50, "unit": "g"}],
        recipe_use_confirmed=True,
    )
    state = _base_state(
        lb=lb,
        task_stack=["TASK_INV_COMMIT"],
        slots={"recipe_name_for_commit": "糖醋排骨"},
    )
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert inv.get("commit_status") == "blocked_recipe_mismatch"
    err = out.get("error_state") or {}
    assert err.get("error_code") == "COMMIT_RECIPE_MISMATCH"
    assert mgr.inventory_manager.get_item("牛肉")["amount"] == 200
