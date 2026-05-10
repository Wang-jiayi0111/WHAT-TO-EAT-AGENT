"""
M3 菜谱子系统模块间集成验收（T-015～T-019 / 规格 §2、§5）。

串联单测已覆盖的模块，做一次「竖切」回归（不启动真实 MCP / RAG）：
**C** → 检索 query 增强 → §2.2 成功体归一；FR-24 空结果软重试；低置信歧义 → `clarify_resolver` 锁定菜名。

不替代 `tests/unit/test_t015_*` … `test_t019_*`；此处侧重跨模块数据流与状态衔接。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agent.memory.effective_constraint import (
    augment_search_query,
    build_effective_constraint,
)
from src.agent.nodes.clarify_resolver import clarify_resolver_node
from src.agent.nodes.researcher import researcher_node
from src.agent.nodes.schema import Ingredient, StructuredRecipe
from src.agent.recipe.ambiguity import build_ambiguity_candidates
from src.agent.core.state_accessors import get_runtime_bundle
from src.mcp.protocol import (
    is_mcp_error_response,
    normalize_search_recipes_success_body,
)
from tests.conftest import make_logistics_buffer, make_minimal_agent_state


def test_m3_chain_c_to_query_to_mcp_success_body_contract():
    """T-015 + T-019：合并 **C** → 增强 query → 成功体仅 id/title/score。"""
    state = make_minimal_agent_state()
    state["active_user_id"] = "u_m3"
    state["memory_state"] = {
        "short_term_constraints": ["少油"],
        "conversation_summary": "",
    }
    profile = {
        "short_term_states": [],
        "allergens": [],
        "medical_restrictions": [],
        "taste_tags": {"like": ["汤"], "dislike": []},
        "disliked_foods": [],
        "dietary_target": None,
    }
    c = build_effective_constraint(state, profile=profile, scope_id="scope_m3")
    q = augment_search_query("冬瓜", c, state)
    assert "冬瓜" in q

    raw_items = [
        {"id": "a.md", "title": "冬瓜汤", "score": 0.9, "content": "SECRET", "source": "/x"},
    ]
    body = normalize_search_recipes_success_body(raw_items, q, effective_constraint_applied=True)
    assert not is_mcp_error_response(body)
    assert body.get("effective_constraint_applied") is True
    for item in body["recipes"]:
        assert set(item.keys()) == {"id", "title", "score"}
        assert "content" not in item


def test_m3_build_ambiguity_candidates_aligns_with_low_confidence_cap():
    """T-017：歧义候选裁剪与 researcher 所用 `build_ambiguity_candidates` 一致。"""
    recipes = [{"title": f"T{i}", "score": 1.0 - i * 0.01} for i in range(8)]
    capped = build_ambiguity_candidates(recipes, max_n=3)
    assert len(capped) == 3
    assert capped[0]["rank"] == 1


@pytest.mark.asyncio
async def test_m3_researcher_fr24_soft_retry_then_recipe_search_empty():
    """T-018：首轮空 + 软信号 → 二次检索仍空 → `RECIPE_SEARCH_EMPTY` 与重试标记。"""
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        side_effect=[
            {"recipes": []},
            {"recipes": []},
        ]
    )
    lb = make_logistics_buffer(extracted_entities={"recipe_name": "无此菜"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("找菜")]
    fake_c = {
        "scope_id": "m3_fr24",
        "hard_exclusions": [],
        "soft_positive_hints": ["清淡"],
        "soft_negative_hints": [],
        "temporal_conditions": [],
        "dietary_target": None,
        "summary_snippet": None,
    }
    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15
    mock_settings.get_ambiguity_max_candidates.return_value = 6
    mock_settings.get_recipe_search_soft_retry_max.return_value = 1

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=fake_c),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q or "q",
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        out = await researcher_node(state)

    assert out["expert_payloads"].get("error_code") == "RECIPE_SEARCH_EMPTY"
    assert out["expert_payloads"].get("recipe_search_soft_retry_attempted") is True
    assert mock_rr.search_recipes.await_count == 2


@pytest.mark.asyncio
async def test_m3_ambiguous_researcher_then_clarify_numeric(tmp_path):
    """T-016/T-017：低置信 → 歧义态；用户回复「1」→ `clarify_resolver` 锁定 title 并推进栈。"""
    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "左候选", "score": 0.20, "id": "a.md"},
                {"title": "右候选", "score": 0.19, "id": "b.md"},
            ]
        }
    )
    lb = make_logistics_buffer(extracted_entities={"recipe_name": "肉"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("想吃肉")]
    state["task_stack"] = ["TASK_SEARCH"]

    fake_c = {
        "scope_id": "m3_amb",
        "hard_exclusions": [],
        "soft_positive_hints": [],
        "soft_negative_hints": [],
        "temporal_conditions": [],
        "dietary_target": None,
        "summary_snippet": None,
    }
    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15
    mock_settings.get_ambiguity_max_candidates.return_value = 6
    mock_settings.get_recipe_search_soft_retry_max.return_value = 1

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=fake_c),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
        patch("src.agent.nodes.researcher.Settings", return_value=mock_settings),
    ):
        r1 = await researcher_node(state)

    assert r1["expert_payloads"].get("status") == "ambiguous"
    merged = {**state, **r1}
    merged["messages"] = list(merged.get("messages") or []) + [HumanMessage("1")]
    r2 = clarify_resolver_node(merged)
    rb = get_runtime_bundle({**merged, **r2})
    assert rb.get("selected_recipe_title") == "左候选"
    assert "TASK_SEARCH" in r2.get("task_stack", [])


@pytest.mark.asyncio
async def test_m3_high_confidence_authoritative_r_after_research(tmp_path):
    """T-016：单候选高置信 → `get_recipe_source` + 全文解析 → 成功载荷。"""
    md = tmp_path / "m3dish.md"
    md.write_text("# m3dish\n", encoding="utf-8")
    ing = Ingredient(name="盐", amount=1.0, unit="g")
    structured = StructuredRecipe(title="m3dish", ingredients=[ing], steps=[])

    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {"title": "m3dish", "score": 1.0, "id": "m3dish.md", "source": str(md)},
            ]
        }
    )
    mock_rr.get_recipe_source = AsyncMock(return_value=str(md))
    mock_rr.parse_recipe_content = AsyncMock(return_value=structured)

    lb = make_logistics_buffer(extracted_entities={"recipe_name": "x"})
    state = make_minimal_agent_state(logistics_buffer=lb)
    state["messages"] = [HumanMessage("x")]

    fake_c = {
        "scope_id": "m3_hi",
        "hard_exclusions": [],
        "soft_positive_hints": [],
        "soft_negative_hints": [],
        "temporal_conditions": [],
        "dietary_target": None,
        "summary_snippet": None,
    }
    mock_settings = MagicMock()
    mock_settings.get_retrieval_top2_relative_gap.return_value = 0.15
    mock_settings.get_ambiguity_max_candidates.return_value = 6
    mock_settings.get_recipe_search_soft_retry_max.return_value = 1

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

    assert out["expert_payloads"].get("status") == "success"
    rb = get_runtime_bundle(out)
    assert rb.get("recipe_parser_version")
    assert len(rb.get("recipe_requirements") or []) >= 1
