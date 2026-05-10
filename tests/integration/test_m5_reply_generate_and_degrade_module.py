"""
M5「回复与降级」模块集成验收（里程碑 M5 / 板块十）

在 **T-025（§9 / FR-60）**、**T-026（FR-61）** 单测之上，串联：
**GeneratorNode** 真实处理器合并（库存 + 缺口）、**TASK_CLARIFY** 可读输出，以及与既有 **T-006（元意图）**、**T-008（FR-52 合并）** 单测互补的数据流检查。

不重复 `test_t025_*` / `test_t026_*` / `test_generator_merged_replies` 的逐条断言。
"""

from __future__ import annotations

import pytest

from langchain_core.messages import HumanMessage

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_sync import runtime_bundle_to_slice_patches
from src.agent.nodes.generator import (
    GeneratorNode,
    HELP_REPLY_TEXT,
    OUT_OF_SCOPE_REPLY_TEXT,
    _collect_merged_generator_reply,
    generator_node,
)

from tests.conftest import make_logistics_buffer


@pytest.mark.asyncio
async def test_m5_merge_inv_check_and_gap_calc_real_handlers() -> None:
    """FR-52：同一轮合并「查库存」与「缺口」话术，均为真实 handler。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(
        inventory_snapshot={"大米": {"amount": 2.0, "unit": "kg"}},
        gap_delivery_mode="fresh",
        shopping_list=[{"name": "青菜", "amount": 300.0, "unit": "g"}],
        sufficient_items=[],
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "error_state": {},
        "messages": [],
    }
    merged, stack = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_INV_CHECK", "TASK_GAP_CALC"],
        lb,
    )
    assert not stack
    assert "大米" in merged and "青菜" in merged
    assert "\n\n" in merged


@pytest.mark.asyncio
async def test_m5_clarify_branch_returns_readable_message() -> None:
    """TASK_CLARIFY：有候选时产出含序号/选择的可读澄清（FR-22 生成侧）。"""
    lb = make_logistics_buffer(
        recipe_candidates=[
            {"title": "西红柿炒鸡蛋"},
            {"title": "西红柿牛腩煲"},
        ],
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_CLARIFY", "TASK_SEARCH"],
        "messages": [HumanMessage(content="西红柿")],
        "loop_guard_count": 0,
    }
    out = await generator_node(state)
    msgs = out.get("messages") or []
    assert msgs
    body = getattr(msgs[-1], "content", "") or ""
    assert "西红柿" in body
    assert "1" in body or "一" in body or "选择" in body


def test_m5_meta_intent_constants_stable() -> None:
    """T-006 / FR-02：帮助与超范围固定话术仍为非空稳定文案。"""
    assert len(HELP_REPLY_TEXT) > 40 and "菜谱" in HELP_REPLY_TEXT
    assert len(OUT_OF_SCOPE_REPLY_TEXT) > 20 and "范围" in OUT_OF_SCOPE_REPLY_TEXT


@pytest.mark.asyncio
async def test_m5_merge_three_segments_including_direct_reply() -> None:
    """成果栈含 DIRECT_REPLY（help）时与缺口段合并顺序正确。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(
        gap_delivery_mode="fresh",
        shopping_list=[{"name": "盐", "amount": 5.0, "unit": "g"}],
        sufficient_items=[],
    )
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "primary_intent": "help",
        "error_state": {},
        "messages": [],
    }
    merged, _ = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_GAP_CALC", "TASK_DIRECT_REPLY"],
        lb,
    )
    assert HELP_REPLY_TEXT in merged
    assert "盐" in merged
    idx_gap = merged.find("盐")
    idx_help = merged.find("你好")
    assert idx_gap >= 0 and idx_help >= 0 and idx_gap < idx_help
