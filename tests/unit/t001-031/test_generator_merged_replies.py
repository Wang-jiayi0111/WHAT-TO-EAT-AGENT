"""T-008：次意图按 task_stack 顺序合并为单条答复（FR-52）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_merge_two_tasks_order_and_double_newline():
    from src.agent.nodes.generator import _collect_merged_generator_reply

    gen = MagicMock()
    gen.handle_inv_check.return_value = "第一段"
    gen.handle_gap_calc.return_value = "第二段"
    lb: dict = {}
    state = {"logistics_buffer": lb}
    merged, stack = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_INV_CHECK", "TASK_GAP_CALC"],
        lb,
    )
    assert merged == "第一段\n\n第二段"
    assert stack == []


@pytest.mark.asyncio
async def test_non_mergeable_token_kept_in_place():
    from src.agent.nodes.generator import _collect_merged_generator_reply

    gen = MagicMock()
    gen.handle_inv_check.return_value = "库存"
    gen.handle_gap_calc.return_value = "缺口"
    lb: dict = {}
    state = {"logistics_buffer": lb}
    merged, stack = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_INV_CHECK", "TASK_SEARCH", "TASK_GAP_CALC"],
        lb,
    )
    assert merged == "库存\n\n缺口"
    assert stack == ["TASK_SEARCH"]


@pytest.mark.asyncio
async def test_summarize_consumes_and_appends_pending_tasks():
    from src.agent.nodes.generator import GeneratorNode, _collect_merged_generator_reply

    gen = GeneratorNode()
    lb = {
        "selected_recipe_title": "测试菜",
        "recipe_cook_step": ["步骤一"],
        "pending_tasks": ["TASK_INV_ADD"],
    }
    state = {"logistics_buffer": lb}
    merged, stack = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_SUMMARIZE"],
        lb,
    )
    assert "测试菜" in merged
    assert "步骤一" in merged
    assert "TASK_SUMMARIZE" not in stack
    assert "TASK_INV_ADD" in stack
    assert lb.get("pending_tasks") == []


@pytest.mark.asyncio
async def test_direct_reply_degraded_skips_llm():
    from src.agent.nodes.generator import _collect_merged_generator_reply

    gen = MagicMock()
    gen.handle_direct_reply = AsyncMock(return_value="不应使用")
    lb = {"degraded_reply": "降级话术"}
    state = {"logistics_buffer": lb}
    merged, stack = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_DIRECT_REPLY"],
        lb,
    )
    assert merged == "降级话术"
    assert stack == []
    gen.handle_direct_reply.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_mergeable_occurrences_stacked_twice():
    from src.agent.nodes.generator import _collect_merged_generator_reply

    gen = MagicMock()
    gen.handle_inv_check.side_effect = ["甲", "乙"]
    lb: dict = {}
    state = {"logistics_buffer": lb}
    merged, stack = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_INV_CHECK", "TASK_INV_CHECK"],
        lb,
    )
    assert merged == "甲\n\n乙"
    assert stack == []
