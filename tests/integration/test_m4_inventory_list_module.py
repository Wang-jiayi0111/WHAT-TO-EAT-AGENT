"""
M4 库存与清单模块集成验收（板块七 / 八；T-020、T-021、T-022、T-023、T-024、T-032、T-033）

在既有单测（各 T-0xx 文件）之上串联：
**logistics_manager_node** 多分支、`inventory_state` 切片、**I** 字典型快照、
扣减后 DB 与再次 **TASK_INV_CHECK** 一致、**TASK_INV_CHECK** + **TASK_GAP_CALC** 同轮、
`materialize_runtime_bundle_from_slices` 与 **Generator** 库存/清单话术。

不重复单测中的逐条规格断言；此处侧重跨任务数据流与端到端一致性。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_accessors import get_runtime_bundle
from src.agent.core.state_sync import materialize_runtime_bundle_from_slices, runtime_bundle_to_slice_patches
from src.agent.nodes.logistics import (
    _inventory_fingerprint,
    _stable_r_fingerprint,
    logistics_manager_node,
    LogisticsManager,
)
from src.agent.nodes.generator import GeneratorNode
from tests.conftest import make_logistics_buffer


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def _base_state(
    lb: dict,
    *,
    task_stack: list[str],
    slots: dict | None = None,
) -> dict:
    return {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": task_stack,
        "slots": dict(slots or {}),
        "expert_payloads": {},
        "messages": [],
        "intents": [],
        "primary_intent": "",
    }


def test_m4_db_chain_commit_then_inv_check_snapshot_matches_db() -> None:
    """端到端：§6.3 扣减成功后，同一会话再 **TASK_INV_CHECK** → **I** 与 DB 一致。"""
    path = _temp_db_path()
    mgr = LogisticsManager(db_path=path, household_id="m4_chain")
    mgr.inventory_manager.upsert("鸡蛋", 10, "个")
    lb = make_logistics_buffer(
        recipe_requirements=[{"name": "鸡蛋", "amount": 2, "unit": "个"}],
        recipe_use_confirmed=True,
    )
    s1 = _base_state(lb, task_stack=["TASK_INV_COMMIT"])
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out1 = logistics_manager_node(s1)
    assert (out1.get("inventory_state") or {}).get("commit_status") == "success"

    s2 = {**out1, "task_stack": ["TASK_INV_CHECK"]}
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=mgr):
        out2 = logistics_manager_node(s2)

    snap = (out2.get("inventory_state") or {}).get("inventory_snapshot") or {}
    assert isinstance(snap, dict)
    assert snap.get("鸡蛋", {}).get("amount") == 8.0
    assert mgr.inventory_manager.get_item("鸡蛋")["amount"] == 8


def test_m4_combined_inv_check_and_gap_calc_triggers_silent_recalc() -> None:
    """同轮 **TASK_INV_CHECK** + **TASK_GAP_CALC**：文末静默缺口仍在；无 **R** 时不调 **GAP_CALC** 重算。"""
    req = [{"name": "牛奶", "amount": 1, "unit": "L"}]
    snap = {"牛奶": {"amount": 0.3, "unit": "L"}}
    stale_gb = {
        "recipe_title": "x",
        "r_fingerprint": "not_the_same",
        "inventory_fingerprint": _inventory_fingerprint(snap),
    }
    lb = make_logistics_buffer(
        recipe_requirements=req,
        gap_basis=stale_gb,
        cached_shopping_gap={
            "shopping_list": [],
            "sufficient_items": [],
            "missing_items": [],
        },
    )
    inst = MagicMock()
    inst.get_inventory_snapshot.return_value = snap
    inst.calculate_shopping_gap.return_value = {
        "shopping_list": [{"name": "牛奶", "amount": 0.7, "unit": "L"}],
        "sufficient_items": [],
        "missing_items": [],
    }
    state = _base_state(
        lb,
        task_stack=["TASK_INV_CHECK", "TASK_GAP_CALC"],
    )
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=inst):
        out = logistics_manager_node(state)

    inst.get_inventory_snapshot.assert_called()
    inst.calculate_shopping_gap.assert_called_once()
    inv = out.get("inventory_state") or {}
    assert inv.get("gap_delivery_mode") == "fresh"
    sl = inv.get("shopping_list") or []
    assert sl and sl[0].get("name") == "牛奶"


def test_m4_slice_roundtrip_overlay_preserved_in_bundle() -> None:
    """节点返回经 `materialize` → `get_runtime_bundle` 仍可读到 overlay / 待购行。"""
    req = [{"name": "胡椒", "amount": 5, "unit": "g"}]
    snap = {"胡椒": {"amount": 0, "unit": "g"}}
    gb = {
        "recipe_title": "t",
        "r_fingerprint": _stable_r_fingerprint(req),
        "inventory_fingerprint": _inventory_fingerprint(snap),
    }
    cache = {
        "shopping_list": [{"name": "胡椒", "amount": 5, "unit": "g"}],
        "sufficient_items": [],
        "missing_items": [],
        "pending_manual": [],
        "computed_at": "x",
    }
    lb = make_logistics_buffer(
        recipe_requirements=req,
        gap_basis=gb,
        cached_shopping_gap=cache,
        shopping_list_overlay=[{"op": "adjust_note", "key": "胡椒", "note": "现磨"}],
    )
    state = _base_state(lb, task_stack=[])
    inst = MagicMock()
    inst.get_inventory_snapshot.return_value = snap
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=inst):
        out = logistics_manager_node(state)

    flat = materialize_runtime_bundle_from_slices(out)
    assert flat.get("shopping_list_overlay")
    rb = get_runtime_bundle(out)
    assert rb.get("shopping_list_overlay")
    assert any("现磨" in str(x.get("note", "")) for x in (rb.get("shopping_list") or []))


def test_m4_generator_inventory_gap_and_commit_handles_smoke() -> None:
    """Generator：库存陈述、缺口陈述、扣减陈述可渲染（与 logistics 切片对齐）。"""
    gen = GeneratorNode()
    lb_empty = make_logistics_buffer(inventory_snapshot={})
    st_empty = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_empty),
    }
    t_inv_empty = gen.handle_inv_check(st_empty)
    assert "空" in t_inv_empty or "没有" in t_inv_empty

    lb_gap = make_logistics_buffer(
        gap_delivery_mode="fresh",
        shopping_list=[{"name": "姜", "amount": 20, "unit": "g"}],
        sufficient_items=[],
    )
    st_gap = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_gap),
        "error_state": {},
    }
    t_gap = gen.handle_gap_calc(st_gap)
    assert "姜" in t_gap or "购买" in t_gap

    lb_commit = make_logistics_buffer(commit_status="success")
    st_commit = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_commit),
    }
    t_commit = gen.handle_inv_commit(st_commit)
    assert "扣减" in t_commit or "库存" in t_commit


@pytest.mark.parametrize(
    "task_stack",
    [
        [],
        ["TASK_INV_CHECK"],
        ["TASK_GAP_CALC"],
        ["TASK_INV_COMMIT"],
    ],
)
def test_m4_inventory_snapshot_always_dict_after_node(task_stack: list[str]) -> None:
    """任一分支结束后，`inventory_state.inventory_snapshot` 经规范化应为 **dict**（§1.2.1）。"""
    lb = make_logistics_buffer(recipe_requirements=[])
    state = _base_state(lb, task_stack=task_stack)
    snap = {"小米": {"amount": 1.0, "unit": "杯"}}
    inst = MagicMock()
    inst.get_inventory_snapshot.return_value = snap
    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=inst):
        out = logistics_manager_node(state)
    inv = out.get("inventory_state") or {}
    got = inv.get("inventory_snapshot")
    assert isinstance(got, dict)
