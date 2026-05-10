"""
T-041：逐条加载 `eval/cases/*.json`，按多轮 `user_turns` 调用 `create_agent` + `ainvoke`，
落盘 §5.0 步骤 2 所需原始量（检索侧证据在 `expert_payloads` / `runtime_bundle`，**R** 在 `recipe_state` 与 `recipe_detail`）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 保证 `python -m eval.run_e2e` 在未 editable 安装时仍可 import `src.*`
_ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.messages import HumanMessage  # noqa: E402

from src.agent.core.state import empty_agent_slices  # noqa: E402
from src.agent.workflow import create_agent  # noqa: E402
from src.libs.base.config_startup_check import run_startup_configuration_check  # noqa: E402
from src.libs.base.settings import Settings  # noqa: E402
from src.observability.runtime_context import bind_invocation_session  # noqa: E402

from .state_capture import build_e2e_snapshot  # noqa: E402

logger = logging.getLogger(__name__)


def default_cases_dir() -> Path:
    return _ROOT / "eval" / "cases"


def default_runs_dir() -> Path:
    return _ROOT / "docs" / "evals" / "runs"


def load_case_files(cases_dir: Path) -> List[Path]:
    out: List[Path] = []
    for p in sorted(cases_dir.glob("*.json")):
        if p.name.startswith("_") or p.name.upper().startswith("QA"):
            continue
        out.append(p)
    return out


def load_cases_from_file(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"用例文件须为 JSON 数组: {path}")
    return data


@dataclass
class RunManifestEntry:
    case_id: str
    source_file: str
    status: str
    capture_path: str
    duration_ms_total: float
    error: Optional[str] = None


@dataclass
class RunResult:
    run_id: str
    entries: List[RunManifestEntry] = field(default_factory=list)


async def _invoke_one_turn(
    agent: Any,
    user_message: str,
    thread_id: str,
    user_id: str,
) -> Tuple[Dict[str, Any], float]:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        current = await agent.aget_state(config)
        existing = current.values.get("messages", [])
        conv_summary = (
            current.values.get("conversation_summary", "") if existing else ""
        )
    except Exception:
        existing = []
        conv_summary = ""

    input_state = {
        **empty_agent_slices(),
        "messages": [HumanMessage(content=user_message)],
        "active_user_id": user_id,
        "conversation_summary": conv_summary,
    }

    t0 = time.perf_counter()
    with bind_invocation_session(thread_id):
        await agent.ainvoke(input_state, config)
    wall_ms = (time.perf_counter() - t0) * 1000.0

    final = await agent.aget_state(config)
    snap = build_e2e_snapshot(dict(final.values))
    snap["wall_time_ms"] = wall_ms
    snap["user_input"] = user_message
    return snap, wall_ms


def _case_matches_filter(case_id: str, case_filter: Optional[str]) -> bool:
    if not case_filter:
        return True
    return case_filter in case_id


async def run_single_case(
    agent: Any,
    case: Dict[str, Any],
    source_file: str,
    thread_id: str,
    user_id: str = "default_user",
) -> Dict[str, Any]:
    turns_out: List[Dict[str, Any]] = []
    total_ms = 0.0
    for ut in case.get("user_turns") or []:
        inp = ut.get("input", "")
        snap, wms = await _invoke_one_turn(agent, str(inp), thread_id, user_id)
        total_ms += wms
        turns_out.append(
            {
                "turn": ut.get("turn"),
                "input": inp,
                "wall_time_ms": wms,
                "snapshot": snap,
                "assistant_reply": str(snap.get("final_response") or "").strip(),
            }
        )
    return {
        "case_id": case.get("case_id"),
        "source_file": source_file,
        "fixture": case,
        "thread_id": thread_id,
        "turns": turns_out,
        "aggregate": {"total_wall_ms": total_ms, "turn_count": len(turns_out)},
    }


async def run_suite(
    *,
    cases_dir: Optional[Path] = None,
    run_id: Optional[str] = None,
    case_filter: Optional[str] = None,
    fail_fast: bool = False,
    user_id: str = "default_user",
) -> RunResult:
    cases_dir = cases_dir or default_cases_dir()
    rid = run_id or f"eval_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    out_dir = default_runs_dir() / rid
    cap_dir = out_dir / "captures"
    out_dir.mkdir(parents=True, exist_ok=True)
    cap_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings()
    if not run_startup_configuration_check(settings):
        raise RuntimeError("配置自检未通过（与 main 一致），请检查 setting.yaml 与日志。")

    agent = create_agent(persist=True)
    result = RunResult(run_id=rid)

    abort_suite = False
    for fp in load_case_files(cases_dir):
        if abort_suite:
            break
        for case in load_cases_from_file(fp):
            cid = str(case.get("case_id") or "")
            if not cid:
                continue
            if not _case_matches_filter(cid, case_filter):
                continue
            t_case0 = time.perf_counter()
            err: Optional[str] = None
            status = "ok"
            capture_rel = f"docs/evals/runs/{rid}/captures/{cid}.json"
            try:
                thread_id = f"{rid}:{cid}"
                payload = await run_single_case(
                    agent, case, fp.name, thread_id=thread_id, user_id=user_id
                )
                (cap_dir / f"{cid}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                status = "error"
                logger.exception("用例失败 case_id=%s", cid)
                (cap_dir / f"{cid}.json").write_text(
                    json.dumps(
                        {
                            "case_id": cid,
                            "source_file": fp.name,
                            "fixture": case,
                            "error": err,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            duration_ms = (time.perf_counter() - t_case0) * 1000.0
            result.entries.append(
                RunManifestEntry(
                    case_id=cid,
                    source_file=fp.name,
                    status=status,
                    capture_path=capture_rel,
                    duration_ms_total=duration_ms,
                    error=err,
                )
            )
            if fail_fast and status == "error":
                abort_suite = True
                break

    manifest = {
        "run_id": rid,
        "cases_dir": str(cases_dir.resolve()),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "entries": [e.__dict__ for e in result.entries],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("T-041 run 完成 run_id=%s 用例数=%s 输出=%s", rid, len(result.entries), out_dir)
    return result


def run_suite_sync(**kwargs: Any) -> RunResult:
    return asyncio.run(run_suite(**kwargs))
