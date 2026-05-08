"""
T-016 / FR-21 / 规格 §5.1～§5.2：高置信锁定与全文解析 **R**。

覆盖：`stage1_high_confidence`、`coerce_mcp_recipe_path`、`resolve_authoritative_structured_recipe`、
`RECIPE_SOURCE_NOT_FOUND` / `RECIPE_PARSE_FAILED`；`researcher_node` 检索分支高/低置信（mock MCP）。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.libs.base.settings import Settings
from src.agent.nodes.researcher import (
    coerce_mcp_recipe_path,
    resolve_authoritative_structured_recipe,
    researcher_node,
    stage1_high_confidence,
)
from src.agent.nodes.schema import Ingredient, StructuredRecipe
from src.agent.state_accessors import get_runtime_bundle
from tests.conftest import make_logistics_buffer, make_minimal_agent_state


def test_stage1_high_confidence_single_candidate_always_locked():
    assert stage1_high_confidence([{"score": 0.1}], gap=0.15) is True


def test_stage1_high_confidence_empty():
    assert stage1_high_confidence([], gap=0.15) is False


def test_stage1_high_confidence_two_candidates_uses_relative_gap():
    gap = 0.15
    assert stage1_high_confidence([{"score": 1.0}, {"score": 0.5}], gap)
    assert not stage1_high_confidence([{"score": 0.20}, {"score": 0.19}], gap)


def test_coerce_mcp_recipe_path_variants():
    assert coerce_mcp_recipe_path(None) == ""
    assert coerce_mcp_recipe_path({"error": "x"}) == ""
    assert coerce_mcp_recipe_path({"file_path": "/tmp/a.md"}) == "/tmp/a.md"
    assert coerce_mcp_recipe_path("/abs/x.md") == "/abs/x.md"


@pytest.mark.asyncio
async def test_resolve_authoritative_empty_title():
    r = MagicMock()
    sr, path, err = await resolve_authoritative_structured_recipe(r, "")
    assert sr is None and path == "" and err == "source_not_found"


@pytest.mark.asyncio
async def test_resolve_authoritative_source_error_dict():
    r = MagicMock()
    r.get_recipe_source = AsyncMock(return_value={"error": "nf"})
    sr, path, err = await resolve_authoritative_structured_recipe(r, "菜A")
    assert sr is None and err == "source_not_found"


@pytest.mark.asyncio
async def test_resolve_authoritative_file_missing_after_coerce():
    r = MagicMock()
    r.get_recipe_source = AsyncMock(return_value={"file_path": "/nonexistent/xyz.md"})
    sr, path, err = await resolve_authoritative_structured_recipe(r, "菜B")
    assert sr is None and err == "source_not_found"


@pytest.mark.asyncio
async def test_resolve_authoritative_empty_r(tmp_path: Path):
    md = tmp_path / "r.md"
    md.write_text("# 测试\n", encoding="utf-8")

    r = MagicMock()
    r.get_recipe_source = AsyncMock(return_value=str(md))
    r.parse_recipe_content = AsyncMock(
        return_value=StructuredRecipe(title="测试", ingredients=[], steps=[])
    )

    sr, path, err = await resolve_authoritative_structured_recipe(r, "测试")
    assert sr is None and err == "empty_r"
    assert path == str(md)


@pytest.mark.asyncio
async def test_resolve_authoritative_success(tmp_path: Path):
    md = tmp_path / "ok.md"
    md.write_text("# 好菜\n", encoding="utf-8")
    ing = Ingredient(name="蛋", amount=2.0, unit="个")
    structured = StructuredRecipe(title="好菜", ingredients=[ing], steps=["炒"])

    r = MagicMock()
    r.get_recipe_source = AsyncMock(return_value=str(md))
    r.parse_recipe_content = AsyncMock(return_value=structured)

    sr, path, err = await resolve_authoritative_structured_recipe(r, "好菜")
    assert err == ""
    assert path == str(md)
    assert sr is not None and len(sr.ingredients) == 1


def _fake_effective_c():
    return {
        "scope_id": "t016",
        "hard_exclusions": [],
        "temporal_conditions": [],
        "summary_snippet": None,
        "soft_positive_hints": [],
        "soft_negative_hints": [],
        "dietary_target": None,
    }


@pytest.mark.asyncio
async def test_researcher_node_high_confidence_sets_parser_version_and_requirements(tmp_path: Path):
    md = tmp_path / "dish.md"
    md.write_text("#  locked\n", encoding="utf-8")
    ing = Ingredient(name="米", amount=1.0, unit="杯")
    structured = StructuredRecipe(title="locked", ingredients=[ing], steps=[])

    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "locked", "score": 1.0, "id": "1.md", "source": str(md)},
            ]
        }
    )
    mock_rr.get_recipe_source = AsyncMock(return_value=str(md))
    mock_rr.parse_recipe_content = AsyncMock(return_value=structured)

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "x"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("找菜")]

    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15
    expected_pv = Settings().get_recipe_parser_version()
    mock_settings.get_recipe_parser_version.return_value = expected_pv

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=_fake_effective_c()),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        out = await researcher_node(state)

    rb = get_runtime_bundle(out)
    assert rb.get("recipe_parser_version") == expected_pv
    assert rb.get("recipe_title_locked") == "locked"
    assert len(rb.get("recipe_requirements") or []) == 1


@pytest.mark.asyncio
async def test_researcher_node_low_confidence_ambiguous_branch():
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "A", "score": 0.20, "id": "a.md"},
                {"title": "B", "score": 0.19, "id": "b.md"},
            ]
        }
    )

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "x"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("找菜")]

    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15
    mock_settings.get_ambiguity_max_candidates.return_value = 6

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=_fake_effective_c()),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        out = await researcher_node(state)

    assert out["expert_payloads"].get("status") == "ambiguous"
    rb = get_runtime_bundle(out)
    assert rb.get("recipe_candidates")


@pytest.mark.asyncio
async def test_researcher_node_high_confidence_source_not_found():
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "仅有标题", "score": 1.0, "id": "1.md"},
            ]
        }
    )
    mock_rr.get_recipe_source = AsyncMock(return_value={"error": "not found"})

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "x"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("找菜")]

    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=_fake_effective_c()),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        out = await researcher_node(state)

    assert out["expert_payloads"].get("error_code") == "RECIPE_SOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_researcher_node_high_confidence_parse_failed_empty_r(tmp_path: Path):
    md = tmp_path / "x.md"
    md.write_text("# 仅有标题\n", encoding="utf-8")

    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "仅有标题", "score": 1.0, "id": "1.md"},
            ]
        }
    )
    mock_rr.get_recipe_source = AsyncMock(return_value=str(md))
    mock_rr.parse_recipe_content = AsyncMock(
        return_value=StructuredRecipe(title="仅有标题", ingredients=[], steps=[])
    )

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "x"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("找菜")]

    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=_fake_effective_c()),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        out = await researcher_node(state)

    assert out["expert_payloads"].get("error_code") == "RECIPE_PARSE_FAILED"
