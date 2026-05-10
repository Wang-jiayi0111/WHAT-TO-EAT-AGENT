"""
多意图仲裁优先级（FR-50；规格 §12.4 与 `intents` 有序列表一致）。

规则（SRS）：安全/硬约束 > 定菜决策 > 库存动作 > 解释闲聊。

实现：为每个意图标签赋予数值秩（越小越优先）；同秩保持模型原始顺序（稳定排序）。
"""

from __future__ import annotations

from typing import Dict, List

# 秩分组：0 画像/禁忌；10～19 定菜与清单；30～39 库存侧；80+ 元意图与闲聊
FR50_INTENT_RANK: Dict[str, int] = {
    "profile_sync": 0,
    "recipe_search": 10,
    "recipe_adopt": 11,
    "shopping_list": 12,
    "inventory_check": 30,
    "inventory_add": 31,
    "inventory_commit": 32,
    "dietary_advice": 80,
    "help": 90,
    "out_of_scope": 90,
    "general_chat": 91,
}

_DEFAULT_RANK = 50


def sort_intents_by_fr50(intents: List[str]) -> List[str]:
    """
    按 FR-50 对意图标签重排；未知标签落在默认秩，同秩按首次出现顺序稳定排序。
    """
    if not intents:
        return []
    indexed = list(enumerate(intents))
    indexed.sort(
        key=lambda item: (FR50_INTENT_RANK.get(item[1], _DEFAULT_RANK), item[0])
    )
    return [intent for _, intent in indexed]
