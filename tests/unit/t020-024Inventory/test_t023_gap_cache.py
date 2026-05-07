"""
T-023 购物缺口缓存与显式交付（FR-40～42 / §7.1～§7.3）
====================================================

**任务**：T-023  
**规格**：FR-40～FR-42；§7.1～§7.3；§9 `GAP_CACHE_MISS`  
**开发记录**：`docs/dev_log.md` [DEV-028]

验收结论写入 **`docs/test_report.md`** [TR-035]。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.state import empty_agent_slices
from src.agent.state_sync import runtime_bundle_to_slice_patches
from src.agent.nodes.logistics import (
    _gap_cache_valid,
    _inventory_fingerprint,
    _merge_shopping_gap_overlay,
    _stable_r_fingerprint,
    logistics_manager_node,
)
from src.agent.nodes.generator import GeneratorNode

from tests.conftest import make_logistics_buffer


def test_t023_gap_cache_valid_requires_matching_fingerprints() -> None:
    """§7.3：R/I 指纹与 gap_basis 一致且缓存含 shopping_list → True。"""
    req = [{"name": "鸡蛋", "amount": 2, "unit": "个"}]
    snap = {"鸡蛋": {"amount": 1, "unit": "个"}}
    lb = {
        "recipe_requirements": req,
        "gap_basis": {
            "recipe_title": "蛋炒饭",
            "r_fingerprint": _stable_r_fingerprint(req),
            "inventory_fingerprint": _inventory_fingerprint(snap),
        },
        "cached_shopping_gap": {
            "shopping_list": [{"name": "鸡蛋", "amount": 1, "unit": "个"}],
            "sufficient_items": [],
            "missing_items": [],
            "pending_manual": [],
            "computed_at": "2026-01-01T00:00:00Z",
        },
    }
    assert _gap_cache_valid(lb, snap) is True
    bad = dict(lb)
    bad["gap_basis"] = {**lb["gap_basis"], "r_fingerprint": "deadbeef"}
    assert _gap_cache_valid(bad, snap) is False


def test_t023_silent_precalc_skips_recalc_when_cache_hits() -> None:
    """§7.3：指纹命中时不调用 calculate_shopping_gap；gap_delivery_mode=cache。"""
    req = [{"name": "牛奶", "amount": 1, "unit": "L"}]
    snap = {"牛奶": {"amount": 0.5, "unit": "L"}}
    gb = {
        "recipe_title": "奶昔",
        "r_fingerprint": _stable_r_fingerprint(req),
        "inventory_fingerprint": _inventory_fingerprint(snap),
    }
    cache = {
        "shopping_list": [{"name": "牛奶", "amount": 0.5, "unit": "L"}],
        "sufficient_items": [],
        "missing_items": [],
        "pending_manual": [],
        "computed_at": "x",
    }
    lb = make_logistics_buffer(recipe_requirements=req, gap_basis=gb, cached_shopping_gap=cache)
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": [],
        "expert_payloads": {},
        "slots": {},
        "messages": [],
        "intents": [],
        "primary_intent": "",
    }
    inst = MagicMock()
    inst.get_inventory_snapshot.return_value = snap
    inst.calculate_shopping_gap.return_value = {
        "shopping_list": [{"name": "不应调用", "amount": 99, "unit": "L"}],
        "sufficient_items": [],
        "missing_items": [],
    }

    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=inst):
        out = logistics_manager_node(state)

    inst.calculate_shopping_gap.assert_not_called()
    inv = out.get("inventory_state") or {}
    assert inv.get("gap_delivery_mode") == "cache"
    assert inv.get("cached_shopping_gap", {}).get("shopping_list") == cache["shopping_list"]


def test_t023_silent_precalc_fresh_when_basis_stale() -> None:
    """指纹不一致 → 全量 §7.2；gap_delivery_mode=fresh。"""
    req = [{"name": "糖", "amount": 100, "unit": "g"}]
    snap = {"糖": {"amount": 50, "unit": "g"}}
    stale_gb = {
        "recipe_title": "甜",
        "r_fingerprint": "not_matching_r_fp",
        "inventory_fingerprint": _inventory_fingerprint(snap),
    }
    lb = make_logistics_buffer(
        recipe_requirements=req,
        gap_basis=stale_gb,
        cached_shopping_gap={"shopping_list": [], "sufficient_items": [], "missing_items": []},
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": [],
        "expert_payloads": {},
        "slots": {},
        "messages": [],
        "intents": [],
        "primary_intent": "",
    }
    inst = MagicMock()
    inst.get_inventory_snapshot.return_value = snap
    inst.calculate_shopping_gap.return_value = {
        "shopping_list": [{"name": "糖", "amount": 50, "unit": "g"}],
        "sufficient_items": [],
        "missing_items": [],
    }

    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=inst):
        out = logistics_manager_node(state)

    inst.calculate_shopping_gap.assert_called_once()
    inv = out.get("inventory_state") or {}
    assert inv.get("gap_delivery_mode") == "fresh"


def test_t023_task_gap_calc_no_r_gap_cache_miss() -> None:
    """TASK_GAP_CALC 且无 **R** → GAP_CACHE_MISS + gap_delivery_mode=empty。"""
    lb = make_logistics_buffer(recipe_requirements=[])
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_GAP_CALC"],
        "expert_payloads": {},
        "slots": {},
        "messages": [],
        "intents": [],
        "primary_intent": "",
    }
    with patch("src.agent.nodes.logistics.LogisticsManager") as LM:
        inst = MagicMock()
        inst.get_inventory_snapshot.return_value = {}
        LM.return_value = inst
        out = logistics_manager_node(state)

    err = out.get("error_state") or {}
    assert err.get("error_code") == "GAP_CACHE_MISS"
    inv = out.get("inventory_state") or {}
    assert inv.get("gap_delivery_mode") == "empty"


def test_t023_generator_gap_cache_and_miss() -> None:
    """generator：cache 话术 vs 无 R 话术。"""
    gen = GeneratorNode()
    lb_cache = make_logistics_buffer(
        gap_delivery_mode="cache",
        shopping_list=[{"name": "盐", "amount": 1, "unit": "袋"}],
        sufficient_items=[],
    )
    st_c = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_cache),
        "error_state": {},
    }
    t_c = gen.handle_gap_calc(st_c)
    assert "缓存" in t_c or "一致" in t_c

    lb_miss = make_logistics_buffer(gap_delivery_mode="empty")
    st_m = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_miss),
        "error_state": {"error_code": "GAP_CACHE_MISS"},
    }
    t_m = gen.handle_gap_calc(st_m)
    assert "用料清单" in t_m or "**R**" in t_m


def test_t023_merge_overlay_remove() -> None:
    """§7.4：overlay remove 从待购行中剔除。"""
    cached = {
        "shopping_list": [{"name": "葱", "amount": 1, "unit": "把"}],
        "sufficient_items": [],
        "pending_manual": [],
    }
    rows, _ = _merge_shopping_gap_overlay(cached, [{"op": "remove", "key": "葱"}])
    assert rows == []
