"""
T-024 购物清单 overlay 与 `list_action`（FR-41/43 / §7.4、§11.2）
================================================================

**任务**：T-024  
**规格**：FR-41、FR-43；§7.3～§7.4；§11.2  
**开发记录**：`docs/dev_log.md` [DEV-029]

验收结论写入 **`docs/test_report.md`** [TR-036]。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.state import empty_agent_slices
from src.agent.state_sync import runtime_bundle_to_slice_patches
from src.agent.nodes.logistics import (
    _apply_list_action_to_overlay_updates,
    _coerce_list_edit_ops,
    _inventory_fingerprint,
    _merge_shopping_gap_overlay,
    _stable_r_fingerprint,
    logistics_manager_node,
)
from src.agent.nodes.generator import GeneratorNode

from tests.conftest import make_logistics_buffer


def test_t024_merge_base_order_pending_manual_then_shopping_list() -> None:
    """§7.3：底表 = `pending_manual` 行在前，再接 `shopping_list`。"""
    cached = {
        "pending_manual": ["香菜"],
        "shopping_list": [{"name": "鸡蛋", "amount": 2, "unit": "个"}],
        "sufficient_items": [{"name": "盐", "amount": 1, "unit": "袋"}],
    }
    rows, suff = _merge_shopping_gap_overlay(cached, [])
    assert rows[0].get("name") == "香菜"
    assert rows[0].get("pending_manual") is True
    assert rows[1].get("name") == "鸡蛋"
    assert len(suff) == 1 and suff[0].get("name") == "盐"


def test_t024_merge_overlay_adjust_note_then_add() -> None:
    """overlay 顺序：先改备注再追加行。"""
    cached = {
        "shopping_list": [{"name": "酱油", "amount": 1, "unit": "瓶"}],
        "pending_manual": [],
        "sufficient_items": [],
    }
    overlay = [
        {"op": "adjust_note", "key": "酱油", "note": "买生抽"},
        {"action": "add", "display": "米醋", "amount": 1, "unit": "瓶"},
    ]
    rows, _ = _merge_shopping_gap_overlay(cached, overlay)
    assert len(rows) == 2
    assert rows[0].get("note") == "买生抽"
    assert rows[1].get("name") == "米醋"


def test_t024_apply_refresh_gap_clears_overlay_and_invalidates_basis() -> None:
    """§7.4：`refresh_gap` 清空 overlay 并置空 `gap_basis`。"""
    lb = {
        "shopping_list_overlay": [{"op": "remove", "key": "葱"}],
        "gap_basis": {"r_fingerprint": "x", "inventory_fingerprint": "y"},
    }
    updates: dict = {}
    _apply_list_action_to_overlay_updates(
        lb,
        updates,
        {"list_action": "refresh_gap"},
    )
    assert updates.get("shopping_list_overlay") == []
    assert updates.get("gap_basis") == {}


def test_t024_apply_mark_bought_appends_remove() -> None:
    """`mark_bought` + `mark_bought_items` → 在既有 overlay 后追加 remove。"""
    lb = {"shopping_list_overlay": [{"op": "add", "display": "预备项", "amount": 0, "unit": "项"}]}
    updates: dict = {}
    _apply_list_action_to_overlay_updates(
        lb,
        updates,
        {
            "list_action": "mark_bought",
            "mark_bought_items": ["鸡蛋", "牛奶"],
        },
    )
    ov = updates.get("shopping_list_overlay") or []
    assert ov[0]["op"] == "add"
    assert ov[-2:] == [
        {"op": "remove", "key": "鸡蛋"},
        {"op": "remove", "key": "牛奶"},
    ]


def test_t024_apply_edit_overlay_list_edit_ops() -> None:
    """`edit_overlay` + `list_edit_ops` 合并进 overlay。"""
    lb: dict = {}
    updates: dict = {}
    _apply_list_action_to_overlay_updates(
        lb,
        updates,
        {
            "list_action": "edit_overlay",
            "list_edit_ops": [
                {"type": "remove", "ingredient": " 盐 "},
                {"action": "adjust_note", "name": "糖", "note": "少买"},
            ],
        },
    )
    ov = updates.get("shopping_list_overlay") or []
    assert ov[0] == {"op": "remove", "key": "盐"}
    assert ov[1]["op"] == "adjust_note" and ov[1]["key"] == "糖"


def test_t024_coerce_list_edit_ops_add_display_alias() -> None:
    """`_coerce_list_edit_ops` 接受 `display` / `text` 等别名。"""
    raw = [{"op": "add", "text": " 生姜 ", "amount": 100, "unit": "g"}]
    out = _coerce_list_edit_ops(raw)
    assert len(out) == 1
    assert out[0]["op"] == "add"
    assert out[0]["display"] == "生姜"
    assert out[0]["amount"] == 100.0


def test_t024_logistics_mark_bought_merges_remove_into_display() -> None:
    """端到端：缓存命中 + `mark_bought` → 展示行划掉待购项。"""
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
    lb = make_logistics_buffer(
        recipe_requirements=req,
        gap_basis=gb,
        cached_shopping_gap=cache,
        shopping_list_overlay=[],
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": [],
        "expert_payloads": {},
        "slots": {"list_action": "mark_bought", "mark_bought_items": ["牛奶"]},
        "messages": [],
        "intents": [],
        "primary_intent": "",
    }
    inst = MagicMock()
    inst.get_inventory_snapshot.return_value = snap
    inst.calculate_shopping_gap.return_value = {
        "shopping_list": [{"name": "不应展示", "amount": 99, "unit": "L"}],
        "sufficient_items": [],
        "missing_items": [],
    }

    with patch("src.agent.nodes.logistics.LogisticsManager", return_value=inst):
        out = logistics_manager_node(state)

    inst.calculate_shopping_gap.assert_not_called()
    inv = out.get("inventory_state") or {}
    assert inv.get("gap_delivery_mode") == "cache"
    ov = inv.get("shopping_list_overlay") or []
    assert any(
        o.get("op") == "remove" and str(o.get("key", "")).strip() == "牛奶" for o in ov
    )
    sl = inv.get("shopping_list") or []
    assert not any(str(it.get("name", "")).strip() == "牛奶" for it in sl)


def test_t024_generator_overlay_manual_adjust_hint() -> None:
    """§7.4：overlay 非空时 `handle_gap_calc` 提示含手动调整。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(
        gap_delivery_mode="fresh",
        shopping_list=[{"name": "胡椒", "amount": 5, "unit": "g"}],
        sufficient_items=[],
        shopping_list_overlay=[{"op": "adjust_note", "key": "胡椒", "note": "现磨"}],
    )
    st = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "error_state": {},
    }
    text = gen.handle_gap_calc(st)
    assert "手动调整" in text
