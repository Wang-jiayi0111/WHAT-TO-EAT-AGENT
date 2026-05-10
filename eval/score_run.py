"""
T-042：对已落盘的 E2E run（`docs/evals/runs/<run_id>/captures/*.json`）计算分层指标与总分。

用法：
  python -m eval.score_run --run-dir docs/evals/runs/<run_id>
  python -m eval.score_run --run-id eval_20260510_120000_ab12cd34

产出（默认同 run 目录）：
  - scores.json：机器可读全量
  - scores_report.md：人类易读摘要（可用 --no-report-md 关闭）
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def default_runs_root() -> Path:
    return _ROOT / "docs" / "evals" / "runs"


def resolve_run_dir(run_id_or_path: str) -> Path:
    p = Path(run_id_or_path)
    if p.is_dir():
        return p.resolve()
    return (default_runs_root() / run_id_or_path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="T-042：E2E 分层打分（§5.1～5.4 + §5.6）"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="run 目录（含 captures/），默认由 --run-id 推导",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="run_id（对应 docs/evals/runs/<run_id>）",
    )
    parser.add_argument(
        "--no-retrieval-hard-fail",
        action="store_true",
        help="禁用「检索必达且无召回」时的总分封顶（§5.6）",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="同时将摘要写入 docs/evals/latest_eval.json",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="禁用 LLM 四维评测；生成层幻觉回退启发式，对话层回退规则澄清对齐",
    )
    parser.add_argument(
        "--no-report-md",
        action="store_true",
        help="不生成易读 Markdown（默认写入 run 目录下 scores_report.md）",
    )
    args = parser.parse_args()

    if not logging.root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    elif args.run_id:
        run_dir = resolve_run_dir(args.run_id)
    else:
        logging.error("请指定 --run-dir 或 --run-id")
        return 2

    from eval.scoring import DEFAULT_WEIGHTS, render_scores_markdown, score_run_directory

    try:
        report = score_run_directory(
            run_dir,
            weights=DEFAULT_WEIGHTS,
            retrieval_must_hit=not args.no_retrieval_hard_fail,
            use_llm_judge=not args.no_llm,
        )
    except FileNotFoundError as e:
        logging.error("%s", e)
        return 2

    out_path = run_dir / "scores.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("已写入 %s  mean_overall=%s", out_path, report.get("mean_overall_score"))

    if not args.no_report_md:
        md_path = run_dir / "scores_report.md"
        md_path.write_text(render_scores_markdown(report), encoding="utf-8")
        logging.info("已写入易读报告 %s", md_path)

    if args.latest:
        latest = _ROOT / "docs" / "evals" / "latest_eval.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        slim = {
            "run_dir": report["run_dir"],
            "mean_overall_score": report["mean_overall_score"],
            "mean_mrr_retrieval": report.get("mean_mrr_retrieval"),
            "case_count": report["case_count"],
        }
        latest.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info("已写入 %s", latest)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
