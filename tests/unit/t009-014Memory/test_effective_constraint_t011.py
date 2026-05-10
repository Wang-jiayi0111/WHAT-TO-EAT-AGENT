"""T-011: effective_constraint C merge, search query augment, hard filter (spec 5.4)."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agent.memory.effective_constraint import (
    augment_search_query,
    build_effective_constraint,
    filter_recipes_by_hard_exclusions,
    resolve_scope_id,
)

# Unicode escapes keep tests stable if source file encoding varies on Windows.
PEANUT = "\u82b1\u751f"  # 花生
TOMATO_EGG = "\u756a\u8304\u7092\u86cb"  # 番茄炒蛋


def test_resolve_scope_id_prefers_household_default():
    settings = MagicMock()
    settings.get_scope_id.return_value = "household_01"
    assert resolve_scope_id({"active_user_id": "user_x"}, settings) == "household_01"
    settings.get_scope_id.assert_called_once_with("user_x")


def test_resolve_scope_id_falls_back_active_user():
    settings = MagicMock()
    settings.get_scope_id.side_effect = lambda fb: fb
    assert resolve_scope_id({"active_user_id": "alice"}, settings) == "alice"


def test_build_effective_constraint_merges_profile_l3_summary():
    """Inject profile to avoid DB; allergens use len>=2 strings (min_len=2 in code)."""
    state = {
        "active_user_id": "u1",
        "memory_state": {
            "short_term_constraints": ["temporal: cold"],
            "conversation_summary": "summary padding " * 40,
        },
    }
    profile = {
        "short_term_states": ["toothache"],
        "allergens": ["peanut", "shellfish"],
        "medical_restrictions": [],
        "taste_tags": {"like": ["mild"], "dislike": ["cilantro"]},
        "disliked_foods": ["celery"],
        "dietary_target": "low sugar",
    }
    c = build_effective_constraint(state, profile=profile, scope_id="scope_test")

    assert c["scope_id"] == "scope_test"
    assert "peanut" in c["hard_exclusions"]
    assert "shellfish" in c["hard_exclusions"]
    assert "temporal: cold" in c["temporal_conditions"]
    assert "toothache" in c["temporal_conditions"]
    assert "mild" in c["soft_positive_hints"]
    assert "cilantro" in c["soft_negative_hints"]
    assert "celery" in c["soft_negative_hints"]
    assert c["dietary_target"] == "low sugar"
    assert c["summary_snippet"] is not None
    assert len(c["summary_snippet"]) <= 502
    assert c["summary_snippet"].endswith("\u2026") or c["summary_snippet"].endswith("...")


def test_build_effective_constraint_summary_no_ellipsis_when_short():
    state = {
        "memory_state": {"conversation_summary": "short", "short_term_constraints": []},
    }
    c = build_effective_constraint(state, profile={}, scope_id="s")
    assert c["summary_snippet"] == "short"


def test_build_effective_constraint_empty_profile_minimal():
    state = {"active_user_id": "u1", "memory_state": {}}
    c = build_effective_constraint(state, profile={}, scope_id="s")
    assert c["hard_exclusions"] == []
    assert c["temporal_conditions"] == []
    assert c["summary_snippet"] is None


def test_augment_search_query_injects_c_and_active_constraints():
    c = {
        "dietary_target": "low salt",
        "soft_positive_hints": ["fish"],
        "soft_negative_hints": ["offal"],
        "temporal_conditions": ["upset stomach"],
        "hard_exclusions": ["shellfish"],
        "summary_snippet": "prefer light meals",
    }
    state = {"active_constraints": {"meal": "dinner"}}
    q = augment_search_query("steamed fish", c, state)
    assert "steamed fish" in q
    assert "[饮食约束]" in q or "constraint" in q.lower()
    assert "low salt" in q
    assert "dinner" in q


def test_augment_search_query_empty_base():
    c = {"temporal_conditions": ["cold"], "hard_exclusions": [], "soft_positive_hints": []}
    q = augment_search_query("", c, {})
    assert "[饮食约束]" in q
    assert "cold" in q


def test_filter_recipes_by_hard_exclusions_chinese_keyword():
    recipes = [
        {"title": PEANUT + "\u788e\u62cc\u83e0\u83dc", "content": ""},
        {"title": TOMATO_EGG, "content": ""},
    ]
    kept = filter_recipes_by_hard_exclusions(recipes, [PEANUT])
    assert len(kept) == 1
    assert kept[0]["title"] == TOMATO_EGG


def test_filter_recipes_by_hard_exclusions_ascii_case_insensitive():
    recipes = [
        {"title": "Peanut Butter Cookies", "snippet": "dessert"},
        {"title": "Plain Rice", "content": "side"},
    ]
    kept = filter_recipes_by_hard_exclusions(recipes, ["peanut"])
    assert len(kept) == 1
    assert "Rice" in kept[0]["title"]


def test_filter_recipes_no_exclusions_returns_shallow_equal():
    recipes = [{"title": "A"}]
    assert filter_recipes_by_hard_exclusions(recipes, []) == recipes
    assert filter_recipes_by_hard_exclusions([], [PEANUT]) == []
