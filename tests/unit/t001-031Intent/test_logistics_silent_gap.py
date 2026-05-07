"""T-002：静默缺口预计算（§1.3 步 5 / §7.1）单测，Inventory DB 以 mock 隔离。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.state import empty_agent_slices
from src.agent.state_sync import runtime_bundle_to_slice_patches

from src.agent.nodes.logistics import (
    _inventory_fingerprint,
    _stable_r_fingerprint,
    logistics_manager_node,
)


def test_stable_r_fingerprint_order_independent():
    a = [{"name": "b", "amount": 1, "unit": "g"}, {"name": "a", "amount": 2, "unit": "个"}]
    b = [{"name": "a", "amount": 2, "unit": "个"}, {"name": "b", "amount": 1, "unit": "g"}]
    assert _stable_r_fingerprint(a) == _stable_r_fingerprint(b)


def test_inventory_fingerprint_stable():
    inv = {"鸡蛋": {"amount": 3.0, "unit": "个"}, "牛奶": {"amount": 1, "unit": "L"}}
    assert _inventory_fingerprint(inv) == _inventory_fingerprint(inv)


@pytest.fixture
def patch_logistics_manager():
    """构造 MemoryInventory：缺口为鸡蛋 1 个。"""
    with patch("src.agent.nodes.logistics.LogisticsManager") as LM:
        inst = MagicMock()
        inst.get_inventory_snapshot.return_value = {"鸡蛋": {"amount": 1, "unit": "个"}}
        inst.calculate_shopping_gap.return_value = {
            "shopping_list": [{"name": "鸡蛋", "amount": 1, "unit": "个"}],
            "sufficient_items": [],
            "missing_items": [],
        }
        inst.update_inventory_after_cooking_report.return_value = ("success", [])
        LM.return_value = inst
        yield inst


def test_silent_precalc_writes_cached_gap_without_gap_calc_task(patch_logistics_manager):
    """researcher 高置信路径：task_stack 可无 TASK_GAP_CALC，仍写入缓存。"""
    lb = {
        "extracted_entities": {},
        "recipe_requirements": [{"name": "鸡蛋", "amount": 2, "unit": "个"}],
    }
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_SUMMARIZE"],
        "expert_payloads": {"recipe_detail": {"title": "测试菜谱"}},
    }
    out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    assert "cached_shopping_gap" in inv
    assert "gap_basis" in inv
    assert inv["gap_basis"]["recipe_title"] == "测试菜谱"
    assert len(inv["cached_shopping_gap"]["shopping_list"]) == 1
    patch_logistics_manager.calculate_shopping_gap.assert_called_once()


def test_silent_precalc_runs_after_inv_commit(patch_logistics_manager):
    """TASK_INV_COMMIT 扣减后仍执行静默预计算（文末统一拉取 I）。"""
    lb = {
        "extracted_entities": {},
        "recipe_requirements": [{"name": "五花肉", "amount": 500, "unit": "g"}],
        "recipe_use_confirmed": True,
    }
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_INV_COMMIT"],
        "expert_payloads": {},
    }
    out = logistics_manager_node(state)
    patch_logistics_manager.update_inventory_after_cooking_report.assert_called_once()
    patch_logistics_manager.get_inventory_snapshot.assert_called()
    assert "cached_shopping_gap" in (out.get("inventory_state") or {})
