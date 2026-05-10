"""
T-029 / SRS §3.2 / NFR-05：横切验收 smoke。

- **规格 §2（MCP）**：失败包络、search_recipes 成功体仅 id/title/score（与 T-019 一致的最小断言）。
- **规格 §12.2（槽位）**：`GLOBAL_SLOT_ENTITY_KEYS` 稳定；`missing_slots` 对 recipe_search 锚点。
- **S-01～S-08**：以「证据文件」存在性做自动化追溯（深度行为由各专项用例承担）。

运行：`pytest tests/smoke/test_t029_acceptance_smoke.py`（不要求 LLM / MCP 子进程）。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agent.intent.slot_filling import (
    GLOBAL_SLOT_ENTITY_KEYS,
    MISSING_RECIPE_SEARCH_ANCHOR,
    compute_missing_slots,
    merge_slots,
    normalize_legacy_entities_to_slots,
)
from src.mcp.protocol import (
    is_mcp_error_response,
    mcp_validation_error,
    normalize_search_recipe_item,
    normalize_search_recipes_success_body,
)
from src.mcp.tool import SearchRecipesService
from tests.conftest import make_minimal_agent_state

# 与 `docs/开发计划.md` §4 场景最低任务集对齐；变更时请与专项测试路径同步。
_SCENARIO_EVIDENCE_PATHS: dict[str, list[str]] = {
    "S-01": [
        "tests/unit/t009-014Memory/test_l3_short_term.py",
        "tests/unit/t009-014Memory/test_effective_constraint_t011.py",
        "tests/unit/t015-019Recipe/test_t015_retrieval_effective_constraint.py",
    ],
    "S-02": [
        "tests/unit/t001-031Intent/test_workflow_routing_baseline.py",
        "tests/unit/t001-031Intent/test_logistics_silent_gap.py",
        "tests/unit/t015-019Recipe/test_t015_retrieval_effective_constraint.py",
    ],
    "S-03": [
        "tests/unit/t015-019Recipe/test_t016_high_confidence_structured_r.py",
        "tests/unit/t020-024Inventory/test_t020_inventory_snapshot.py",
        "tests/unit/t020-024Inventory/test_t023_gap_cache.py",
        "tests/unit/t020-024Inventory/test_t024_shopping_list_overlay.py",
    ],
    "S-04": [
        "tests/unit/t020-024Inventory/test_t020_inventory_snapshot.py",
        "tests/unit/t025-026Reply/test_t025_section9_generator_messages.py",
    ],
    "S-05": [
        "tests/unit/t001-031Intent/test_intent_priority_fr50.py",
        "tests/unit/t001-031Intent/test_generator_merged_replies.py",
    ],
    "S-06": ["tests/unit/t015-019Recipe/test_t017_recipe_ambiguity_clarify.py"],
    "S-07": [
        "tests/unit/t009-014Memory/test_memory_keeper_t012.py",
        "tests/unit/t009-014Memory/test_user_profiles_t014_long_term.py",
        "tests/unit/t015-019Recipe/test_t015_retrieval_effective_constraint.py",
    ],
    "S-08": [
        "tests/unit/t020-024Inventory/test_t023_gap_cache.py",
        "tests/unit/t020-024Inventory/test_t024_shopping_list_overlay.py",
    ],
}

pytestmark = pytest.mark.acceptance_smoke

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_section2_validation_error_envelope():
    e = mcp_validation_error("bad")
    assert e["status"] == "error" and "error" in e
    assert json.loads(json.dumps(e)) == e


def test_mcp_section2_is_error_heuristic():
    assert is_mcp_error_response(mcp_validation_error("x")) is True
    assert is_mcp_error_response({"recipes": [], "query_used": "q"}) is False


def test_mcp_section2_normalize_item_public_fields_only():
    raw = {"id": 1, "title": " 蛋 ", "score": 0.3, "content": "x"}
    out = normalize_search_recipe_item(raw)
    assert set(out) == {"id", "title", "score"}


def test_mcp_section2_success_body_shape():
    body = normalize_search_recipes_success_body(
        [{"id": "a", "title": "A", "score": 0.9}], "q1"
    )
    assert "recipes" in body and "query_used" in body
    assert set(body["recipes"][0]) == {"id", "title", "score"}


@pytest.mark.asyncio
async def test_mcp_section2_search_service_rejects_blank_query():
    svc = SearchRecipesService(MagicMock(), MagicMock())
    out = await svc.execute("  \t", user_id="u")
    assert is_mcp_error_response(out)


def test_slot_section12_global_entity_keys_stable():
    """与 `src/agent/intent/slot_filling.py` §12.2 表一致；增删键须同步改此处期望数。"""
    assert "list_action" in GLOBAL_SLOT_ENTITY_KEYS
    assert "mark_bought_items" in GLOBAL_SLOT_ENTITY_KEYS
    assert len(GLOBAL_SLOT_ENTITY_KEYS) == 15


def test_slot_section12_normalize_preserves_mark_bought():
    slots = normalize_legacy_entities_to_slots(
        {"mark_bought_items": ["鸡蛋"], "list_action": "mark_bought"},
        ["shopping_list"],
    )
    assert slots.get("mark_bought_items") == ["鸡蛋"]
    assert slots.get("list_action") == "mark_bought"


def test_slot_section12_merge_slots_override():
    base = {"recipe_query": "a", "list_action": "show"}
    out = merge_slots(base, {"list_action": "refresh_gap"})
    assert out["recipe_query"] == "a" and out["list_action"] == "refresh_gap"


def test_slot_section12_missing_recipe_search_anchor():
    st = make_minimal_agent_state()
    miss = compute_missing_slots(["recipe_search"], {}, st)
    assert MISSING_RECIPE_SEARCH_ANCHOR in miss
    miss_ok = compute_missing_slots(
        ["recipe_search"], {"recipe_query": "低脂"}, st
    )
    assert MISSING_RECIPE_SEARCH_ANCHOR not in miss_ok


# ── S-01～S-08：证据文件（与 `docs/开发计划.md` §4 最低任务集对齐）────────────────


def _assert_evidence(paths: list[str]) -> None:
    for rel in paths:
        p = _REPO_ROOT / Path(rel)
        assert p.is_file(), f"验收追溯文件缺失: {rel}"


@pytest.mark.parametrize(
    "scenario_id, evidence_files",
    list(sorted(_SCENARIO_EVIDENCE_PATHS.items())),
)
def test_scenario_evidence_registry(scenario_id: str, evidence_files: list[str]) -> None:
    """NFR-05：场景与专项测试文件的追溯关系可自动化校验。"""
    _assert_evidence(evidence_files)
