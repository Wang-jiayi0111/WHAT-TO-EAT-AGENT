"""
T-018 / FR-24：无结果说明与软约束放宽重试（`effective_constraint` + `researcher_node`）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agent.memory.effective_constraint import (
    effective_constraint_has_retryable_soft_signals,
    relaxed_effective_constraint_for_search_retry,
)
from src.agent.nodes.researcher import researcher_node
from src.agent.nodes.schema import Ingredient, StructuredRecipe
from src.agent.core.state_accessors import get_runtime_bundle
from tests.conftest import make_logistics_buffer, make_minimal_agent_state


def test_effective_constraint_has_retryable_soft_signals_positive():
    assert effective_constraint_has_retryable_soft_signals(
        {
            "hard_exclusions": [],
            "soft_positive_hints": ["清淡"],
            "soft_negative_hints": [],
            "temporal_conditions": [],
            "dietary_target": None,
            "summary_snippet": None,
        }
    )


def test_effective_constraint_has_retryable_soft_signals_from_temporal_dietary_summary():
    assert effective_constraint_has_retryable_soft_signals(
        {
            "temporal_conditions": ["感冒"],
            "dietary_target": " 低糖 ",
            "summary_snippet": "用户爱喝汤",
            "soft_negative_hints": [],
            "soft_positive_hints": [],
            "hard_exclusions": [],
        }
    )


def test_effective_constraint_has_retryable_soft_signals_false_when_only_hard():
    assert not effective_constraint_has_retryable_soft_signals(
        {
            "hard_exclusions": ["花生"],
            "soft_positive_hints": [],
            "soft_negative_hints": [],
            "temporal_conditions": [],
            "dietary_target": None,
            "summary_snippet": None,
        }
    )


def test_relaxed_effective_constraint_keeps_hard_and_scope_clears_soft():
    c = {
        "scope_id": "house_x",
        "hard_exclusions": ["walnut"],
        "soft_positive_hints": ["mild"],
        "soft_negative_hints": ["cilantro"],
        "temporal_conditions": ["cold"],
        "dietary_target": "low sugar",
        "summary_snippet": "summary",
    }
    r = relaxed_effective_constraint_for_search_retry(c)
    assert r["scope_id"] == "house_x"
    assert r["hard_exclusions"] == ["walnut"]
    assert r["soft_positive_hints"] == []
    assert r["soft_negative_hints"] == []
    assert r["temporal_conditions"] == []
    assert r["dietary_target"] is None
    assert r["summary_snippet"] is None


def _fake_c_with_soft():
    return {
        "scope_id": "t018",
        "hard_exclusions": [],
        "soft_positive_hints": ["清淡"],
        "soft_negative_hints": [],
        "temporal_conditions": [],
        "dietary_target": None,
        "summary_snippet": None,
    }


def _mock_settings_for_researcher(*, soft_retry_max: int = 1):
    m = MagicMock()
    m.get_retrieval_top2_relative_gap.return_value = 0.15
    m.get_ambiguity_max_candidates.return_value = 6
    m.get_recipe_search_soft_retry_max.return_value = soft_retry_max
    return m


@pytest.mark.asyncio
async def test_researcher_empty_then_soft_retry_still_empty_sets_fr24_flags():
    """首轮空 + 可重试软信号 → 第二次仍空 → 长文案 + RECIPE_SEARCH_EMPTY + soft_retry 标记。"""
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        side_effect=[
            {"recipes": []},
            {"recipes": []},
        ]
    )

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "不存在的菜"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("随便")]

    with (
        patch(
            "src.agent.nodes.researcher.build_effective_constraint",
            return_value=_fake_c_with_soft(),
        ),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q or "fallback",
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch(
            "src.agent.nodes.researcher.Settings",
            return_value=_mock_settings_for_researcher(soft_retry_max=1),
        ),
    ):
        out = await researcher_node(state)

    assert mock_rr.search_recipes.await_count == 2
    assert out["expert_payloads"].get("error_code") == "RECIPE_SEARCH_EMPTY"
    assert out["expert_payloads"].get("recipe_search_soft_retry_attempted") is True
    rb = get_runtime_bundle(out)
    assert "放宽" in (rb.get("degraded_reply") or "")


@pytest.mark.asyncio
async def test_researcher_empty_no_soft_signals_no_second_search():
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(return_value={"recipes": []})

    c = {
        "scope_id": "t018b",
        "hard_exclusions": ["peanut"],
        "soft_positive_hints": [],
        "soft_negative_hints": [],
        "temporal_conditions": [],
        "dietary_target": None,
        "summary_snippet": None,
    }
    lb = make_logistics_buffer(extracted_entities={"recipe_name": "x"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("y")]

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=c),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, cc, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch(
            "src.agent.nodes.researcher.Settings",
            return_value=_mock_settings_for_researcher(soft_retry_max=1),
        ),
    ):
        out = await researcher_node(state)

    assert mock_rr.search_recipes.await_count == 1
    assert out["expert_payloads"].get("recipe_search_soft_retry_attempted") is False
    rb = get_runtime_bundle(out)
    assert "暂时没有找到" in (rb.get("degraded_reply") or "")
    assert "放宽" not in (rb.get("degraded_reply") or "")


@pytest.mark.asyncio
async def test_researcher_soft_retry_max_zero_skips_retry():
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(return_value={"recipes": []})

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "z"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("z")]

    with (
        patch(
            "src.agent.nodes.researcher.build_effective_constraint",
            return_value=_fake_c_with_soft(),
        ),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch(
            "src.agent.nodes.researcher.Settings",
            return_value=_mock_settings_for_researcher(soft_retry_max=0),
        ),
    ):
        out = await researcher_node(state)

    assert mock_rr.search_recipes.await_count == 1
    assert out["expert_payloads"].get("recipe_search_soft_retry_attempted") is False


@pytest.mark.asyncio
async def test_researcher_second_search_returns_recipes_stops_retry_loop(tmp_path):
    """放宽后第二次检索有结果 → 走后续高置信 / 歧义逻辑，不应带 RECIPE_SEARCH_EMPTY。"""
    md = tmp_path / "one.md"
    md.write_text("# one\n", encoding="utf-8")

    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        side_effect=[
            {"recipes": []},
            {
                "recipes": [
                    {"title": "one", "score": 1.0, "id": "one.md", "source": str(md)},
                ]
            },
        ]
    )
    mock_rr.get_recipe_source = AsyncMock(return_value=str(md))
    mock_rr.parse_recipe_content = AsyncMock(
        return_value=StructuredRecipe(
            title="one",
            ingredients=[Ingredient(name="水", amount=1.0, unit="ml")],
            steps=[],
        )
    )

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "q"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("q")]

    with (
        patch(
            "src.agent.nodes.researcher.build_effective_constraint",
            return_value=_fake_c_with_soft(),
        ),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch(
            "src.agent.nodes.researcher.Settings",
            return_value=_mock_settings_for_researcher(soft_retry_max=1),
        ),
    ):
        out = await researcher_node(state)

    assert mock_rr.search_recipes.await_count == 2
    assert out["expert_payloads"].get("status") == "success"
    assert out["expert_payloads"].get("error_code") is None
