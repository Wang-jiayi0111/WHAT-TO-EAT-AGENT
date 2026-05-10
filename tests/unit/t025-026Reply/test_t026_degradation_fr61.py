"""
T-026 全链路降级话术（FR-61）
==========================

**任务**：T-026  
**规格**：FR-61  
**开发记录**：`docs/dev_log.md` [DEV-031]

验收结论写入 **`docs/test_report.md`** [TR-039]。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_sync import runtime_bundle_to_slice_patches
from src.agent.responses.degradation_messages import (
    message_generator_empty_turn,
    message_llm_call_failed,
    message_llm_empty_output,
    message_merged_segments_empty,
    message_recipe_search_service_unavailable,
)
from src.agent.nodes.generator import GeneratorNode, _collect_merged_generator_reply, generator_node

from tests.conftest import make_logistics_buffer


def test_t026_degradation_messages_are_nonempty_and_distinct() -> None:
    """降级文案非空且各有可辨认同口径短语。"""
    assert "模型" in message_llm_call_failed() or "超时" in message_llm_call_failed()
    assert "有效文字" in message_llm_empty_output()
    assert "内部步骤" in message_merged_segments_empty(["TASK_INV_CHECK"])
    assert "检索服务" in message_recipe_search_service_unavailable()
    assert "可读内容" in message_generator_empty_turn(["TASK_SEARCH"])


@pytest.mark.asyncio
async def test_t026_handle_direct_reply_empty_llm_yields_empty_output_message() -> None:
    """LLM 返回空白 → `message_llm_empty_output`。"""
    gen = GeneratorNode()
    mock_resp = MagicMock()
    mock_resp.content = "   \n"
    gen.llm = MagicMock()
    gen.llm.ainvoke = AsyncMock(return_value=mock_resp)
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(make_logistics_buffer()),
        "primary_intent": "general_chat",
        "messages": [],
    }
    out = await gen.handle_direct_reply(state)
    assert out == message_llm_empty_output()


@pytest.mark.asyncio
async def test_t026_handle_direct_reply_exception_yields_call_failed_message() -> None:
    """LLM 异常 → `message_llm_call_failed`。"""
    gen = GeneratorNode()
    gen.llm = MagicMock()
    gen.llm.ainvoke = AsyncMock(side_effect=RuntimeError("simulated failure"))
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(make_logistics_buffer()),
        "primary_intent": "dietary_advice",
        "messages": [],
    }
    out = await gen.handle_direct_reply(state)
    assert out == message_llm_call_failed()


@pytest.mark.asyncio
async def test_t026_collect_merge_empty_segments_fr61_fallback() -> None:
    """成果任务已消费但段全空 → `message_merged_segments_empty`。"""
    gen = MagicMock(spec=GeneratorNode)
    gen.handle_inv_check.return_value = ""
    lb: dict = {}
    state = {"task_stack": ["TASK_INV_CHECK"], "logistics_buffer": lb}
    merged, _ = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_INV_CHECK"],
        lb,
    )
    assert merged == message_merged_segments_empty(["TASK_INV_CHECK"])


@pytest.mark.asyncio
async def test_t026_generator_node_non_mergeable_only_yields_empty_turn() -> None:
    """仅非合并类任务时合并为空 → `message_generator_empty_turn`，仍产出 AIMessage。"""
    lb = make_logistics_buffer()
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": ["TASK_SEARCH"],
        "messages": [],
        "loop_guard_count": 0,
    }
    out = await generator_node(state)
    assert out
    msgs = out.get("messages") or []
    assert msgs
    last = msgs[-1]
    content = getattr(last, "content", str(last))
    assert content.strip() == message_generator_empty_turn(["TASK_SEARCH"]).strip()


@pytest.mark.asyncio
async def test_t026_recipe_search_unavailable_matches_helper() -> None:
    """researcher 写入的 MCP 不可用话术与集中函数一致。"""
    from src.agent.nodes import researcher as researcher_mod

    assert (
        researcher_mod.message_recipe_search_service_unavailable()
        == message_recipe_search_service_unavailable()
    )
