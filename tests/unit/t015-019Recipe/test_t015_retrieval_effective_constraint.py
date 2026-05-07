"""
T-015 / FR-11 / FR-20：检索链路统一传入有效约束 **C**。

覆盖：
- `RecipeResearcher.search_recipes` 将 `effective_constraint` 原样放入 MCP 参数（与无参对比）；
- `SearchRecipesService.execute` 在传入 **C** 时走 §5.4 硬过滤并返回 `effective_constraint_applied`；
- `researcher_node` 检索分支将 `build_effective_constraint` 结果交给 `search_recipes`，并写回 `memory_state.effective_constraint`。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agent.nodes.researcher import (
    RecipeResearcher,
    _merge_effective_constraint_into_memory_patch,
    researcher_node,
)
from src.agent.nodes.schema import StructuredRecipe
from src.mcp.tool import SearchRecipesService
from tests.conftest import make_logistics_buffer, make_minimal_agent_state


@pytest.mark.asyncio
async def test_search_recipes_includes_effective_constraint_in_mcp_args():
    """MCP `search_recipes` 调用参数含 **C**（T-015）。"""
    with patch.object(RecipeResearcher, "__init__", lambda self: None):
        rr = RecipeResearcher.__new__(RecipeResearcher)
        rr._call_mcp_tool = AsyncMock(return_value={"recipes": []})

        c = {"scope_id": "h1", "hard_exclusions": ["花生", "虾"]}
        await rr.search_recipes("晚餐", "h1", effective_constraint=c, top_k=10)

        rr._call_mcp_tool.assert_awaited_once()
        name, args = rr._call_mcp_tool.await_args.args
        assert name == "search_recipes"
        assert args["query"] == "晚餐"
        assert args["user_id"] == "h1"
        assert args["top_k"] == 10
        assert args["effective_constraint"] == c


@pytest.mark.asyncio
async def test_search_recipes_omits_constraint_key_when_none():
    with patch.object(RecipeResearcher, "__init__", lambda self: None):
        rr = RecipeResearcher.__new__(RecipeResearcher)
        rr._call_mcp_tool = AsyncMock(return_value={"recipes": []})

        await rr.search_recipes("x", "u", effective_constraint=None)

        _name, args = rr._call_mcp_tool.await_args.args
        assert "effective_constraint" not in args


@pytest.mark.asyncio
async def test_search_recipes_service_applies_hard_exclusions_section_54():
    """`SearchRecipesService` 传入 **C** 时按 §5.4 过滤（T-015）。"""
    rag = MagicMock()
    rag.get_detailed_results.return_value = {
        "results": [
            {
                "id": "1",
                "content": "chunk",
                "metadata": {"recipe_name": "\u82b1\u751f\u751c\u6c64"},  # 花生甜汤
                "score": 0.95,
            },
            {
                "id": "2",
                "content": "chunk",
                "metadata": {"recipe_name": "\u5927\u7c73\u7ca5"},  # 大米粥
                "score": 0.85,
            },
        ]
    }
    upm = MagicMock()
    upm.get_user_profile.return_value = None

    svc = SearchRecipesService(rag, upm)
    c = {"hard_exclusions": ["\u82b1\u751f"]}  # 花生，与 title 命中 §5.4
    out = await svc.execute("甜品", user_id="u", top_k=10, effective_constraint=c)

    assert out.get("effective_constraint_applied") is True
    peanut = "\u82b1\u751f"
    titles = [r.get("title") or "" for r in out["recipes"]]
    assert all(peanut not in t for t in titles)
    assert len(out["recipes"]) == 1


def test_merge_effective_constraint_into_memory_patch_writes_memory_state():
    c = {"scope_id": "s", "hard_exclusions": ["egg"]}
    patch_out = _merge_effective_constraint_into_memory_patch({"recipe_state": {}}, c)
    assert patch_out["memory_state"]["effective_constraint"] == c


@pytest.mark.asyncio
async def test_researcher_node_forwards_c_to_search_recipes_and_memory():
    """检索分支：`scope_for_mcp`、`**C**` 与 `memory_state` 一致（T-015）。"""
    lb = make_logistics_buffer(extracted_entities={"recipe_name": "番茄"})
    base = make_minimal_agent_state(logistics_buffer=lb)
    base["messages"] = [HumanMessage(content="想吃番茄炒蛋")]
    base["task_stack"] = ["TASK_SEARCH"]
    base["active_user_id"] = "user_z"

    fake_c = {
        "scope_id": "house_t015",
        "hard_exclusions": ["walnut", "cashew"],
        "temporal_conditions": [],
        "summary_snippet": None,
        "soft_positive_hints": [],
        "soft_negative_hints": [],
        "dietary_target": None,
    }

    mock_rr = MagicMock()
    mock_rr.search_recipes = AsyncMock(
        return_value={
            "recipes": [
                {
                    "title": "番茄炒蛋",
                    "score": 1.0,
                    "id": "egg.md",
                    "source": str(__file__),
                }
            ]
        }
    )
    mock_rr.get_recipe_source = AsyncMock(return_value=str(__file__))
    mock_rr.parse_recipe_content = AsyncMock(
        return_value=StructuredRecipe(title="番茄炒蛋", ingredients=[], steps=[])
    )

    with (
        patch("src.agent.nodes.researcher.build_effective_constraint", return_value=fake_c),
        patch(
            "src.agent.nodes.researcher.augment_search_query",
            side_effect=lambda q, c, s: q,
        ),
        patch("src.agent.nodes.researcher.RecipeResearcher", return_value=mock_rr),
    ):
        out = await researcher_node(base)

    mock_rr.search_recipes.assert_awaited_once()
    kw = mock_rr.search_recipes.await_args.kwargs
    assert kw["effective_constraint"] == fake_c
    assert mock_rr.search_recipes.await_args.args[1] == "house_t015"

    mem = out.get("memory_state") or {}
    assert mem.get("effective_constraint") == fake_c

