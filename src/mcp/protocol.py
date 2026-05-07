"""
MCP 菜谱工具 JSON 契约（规格 §2；IR-02 / T-019）。

成功 / 失败分支与 Agent 解析约定见 `docs/规格设计.md` §2.2～2.4。
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


def mcp_validation_error(message: str) -> Dict[str, Any]:
    """§2.4：失败响应须含 `status`=`error` 与可读 `error` 文案。"""
    return {"status": "error", "error": message}


def is_mcp_error_response(parsed: Any) -> bool:
    """
    Agent 侧分支：解析 JSON 后的对象是否为失败包络。
    - `search_recipes` 成功体必含 `recipes`（可为空列表）。
    - `get_recipe_source` 成功为 JSON 字符串或 `null`，非 dict。
    """
    if not isinstance(parsed, dict):
        return False
    if parsed.get("status") == "error":
        return True
    if "recipes" in parsed:
        return False
    if parsed.get("error") is not None:
        return True
    return False


def normalize_search_recipe_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    """§2.2：对外仅暴露 `id` / `title` / `score`（禁止向 Agent 泄露全文 content）。"""
    try:
        score = float(item.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("title") or "").strip(),
        "score": score,
    }


def normalize_search_recipes_success_body(
    recipes: List[Dict[str, Any]],
    query_used: str,
    *,
    effective_constraint_applied: Optional[bool] = None,
) -> Dict[str, Any]:
    """§2.2 逻辑结构 + T-015 扩展字段 `effective_constraint_applied`（可选）。"""
    body: Dict[str, Any] = {
        "recipes": [normalize_search_recipe_item(x) for x in recipes],
        "query_used": (query_used or "").strip(),
    }
    if effective_constraint_applied is not None:
        body["effective_constraint_applied"] = bool(effective_constraint_applied)
    return body
