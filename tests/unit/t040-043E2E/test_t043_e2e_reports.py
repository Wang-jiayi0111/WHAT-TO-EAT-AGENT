"""T-043：单用例报告 §5.5 链路树、总报告渲染与落盘（docs_root 隔离）。"""

from __future__ import annotations

import json
from pathlib import Path

from eval.e2e_reports import (
    aggregate_efficiency_across_cases,
    build_section_5_5_chain_tree,
    render_per_case_markdown,
    render_run_summary_markdown,
    write_all_t043_artifacts,
)
from eval.scoring import DEFAULT_WEIGHTS, score_capture_payload


def test_build_chain_tree_contains_steps():
    capture = {
        "case_id": "x1",
        "fixture": {
            "scenario_category": "recipe_query",
            "expected": {
                "primary_intent": "recipe_search",
                "key_slots": {"recipe_name": "西红柿鸡蛋"},
                "golden_recipe_ids": ["recipe_id_西红柿炒鸡蛋"],
            },
        },
        "turns": [
            {
                "turn": 1,
                "input": "西红柿鸡蛋怎么做",
                "assistant_reply": "可按以下步骤……",
                "snapshot": {
                    "primary_intent": "recipe_search",
                    "slots": {"recipe_name": "西红柿鸡蛋"},
                    "needs_clarification": False,
                    "expert_payloads": {
                        "search_results": [
                            {"id": "recipe_id_西红柿炒鸡蛋", "title": "西红柿炒鸡蛋"}
                        ]
                    },
                    "recipe_state": {},
                    "runtime_bundle": {},
                },
            }
        ],
    }
    scored = score_capture_payload(capture, use_llm_judge=False)
    tree = build_section_5_5_chain_tree(capture, scored)
    assert "意图识别" in tree
    assert "槽位提取" in tree
    assert "检索调用" in tree
    assert "过滤排序" in tree and "未实现" in tree
    assert "生成回复" in tree
    assert "```text" in tree


def test_write_all_t043_artifacts_tmp_docs(tmp_path: Path):
    run_dir = tmp_path / "eval_unit_t043"
    cap_dir = run_dir / "captures"
    cap_dir.mkdir(parents=True)
    capture = {
        "case_id": "c_mini",
        "source_file": "t.json",
        "fixture": {
            "case_id": "c_mini",
            "scenario_category": "general_chat",
            "expected": {"primary_intent": "general_chat"},
        },
        "turns": [
            {
                "input": "你好",
                "assistant_reply": "您好",
                "snapshot": {"primary_intent": "general_chat", "slots": {}},
            }
        ],
    }
    (cap_dir / "c_mini.json").write_text(
        json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    scored = score_capture_payload(capture, use_llm_judge=False)
    report = {
        "run_dir": str(run_dir),
        "weights": dict(DEFAULT_WEIGHTS),
        "case_count": 1,
        "mean_overall_score": scored["overall_score"],
        "mean_mrr_retrieval": None,
        "cases": [scored],
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {"run_id": run_dir.name, "entries": [{"case_id": "c_mini", "status": "ok"}]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    docs_root = tmp_path / "docs"
    paths = write_all_t043_artifacts(
        run_dir,
        report,
        write_main_agent_eval_report=True,
        docs_root=docs_root,
    )
    case_md = Path(paths["cases_root"]) / "c_mini.md"
    assert case_md.is_file()
    body = case_md.read_text(encoding="utf-8")
    assert "§5.5" in body and "overall" in body
    man = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert man.get("t043", {}).get("scores_json")
    assert (run_dir / "e2e_summary.md").is_file()
    assert (docs_root / "evals" / f"e2e_summary_{run_dir.name}.md").is_file()
    assert (docs_root / "agent_eval_report.md").is_file()
    summary = (run_dir / "e2e_summary.md").read_text(encoding="utf-8")
    assert "§5.4 效率观测汇总" in summary


def test_aggregate_efficiency_and_summary_section():
    scored_ok = {
        "case_id": "a",
        "status": "ok",
        "layers": {
            "efficiency": {
                "metrics": {
                    "total_wall_ms": 100.0,
                    "tokens_total_from_messages": 50,
                    "mcp_inferred_total": 2,
                }
            }
        },
    }
    scored_err = {"case_id": "b", "status": "error", "overall_score": 0.0}
    agg = aggregate_efficiency_across_cases([scored_ok, scored_err])
    assert agg["run_case_count"] == 2
    assert agg["timing_case_count"] == 1
    assert agg["sum_wall_ms"] == 100.0
    assert agg["sum_tokens"] == 50
    assert agg["sum_mcp_inferred"] == 2

    md = render_run_summary_markdown(
        {
            "run_dir": "/tmp",
            "case_count": 2,
            "mean_overall_score": 0.5,
            "mean_mrr_retrieval": None,
            "weights": {"retrieval": 0.35, "generation": 0.325, "dialogue": 0.325},
            "cases": [scored_ok, scored_err],
        },
        run_id="eval_x",
        manifest_path="docs/evals/runs/eval_x/manifest.json",
    )
    assert "§5.4 效率观测汇总" in md
    assert "全 run 墙钟合计" in md
    assert "| `a` |" in md


def test_render_per_case_error_capture():
    capture = {"case_id": "bad", "turns": [], "fixture": {}, "error": "boom"}
    scored = {"case_id": "bad", "status": "error", "error": "boom", "overall_score": 0.0}
    md = render_per_case_markdown(capture, scored)
    assert "boom" in md
    assert "§5.5" in md
