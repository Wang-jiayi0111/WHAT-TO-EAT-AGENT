"""
T-017 / FR-22 / 规格 §5.1：多候选澄清——有限结构化候选、`clarify_resolver` 解析、generator 无效选择话术。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agent.nodes.clarify_resolver import (
    _normalize_candidates,
    _parse_user_choice,
    clarify_resolver_node,
)
from src.agent.nodes.generator import GeneratorNode
from src.agent.nodes.researcher import researcher_node
from src.agent.recipe_ambiguity import build_ambiguity_candidates
from src.agent.state_accessors import get_runtime_bundle
from tests.conftest import make_logistics_buffer, make_minimal_agent_state


def test_build_ambiguity_candidates_cap_and_dedup():
    recipes = [
        {"title": "A菜", "score": 0.9},
        {"title": "A菜", "score": 0.8},
        {"title": "B菜", "score": 0.7},
        {"title": "C菜", "score": 0.6},
    ]
    out = build_ambiguity_candidates(recipes, max_n=2)
    assert len(out) == 2
    assert out[0]["title"] == "A菜" and out[0]["rank"] == 1
    assert out[1]["title"] == "B菜" and out[1]["rank"] == 2
    assert "score" in out[0]


def test_build_ambiguity_candidates_empty_or_zero_cap():
    assert build_ambiguity_candidates([], max_n=6) == []
    assert build_ambiguity_candidates([{"title": "x", "score": 1}], max_n=0) == []


def test_parse_user_choice_digit():
    cands = _normalize_candidates(["Alpha", "Beta"])
    assert _parse_user_choice("2", cands)["title"] == "Beta"
    assert _parse_user_choice("选1", cands)["title"] == "Alpha"


def test_parse_user_choice_partial_title():
    cands = _normalize_candidates([{"title": "糖醋排骨"}, {"title": "红烧肉"}])
    picked = _parse_user_choice("糖醋", cands)
    assert picked and picked["title"] == "糖醋排骨"


def test_parse_user_choice_unrecognized():
    cands = _normalize_candidates(["A", "B"])
    assert _parse_user_choice("完全无关xyz", cands) is None


def test_clarify_resolver_success_numeric_then_bundle():
    lb = make_logistics_buffer(
        recipe_candidates=[
            {"title": "候选甲", "score": 0.5, "rank": 1},
            {"title": "候选乙", "score": 0.4, "rank": 2},
        ]
    )
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["task_stack"] = ["TASK_SEARCH", "TASK_CLARIFY"]
    state["messages"] = [HumanMessage(content="2")]

    out = clarify_resolver_node(state)
    rb = get_runtime_bundle(out)
    assert rb.get("selected_recipe_title") == "候选乙"
    assert rb.get("recipe_candidates") == []
    assert "TASK_SEARCH" in out["task_stack"]
    assert "TASK_CLARIFY" not in out["task_stack"]


def test_clarify_resolver_invalid_choice_sets_flag_and_stack():
    lb = make_logistics_buffer(
        recipe_candidates=[{"title": "仅一项", "score": 0.5, "rank": 1}],
    )
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage(content="不是序号也不是菜名zzz")]

    out = clarify_resolver_node(state)
    rb = get_runtime_bundle(out)
    assert rb.get("clarify_error") == "invalid_choice"
    assert out["task_stack"] == ["TASK_CLARIFY"]


def test_clarify_resolver_no_candidates_returns_empty():
    lb = make_logistics_buffer(recipe_candidates=[])
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("1")]
    assert clarify_resolver_node(state) == {}


def test_generator_handle_clarify_invalid_choice_prefix():
    lb = make_logistics_buffer(
        recipe_candidates=[
            {"title": "红烧肉", "score": 0.9, "rank": 1},
            {"title": "糖醋排骨", "score": 0.8, "rank": 2},
        ],
        clarify_error="invalid_choice",
    )
    state = make_minimal_agent_state(logistics_buffer=lb)

    with patch.object(GeneratorNode, "__init__", lambda self: None):
        gen = GeneratorNode.__new__(GeneratorNode)
        text = gen.handle_clarify(state)

    assert "没能识别" in text or "抱歉" in text
    assert "1～2" in text or "1~2" in text.replace("～", "~")
    assert "红烧肉" in text


@pytest.mark.asyncio
async def test_researcher_low_confidence_sets_structured_candidates_and_clarification_kind():
    """歧义分支：`build_ambiguity_candidates` 上限 + `clarification_kind`。"""
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "X", "score": 0.20, "id": "x.md"},
                {"title": "Y", "score": 0.19, "id": "y.md"},
                {"title": "Z", "score": 0.18, "id": "z.md"},
            ]
        }
    )

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "q"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("找菜")]

    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15
    mock_settings.get_ambiguity_max_candidates.return_value = 2

    fake_c = {
        "scope_id": "t017",
        "hard_exclusions": [],
        "temporal_conditions": [],
        "summary_snippet": None,
        "soft_positive_hints": [],
        "soft_negative_hints": [],
        "dietary_target": None,
    }

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=fake_c),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        out = await researcher_node(state)

    assert out["expert_payloads"].get("status") == "ambiguous"
    assert out["expert_payloads"].get("ambiguity_candidate_count") == 2
    rb = get_runtime_bundle(out)
    assert rb.get("clarification_kind") == "recipe_pick"
    cand = rb.get("recipe_candidates") or []
    assert len(cand) == 2
    # `materialize_runtime_bundle_from_slices` 将带 title 的 dict 压成字符串列表（legacy 形状）
    assert cand == ["X", "Y"]
