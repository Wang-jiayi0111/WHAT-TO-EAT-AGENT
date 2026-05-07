"""
T-019 / IR-02 / 规格 §2：MCP JSON 契约、校验错误包络、成功体字段归一。

不导入 `src.mcp.server`（避免拉起 RAG/Chroma）；`handle_call_tool` 的 query / recipe_name
校验逻辑与 `SearchRecipesService.execute`、`RecipeSourceService.execute` 对齐单测。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.mcp.protocol import (
    is_mcp_error_response,
    mcp_validation_error,
    normalize_search_recipe_item,
    normalize_search_recipes_success_body,
)
from src.mcp.tool import RecipeSourceService, SearchRecipesService


def test_mcp_validation_error_shape():
    e = mcp_validation_error("bad arg")
    assert e == {"status": "error", "error": "bad arg"}
    assert json.loads(json.dumps(e)) == e


@pytest.mark.parametrize(
    "parsed,expect_err",
    [
        (None, False),
        ("path/string", False),
        ({"status": "error", "error": "x"}, True),
        (mcp_validation_error("q"), True),
        ({"recipes": [], "query_used": "a"}, False),
        ({"recipes": [{"id": "1", "title": "t", "score": 0.1}]}, False),
        ({"error": "upstream"}, True),
        ({"foo": 1}, False),
    ],
)
def test_is_mcp_error_response(parsed, expect_err):
    assert is_mcp_error_response(parsed) is expect_err


def test_normalize_search_recipe_item_only_public_fields():
    raw = {
        "id": 99,
        "title": "  红烧肉  ",
        "score": "0.5",
        "content": "secret",
        "source": "/x.md",
    }
    out = normalize_search_recipe_item(raw)
    assert set(out) == {"id", "title", "score"}
    assert out["id"] == "99"
    assert out["title"] == "红烧肉"
    assert out["score"] == 0.5
    assert "content" not in out


def test_normalize_search_recipes_success_body_optional_flag():
    body = normalize_search_recipes_success_body(
        [{"id": "a", "title": "A", "score": 1}],
        "  q  ",
        effective_constraint_applied=True,
    )
    assert body["query_used"] == "q"
    assert body["effective_constraint_applied"] is True
    assert len(body["recipes"]) == 1


@pytest.mark.asyncio
async def test_search_recipes_service_execute_rejects_empty_query():
    svc = SearchRecipesService(MagicMock(), MagicMock())
    out = await svc.execute("   ", user_id="u")
    assert is_mcp_error_response(out)
    assert "query" in out["error"].lower() or "empty" in out["error"].lower()


@pytest.mark.asyncio
async def test_search_recipes_service_default_top_k_is_five():
    rag = MagicMock()
    rag.get_detailed_results.return_value = {"results": []}
    upm = MagicMock()
    upm.get_user_profile.return_value = None
    svc = SearchRecipesService(rag, upm)
    await svc.execute("鸡蛋", user_id="u")
    rag.get_detailed_results.assert_called_once()
    assert rag.get_detailed_results.call_args[1]["top_k"] == 5


@pytest.mark.asyncio
async def test_search_recipes_service_success_recipes_only_id_title_score():
    rag = MagicMock()
    rag.get_detailed_results.return_value = {
        "results": [
            {
                "id": "doc1",
                "content": "body",
                "metadata": {"recipe_name": "公开菜名"},
                "score": 0.88,
            }
        ]
    }
    upm = MagicMock()
    upm.get_user_profile.return_value = None
    svc = SearchRecipesService(rag, upm)
    out = await svc.execute("找菜", user_id="u", top_k=3)
    assert not is_mcp_error_response(out)
    assert "query_used" in out
    r0 = out["recipes"][0]
    assert set(r0.keys()) == {"id", "title", "score"}
    assert r0["title"] == "公开菜名"


@pytest.mark.asyncio
async def test_search_recipes_service_with_effective_constraint_no_content_in_output():
    rag = MagicMock()
    rag.get_detailed_results.return_value = {
        "results": [
            {
                "id": "1",
                "content": "花生汤",
                "metadata": {"recipe_name": "花生甜汤"},
                "score": 0.9,
            },
            {
                "id": "2",
                "content": "白粥",
                "metadata": {"recipe_name": "白粥"},
                "score": 0.8,
            },
        ]
    }
    upm = MagicMock()
    upm.get_user_profile.return_value = None
    svc = SearchRecipesService(rag, upm)
    c = {"hard_exclusions": ["\u82b1\u751f"]}  # 花生
    out = await svc.execute("甜品", user_id="u", effective_constraint=c)
    assert out.get("effective_constraint_applied") is True
    for item in out["recipes"]:
        assert "content" not in item
        assert set(item.keys()) == {"id", "title", "score"}


@pytest.mark.asyncio
async def test_recipe_source_service_empty_name_raises():
    dm = MagicMock()
    svc = RecipeSourceService(dm)
    with pytest.raises(ValueError, match="recipe_name"):
        await svc.execute("")


@pytest.mark.asyncio
async def test_recipe_source_service_returns_optional_path():
    dm = MagicMock()
    dm.get_source_by_name.return_value = "/data/recipes/a.md"
    svc = RecipeSourceService(dm)
    path = await svc.execute("  糖醋排骨  ")
    assert path == "/data/recipes/a.md"
    dm.get_source_by_name.assert_called_once_with("糖醋排骨")
