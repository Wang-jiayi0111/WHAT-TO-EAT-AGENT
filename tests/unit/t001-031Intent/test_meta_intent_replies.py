"""T-006：元意图 help / out_of_scope / dietary_advice / recipe_adopt（FR-02；§11.3～11.4）。"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage


@pytest.fixture
def minimal_lb():
    return {
        "extracted_entities": {},
        "router_reasoning": "",
        "recipe_candidates": [],
        "selected_recipe_id": None,
        "recipe_requirements": [],
        "recipe_cook_step": None,
        "inventory_snapshot": [],
        "ingredient_gaps": [],
        "action_metadata": {},
        "pending_tasks": [],
    }


@pytest.mark.asyncio
async def test_handle_direct_reply_help(minimal_lb):
    from src.agent.nodes.generator import GeneratorNode, HELP_REPLY_TEXT

    g = GeneratorNode()
    state = {
        "primary_intent": "help",
        "messages": [HumanMessage(content="你能做什么")],
        "conversation_summary": "",
        "logistics_buffer": minimal_lb,
    }
    out = await g.handle_direct_reply(state)
    assert out == HELP_REPLY_TEXT


@pytest.mark.asyncio
async def test_handle_direct_reply_out_of_scope(minimal_lb):
    from src.agent.nodes.generator import GeneratorNode, OUT_OF_SCOPE_REPLY_TEXT

    g = GeneratorNode()
    state = {
        "primary_intent": "out_of_scope",
        "messages": [HumanMessage(content="写一段排序算法")],
        "conversation_summary": "",
        "logistics_buffer": minimal_lb,
    }
    out = await g.handle_direct_reply(state)
    assert out == OUT_OF_SCOPE_REPLY_TEXT


@pytest.mark.asyncio
async def test_handle_direct_reply_recipe_adopt(minimal_lb):
    from src.agent.nodes.generator import GeneratorNode

    g = GeneratorNode()
    lb = {**minimal_lb, "selected_recipe_title": "糖醋排骨"}
    state = {
        "primary_intent": "recipe_adopt",
        "messages": [HumanMessage(content="就做糖醋排骨")],
        "conversation_summary": "",
        "logistics_buffer": lb,
    }
    out = await g.handle_direct_reply(state)
    assert "糖醋排骨" in out


@pytest.mark.asyncio
async def test_handle_direct_reply_dietary_delegates(minimal_lb):
    from unittest.mock import AsyncMock

    from src.agent.nodes.generator import GeneratorNode

    g = GeneratorNode()
    g.handle_dietary_advice = AsyncMock(return_value="建议清淡饮食。")
    state = {
        "primary_intent": "dietary_advice",
        "slots": {"diet_topic": "感冒清淡"},
        "messages": [HumanMessage(content="感冒吃什么")],
        "conversation_summary": "",
        "logistics_buffer": minimal_lb,
    }
    out = await g.handle_direct_reply(state)
    assert "清淡" in out
    g.handle_dietary_advice.assert_called_once()
