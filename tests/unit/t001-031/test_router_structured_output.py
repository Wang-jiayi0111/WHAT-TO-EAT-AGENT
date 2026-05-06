"""T-004：router 输出 primary_intent / intents / confidence / needs_clarification（FR-01）。"""

from __future__ import annotations

from unittest.mock import patch

from langchain_core.messages import HumanMessage

from src.agent.nodes import router


def _minimal_state(**kwargs):
    base = {
        "messages": [HumanMessage(content="想做红烧肉")],
        "task_stack": [],
        "conversation_summary": "",
        "active_user_id": "u1",
        "logistics_buffer": {
            "extracted_entities": {},
            "router_reasoning": "",
            "recipe_candidates": [],
            "selected_recipe_id": None,
            "recipe_requirements": [],
            "recipe_cook_step": None,
            "inventory_snapshot": [],
            "ingredient_gaps": [],
            "action_metadata": {},
            "pending_tasks": [],
        },
    }
    base.update(kwargs)
    return base


def test_router_emits_fr01_fields_when_classifier_returns_full_detail():
    detail = {
        "intent": "recipe_search",
        "primary_intent": "recipe_search",
        "intents": ["recipe_search", "shopping_list"],
        "secondary_intents": ["shopping_list"],
        "confidence": 0.92,
        "needs_clarification": False,
        "task_stack": ["TASK_SEARCH", "TASK_GAP_CALC"],
        "entities": {"recipe_name": "红烧肉"},
        "slots": {"recipe_name": "红烧肉"},
        "missing_slots": [],
        "reasoning": "用户要找菜并可能要清单",
    }
    with patch.object(router._classifier, "get_intent_details", return_value=detail):
        out = router.router_node(_minimal_state())

    assert out["primary_intent"] == "recipe_search"
    assert out["intents"] == ["recipe_search", "shopping_list"]
    assert out["confidence"] == 0.92
    assert out["needs_clarification"] is False
    assert out["slots"] == {"recipe_name": "红烧肉"}
    assert out["missing_slots"] == []
    assert out["current_intent"] == "recipe_search"


def test_router_skips_llm_when_waiting_clarify():
    with patch.object(router._classifier, "get_intent_details") as m:
        out = router.router_node(_minimal_state(task_stack=["TASK_CLARIFY"]))
        m.assert_not_called()
    assert out == {}


def test_router_empty_messages_returns_safe_defaults():
    out = router.router_node(_minimal_state(messages=[]))
    assert out["primary_intent"] == "general_chat"
    assert out["needs_clarification"] is False
    assert out["confidence"] == 1.0
