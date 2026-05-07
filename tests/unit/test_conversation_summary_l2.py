"""T-009 / §4.2：L2 `conversation_summary_node` 仅维护 messages 与摘要，不触碰业务切片。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.nodes.conversation_summary import conversation_summary_node
from tests.conftest import make_minimal_agent_state


@pytest.mark.asyncio
async def test_l2_empty_messages_returns_empty():
    state = make_minimal_agent_state()
    state["messages"] = []
    out = await conversation_summary_node(state)
    assert out == {}


@pytest.mark.asyncio
async def test_l2_under_compress_threshold_no_llm_preserves_business_fields_untouched():
    """消息条数 ≤ COMPRESS_TRIGGER：不触发压缩，不调用 LLM；返回值不含 task_stack / recipe_state 等。"""
    state = make_minimal_agent_state()
    state["messages"] = [HumanMessage(content="今天吃什么？")]
    state["memory_state"] = {
        "conversation_summary": "用户偏好清淡",
        "short_term_constraints": ["少油"],
    }
    state["task_stack"] = ["TASK_CLARIFY", "TASK_SEARCH"]
    state["recipe_state"] = {"recipe_candidates": [{"title": "番茄炒蛋"}]}

    out = await conversation_summary_node(state)

    assert set(out.keys()) <= {"messages", "conversation_summary", "memory_state"}
    assert "task_stack" not in out
    assert "recipe_state" not in out
    assert "inventory_state" not in out
    assert "control_state" not in out
    assert out["conversation_summary"] == "用户偏好清淡"
    # 节点仅返回摘要键补丁，由 merge_slice 与上一轮 memory_state 合并
    assert out["memory_state"] == {"conversation_summary": "用户偏好清淡"}
    assert out["messages"] == state["messages"]


@pytest.mark.asyncio
async def test_l2_compress_path_mocked_does_not_return_business_keys():
    """触发压缩时仅返回 messages / conversation_summary / memory_state 摘要镜像。"""
    state = make_minimal_agent_state()
    # 9 条 > COMPRESS_TRIGGER(8)
    state["messages"] = [
        HumanMessage(content=f"轮次{i}") if i % 2 == 0 else AIMessage(content=f"回复{i}")
        for i in range(9)
    ]
    state["conversation_summary"] = ""
    state["memory_state"] = {}
    state["task_stack"] = ["TASK_GAP_CALC"]
    state["inventory_state"] = {"inventory_snapshot": {"鸡蛋": {"amount": 1, "unit": "个"}}}

    kept = state["messages"][-4:]
    merged = "摘要：用户多轮追问菜谱。"

    with patch(
        "src.agent.nodes.conversation_summary.ConversationSummaryManager.maybe_compress",
        new_callable=AsyncMock,
        return_value=(kept, merged),
    ) as mc:
        out = await conversation_summary_node(state)

    mc.assert_awaited_once()
    assert set(out.keys()) == {"messages", "conversation_summary", "memory_state"}
    assert out["messages"] == kept
    assert out["conversation_summary"] == merged
    assert out["memory_state"] == {"conversation_summary": merged}
    assert "task_stack" not in out
    assert "inventory_state" not in out


@pytest.mark.asyncio
async def test_l2_on_failure_returns_empty():
    state = make_minimal_agent_state()
    state["messages"] = [HumanMessage("x")]

    with patch(
        "src.agent.nodes.conversation_summary.ConversationSummaryManager.maybe_compress",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        out = await conversation_summary_node(state)

    assert out == {}
