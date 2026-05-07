"""
M2 记忆子系统模块间集成验收（板块四 T-009～T-014）。

位置：``tests/integration/``（跨模块串联，非单文件单元测试）。

在既有单测基础上，用少量用例串联：
L3 抽取 → memory_state → build_effective_constraint(**C**) → 检索 query 增强 → 硬排除过滤；
以及 T-013 TTL 清理入口与临时库的接线。

不重复 ``test_conversation_summary_l2`` / ``test_l3_short_term`` / ``test_memory_keeper_t012``
等文件的断言细节；此处侧重跨模块行为一致性与数据流。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agent.effective_constraint import (
    augment_search_query,
    build_effective_constraint,
    filter_recipes_by_hard_exclusions,
)
from src.agent.l3_short_term import augment_query_for_search, build_l3_memory_patch
from src.agent.short_term_ttl import run_short_term_ttl_cleanup
from src.libs.base.user_profiles import UserProfileManager
from tests.conftest import make_minimal_agent_state

PEANUT = "\u82b1\u751f"


def test_m2_pipeline_L3_to_C_to_queries_and_hard_filter():
    """
    T-010 / T-011：用户句 → L3 → **C** → augment_search_query + augment_query_for_search → §5.4。
    """
    state = make_minimal_agent_state()
    state["messages"] = [
        HumanMessage(content=f"\u7259\u75bc\uff0c\u60f3\u5403\u6e05\u6de1\u5c11\u6cb9\u7684\u4e1c\u897f"),  # 牙疼，想吃清淡少油
    ]
    state["active_user_id"] = "integration_user"

    l3_patch = build_l3_memory_patch(state)
    assert "memory_state" in l3_patch
    mem = state.get("memory_state") or {}
    merged_mem = {**mem, **l3_patch["memory_state"]}
    state["memory_state"] = merged_mem
    assert merged_mem.get("short_term_constraints")

    profile = {
        "short_term_states": ["db: fatigue"],
        # 中文菜名需中文关键词命中 §5.4（与英文 peanut 对英文标题对应）
        "allergens": [PEANUT, "shellfish"],
        "medical_restrictions": [],
        "taste_tags": {"like": ["soup"], "dislike": []},
        "disliked_foods": [],
        "dietary_target": "easy digest",
    }
    state["memory_state"]["conversation_summary"] = "User prefers light meals this week."

    c = build_effective_constraint(state, profile=profile, scope_id="house_int")
    assert PEANUT in c["hard_exclusions"]
    assert any("清淡" in x or "牙" in x or "口腔" in x for x in c["temporal_conditions"])
    assert "db: fatigue" in c["temporal_conditions"]

    base_q = "晚餐"
    q_c = augment_search_query(base_q, c, state)
    assert "饮食目标" in q_c or "近期状态" in q_c
    q_full = augment_query_for_search(q_c, state)
    assert "饮食约束" in q_full or base_q in q_full

    recipes = [
        {"title": f"{PEANUT}汤圆", "content": ""},
        {"title": "小米粥", "content": "清淡"},
    ]
    kept = filter_recipes_by_hard_exclusions(recipes, c["hard_exclusions"])
    titles = [r["title"] for r in kept]
    assert f"{PEANUT}汤圆" not in titles
    assert "小米粥" in titles


def test_m2_T013_run_short_term_ttl_cleanup_purges_expired(tmp_path: Path):
    """T-013：`run_short_term_ttl_cleanup` 在配置开启时删除过期短期行。"""
    db = tmp_path / "ttl_m2.db"
    mgr = UserProfileManager(db_path=str(db))
    scope = "scope_ttl_m2"
    mgr.add_short_term_state(scope, "stale_row", ttl_days=1)

    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE user_short_term_states SET expires_at = ? WHERE user_id=?",
        ((datetime.now() - timedelta(days=3)).isoformat(), scope),
    )
    conn.commit()
    conn.close()

    mock_settings = MagicMock()
    mock_settings.should_purge_short_term_expired_on_turn.return_value = True
    mock_settings.get_user_profiles_db_path.return_value = str(db)
    mock_settings.get_scope_id.return_value = scope

    with patch("src.agent.short_term_ttl.Settings", return_value=mock_settings):
        n = run_short_term_ttl_cleanup(scope)

    assert n >= 1
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM user_short_term_states WHERE user_id=?", (scope,))
    cnt = cur.fetchone()[0]
    conn.close()
    assert cnt == 0


def test_m2_T014_long_term_patch_roundtrip_with_chain(tmp_path: Path):
    """T-014：临时库写入长期画像后，get_user_profile 供 **C** 读取 hard_exclusions。"""
    db = tmp_path / "m2_t014.db"
    mgr = UserProfileManager(db_path=str(db))
    uid = "m2_chain_user"
    assert mgr.apply_long_term_patch(
        uid,
        {"allergens": ["walnut", "cashew"]},
        "passive_extract",
    )

    state = make_minimal_agent_state()
    state["active_user_id"] = uid
    state["memory_state"] = {"short_term_constraints": [], "conversation_summary": ""}

    prof = mgr.get_user_profile(uid) or {}
    c = build_effective_constraint(state, profile=prof, scope_id=uid)
    assert "walnut" in c["hard_exclusions"]
    assert "cashew" in c["hard_exclusions"]
