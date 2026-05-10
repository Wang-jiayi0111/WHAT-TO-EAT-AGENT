"""
T-041：E2E 批跑 runner 与 `state_capture`（独立入口 `python -m eval.run_e2e`，非 pytest 主驱动）。

单测仅覆盖可离线验证的：用例加载、过滤、`build_e2e_snapshot` / `extract_assistant_reply`、manifest 结构契约。
全量 Agent 批跑由 CI 或本地显式执行 `python -m eval.run_e2e`。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from eval.runner import (
    RunManifestEntry,
    _case_matches_filter,
    default_cases_dir,
    load_case_files,
    load_cases_from_file,
)
from eval.state_capture import build_e2e_snapshot, extract_assistant_reply
from src.agent.core.state import empty_agent_slices


def test_default_cases_dir_exists():
    d = default_cases_dir()
    assert d.is_dir() and d.name == "cases"


def test_load_case_files_skips_private_prefix(tmp_path: Path):
    (tmp_path / "_skip.json").write_text("[]", encoding="utf-8")
    (tmp_path / "ok.json").write_text("[]", encoding="utf-8")
    files = load_case_files(tmp_path)
    assert [p.name for p in files] == ["ok.json"]


def test_load_cases_from_file_accepts_array(tmp_path: Path):
    p = tmp_path / "t.json"
    p.write_text('[{"case_id": "a", "user_turns": []}]', encoding="utf-8")
    cases = load_cases_from_file(p)
    assert len(cases) == 1 and cases[0]["case_id"] == "a"


def test_load_cases_from_file_rejects_non_array(tmp_path: Path):
    p = tmp_path / "obj.json"
    p.write_text('{"case_id": "x"}', encoding="utf-8")
    with pytest.raises(ValueError, match="数组"):
        load_cases_from_file(p)


def test_case_matches_filter():
    assert _case_matches_filter("recipe_query_001", None) is True
    assert _case_matches_filter("recipe_query_001", "001") is True
    assert _case_matches_filter("recipe_query_001", "zzz") is False


def test_extract_assistant_reply_final_response_wins():
    state = {
        **empty_agent_slices(),
        "final_response": "  direct  ",
        "messages": [HumanMessage(content="h"), AIMessage(content="ignored")],
    }
    assert extract_assistant_reply(state).strip() == "direct"


def test_extract_assistant_reply_from_last_ai():
    state = {
        **empty_agent_slices(),
        "messages": [HumanMessage(content="h"), AIMessage(content="last ai")],
    }
    assert extract_assistant_reply(state) == "last ai"


def test_build_e2e_snapshot_mcp_evidence_search():
    state = {
        **empty_agent_slices(),
        "messages": [],
        "expert_payloads": {"search_results": [{"id": "1"}]},
    }
    snap = build_e2e_snapshot(state)
    assert snap["mcp_evidence"]["inferred_sequence"] == ["search_recipes"]
    assert snap["mcp_evidence"]["inferred_total"] == 1


def test_build_e2e_snapshot_mcp_evidence_parse_chain():
    state = {
        **empty_agent_slices(),
        "messages": [],
        "expert_payloads": {"recipe_detail": {"title": "t"}},
    }
    snap = build_e2e_snapshot(state)
    seq = snap["mcp_evidence"]["inferred_sequence"]
    assert "get_recipe_source" in seq and "parse_recipe_content" in seq


def test_run_manifest_entry_dict_serializable():
    e = RunManifestEntry(
        case_id="c1",
        source_file="f.json",
        status="ok",
        capture_path="docs/evals/runs/r/captures/c1.json",
        duration_ms_total=1.5,
        error=None,
    )
    d = e.__dict__
    assert json.loads(json.dumps(d))["case_id"] == "c1"
