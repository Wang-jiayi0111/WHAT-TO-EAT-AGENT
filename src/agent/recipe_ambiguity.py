"""
菜谱检索歧义分支（FR-22；规格 §5.1）：有限候选 + 结构化项，供 generator / clarify_resolver 使用。
"""
from __future__ import annotations

from typing import Any, Dict, List


def build_ambiguity_candidates(recipes: List[Dict[str, Any]], max_n: int) -> List[Dict[str, Any]]:
    """
    取阶段一检索结果的前 max_n 条，按 title 去重，保留 score 与序号。
    """
    if not recipes or max_n < 1:
        return []
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in recipes:
        if len(out) >= max_n:
            break
        title = str(r.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(
            {
                "title": title,
                "score": float(r.get("score") or 0),
                "rank": len(out) + 1,
            }
        )
    return out
