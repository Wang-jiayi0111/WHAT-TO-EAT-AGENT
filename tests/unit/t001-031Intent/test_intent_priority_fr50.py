"""T-007：FR-50 多意图排序。"""

from src.agent.intent.intent_priority import sort_intents_by_fr50


def test_recipe_search_before_inventory_check():
    assert sort_intents_by_fr50(["inventory_check", "recipe_search"]) == [
        "recipe_search",
        "inventory_check",
    ]


def test_profile_sync_first():
    assert sort_intents_by_fr50(
        ["general_chat", "profile_sync", "recipe_search"]
    ) == ["profile_sync", "recipe_search", "general_chat"]


def test_stable_when_same_tier():
    # help 与 out_of_scope 同秩 90，保持首次出现顺序
    assert sort_intents_by_fr50(["out_of_scope", "help"]) == ["out_of_scope", "help"]
    assert sort_intents_by_fr50(["help", "out_of_scope"]) == ["help", "out_of_scope"]
