"""eval/scoring：效率层不入总分、无 LLM 时打分可运行。"""

from __future__ import annotations

from eval.scoring import score_capture_payload, score_efficiency_layer


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
