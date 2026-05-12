"""eval/scoring：效率层不入总分、无 LLM 时打分可运行。"""

from __future__ import annotations

from eval.scoring import (
    compute_intent_alignment_score,
    score_capture_payload,
    score_dialogue_layer,
    score_efficiency_layer,
    score_retrieval_layer,
    score_shopping_list_ops_layer,
)


def test_efficiency_layer_no_aggregate_score():
    turns = [{"wall_time_ms": 100.0, "snapshot": {"mcp_evidence": {"inferred_total": 2}}}]
    e = score_efficiency_layer(turns)
    assert e["aggregate_score"] is None
    assert e["metrics"]["total_wall_ms"] == 100.0
    assert e["metrics"]["mcp_inferred_total"] == 2


def test_score_capture_without_llm_minimal():
    payload = {
        "case_id": "t",
        "fixture": {
            "expected": {
                "primary_intent": "recipe_search",
                "golden_recipe_ids": ["recipe_id_西红柿炒鸡蛋"],
            },
        },
        "turns": [
            {
                "assistant_reply": "西红柿",
                "snapshot": {
                    "primary_intent": "recipe_search",
                    "expert_payloads": {
                        "search_results": [
                            {"id": "recipe_id_西红柿炒鸡蛋", "title": "西红柿炒鸡蛋"}
                        ]
                    },
                    "recipe_state": {},
                },
            }
        ],
    }
    r = score_capture_payload(payload, use_llm_judge=False)
    assert r["status"] == "ok"
    assert r["layers"]["efficiency"]["aggregate_score"] is None
    assert "efficiency" not in r["weight_detail"] or all(
        k != "efficiency" for k in r["weight_detail"]
    )
    assert "llm_judge" not in r


def test_retrieval_recall_or_and_top1_accuracy():
    """golden_recipe_ids：召回=任一命中；准确率=Top-1 是否为金标之一。"""
    expected = {"golden_recipe_ids": ["recipe_id_A菜", "recipe_id_B菜"]}
    turns = [
        {
            "snapshot": {
                "expert_payloads": {
                    "search_results": [
                        {"id": "x", "title": "无关标题"},
                        {"id": "y", "title": "B菜家常做法"},
                    ]
                },
                "recipe_state": {},
            }
        }
    ]
    layer = score_retrieval_layer(expected, turns, retrieval_must_hit=True)
    assert layer["hard_fail"] is False
    rr = layer["submetrics"]["retrieval_recall"]["score"]
    assert rr == 1.0
    ta = layer["submetrics"]["retrieval_accuracy_top1"]["score"]
    assert ta == 0.0


def test_shopping_list_ops_overlay_remove():
    expected = {
        "shopping_list_assert": {
            "overlay_remove_keys_contain": ["青椒"],
            "overlay_ops_min": 1,
        }
    }
    turns = [
        {
            "snapshot": {
                "inventory_state": {
                    "shopping_list_overlay": [
                        {"op": "remove", "key": "青椒"},
                    ],
                    "cached_shopping_gap": {"shopping_list": []},
                }
            }
        }
    ]
    layer = score_shopping_list_ops_layer(expected, turns)
    assert layer["aggregate_score"] == 1.0


def test_shopping_list_ops_no_inventory_state_fails():
    expected = {"shopping_list_assert": {"gap_cache_present": True}}
    turns = [{"snapshot": {}}]
    layer = score_shopping_list_ops_layer(expected, turns)
    assert layer["aggregate_score"] == 0.0


def test_retrieval_top1_accuracy_when_first_is_golden():
    expected = {"golden_recipe_ids": ["recipe_id_西红柿炒鸡蛋"]}
    turns = [
        {
            "snapshot": {
                "expert_payloads": {
                    "search_results": [{"id": "recipe_id_西红柿炒鸡蛋", "title": "西红柿炒鸡蛋"}]
                },
                "recipe_state": {},
            }
        }
    ]
    layer = score_retrieval_layer(expected, turns, retrieval_must_hit=True)
    assert layer["submetrics"]["retrieval_accuracy_top1"]["score"] == 1.0
    assert layer["submetrics"]["retrieval_recall"]["score"] == 1.0


def test_compute_intent_alignment_primary_only():
    expected = {"primary_intent": "recipe_search"}
    snap = {"primary_intent": "recipe_search", "intents": ["recipe_search", "dietary_advice"]}
    s, d = compute_intent_alignment_score(expected, snap)
    assert s == 1.0
    assert d.get("primary_match") == 1.0


def test_compute_intent_alignment_multi_subset_order_free():
    expected = {"intents": ["recipe_adopt", "recipe_search"]}
    snap = {"intents": ["recipe_search", "recipe_adopt", "general_chat"]}
    s, d = compute_intent_alignment_score(expected, snap)
    assert s == 1.0
    assert d["intents_subset_recall"] == 1.0


def test_compute_intent_alignment_partial_multi_recall():
    expected = {"intents": ["recipe_adopt", "recipe_search"]}
    snap = {"intents": ["recipe_adopt"]}
    s, d = compute_intent_alignment_score(expected, snap)
    assert abs(d["intents_subset_recall"] - 0.5) < 1e-9
    assert abs(s - 0.5) < 1e-9


def test_compute_intent_alignment_primary_and_multi_averaged():
    expected = {"primary_intent": "recipe_adopt", "intents": ["recipe_adopt", "recipe_search"]}
    snap_wrong_primary = {
        "primary_intent": "recipe_search",
        "intents": ["recipe_search", "recipe_adopt"],
    }
    s2, _ = compute_intent_alignment_score(expected, snap_wrong_primary)
    assert abs(s2 - 0.5) < 1e-9


def test_score_dialogue_layer_intent_match_with_intents():
    expected = {
        "primary_intent": "recipe_adopt",
        "intents": ["recipe_adopt", "recipe_search"],
        "needs_clarification": False,
    }
    turns = [
        {
            "snapshot": {
                "primary_intent": "recipe_adopt",
                "intents": ["recipe_search", "recipe_adopt", "general_chat"],
                "needs_clarification": False,
            }
        }
    ]
    layer = score_dialogue_layer(expected, turns, llm_bundle=None)
    im = layer["submetrics"]["intent_match"]
    assert im["status"] == "ok"
    assert im["score"] >= 0.99
