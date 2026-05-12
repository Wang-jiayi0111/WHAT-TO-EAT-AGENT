"""
T-041 独立入口：`python -m eval.run_e2e`（开发计划 §6；非 main、非 pytest 主驱动）。

示例：
  python -m eval.run_e2e --case-filter nutrition_query_005
  python -m eval.run_e2e --cases-dir eval/cases --fail-fast
  python -m eval.run_e2e --cases-dir eval/cases/recipe_search.json
  python -m eval.run_e2e --cases-dir shopping_list.json
（`--cases-dir`：目录；或**单个** `.json` 路径；或**仅文件名**如 `shopping_list.json` → 自动使用 `<项目根>/eval/cases/shopping_list.json`）
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WHAT-TO-EAT-AGENT E2E 批跑（T-041）：采集状态与回复落盘至 docs/evals/runs/<run_id>/"
    )
    parser.add_argument(
        "--cases-dir",
        type=str,
        default=None,
        metavar="DIR_OR_JSON",
        help="用例目录；或单个 .json 路径；或仅文件名如 shopping_list.json（默认目录 <项目根>/eval/cases）",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="运行 ID（默认自动生成 eval_YYYYMMDD_HHMMSS_<suffix>）",
    )
    parser.add_argument(
        "--case-filter",
        type=str,
        default=None,
        help="仅运行 case_id 包含该子串的用例",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="首条失败即停止后续用例",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="default_user",
        help="传入 Agent 的 active_user_id（与 MCP user_id / SCOPE 对齐）",
    )
    args = parser.parse_args()

    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )

    from eval.runner import default_cases_dir, run_suite

    def _resolve_cases_dir_arg(raw: str) -> tuple[Path, list[Path] | None]:
        """返回 (manifest 用的 cases_dir, 若为单文件则 case_files 列表否则 None)。"""
        default_d = default_cases_dir()
        p = Path(raw.strip())
        if p.suffix.lower() != ".json":
            pr = p.resolve()
            if not pr.is_dir():
                raise FileNotFoundError(f"不是有效目录: {pr}")
            return pr, None
        # .json：先试原路径（相对 cwd），再试默认用例目录下的同名文件
        candidates: list[Path] = []
        if p.is_absolute() or len(p.parts) > 1:
            candidates.append(p.resolve())
        else:
            candidates.append((Path.cwd() / p).resolve())
        candidates.append((default_d / p.name).resolve())
        seen: set[Path] = set()
        ordered: list[Path] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        for c in ordered:
            if c.is_file():
                return c.parent, [c]
        raise FileNotFoundError(
            f"未找到用例 JSON（已尝试: {', '.join(str(x) for x in ordered)}）"
        )

    case_files: list[Path] | None = None
    if args.cases_dir is not None:
        try:
            cases_dir, case_files = _resolve_cases_dir_arg(args.cases_dir)
        except FileNotFoundError as e:
            logging.error("%s", e)
            return 2
    else:
        cases_dir = default_cases_dir()

    if not cases_dir.is_dir():
        logging.error("用例目录不存在: %s", cases_dir)
        return 2

    async def _go():
        return await run_suite(
            cases_dir=cases_dir,
            case_files=case_files,
            run_id=args.run_id,
            case_filter=args.case_filter,
            fail_fast=args.fail_fast,
            user_id=args.user_id,
        )

    r = asyncio.run(_go())
    bad = sum(1 for e in r.entries if e.status != "ok")
    logging.info("run_id=%s 完成 条数=%s 失败=%s", r.run_id, len(r.entries), bad)
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(main())
