"""T-010 / FR-17 / §4.3：L3 当轮约束抽取、合并与检索 query 增强。"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.memory.l3_short_term import (
    augment_query_for_search,
    build_l3_memory_patch,
    extract_short_term_lines,
    latest_user_text,
    merge_short_term_constraints,
)
from src.agent.nodes.short_term import short_term_constraints_node
from tests.conftest import make_minimal_agent_state


def test_extract_short_term_cold():
    lines = extract_short_term_lines("我这两天感冒了，想吃点清淡的")
    assert any("感冒" in x for x in lines)
    assert any("清淡" in x for x in lines)


def test_merge_short_term_dedup_order():
    a = ["短期：A", "短期：B"]
    b = ["短期：B", "短期：C"]
    assert merge_short_term_constraints(a, b) == ["短期：A", "短期：B", "短期：C"]


def test_latest_user_text_skips_ai():
    msgs = [HumanMessage("第一句"), AIMessage("助手"), HumanMessage("最后一句")]
    assert latest_user_text(msgs) == "最后一句"


def test_build_l3_memory_patch_appends_constraints():
    state = make_minimal_agent_state()
    state["messages"] = [HumanMessage("感冒了吃点啥")]
    state["memory_state"] = {}
    patch = build_l3_memory_patch(state)
    assert "memory_state" in patch
    st = patch["memory_state"]["short_term_constraints"]
    assert isinstance(st, list) and len(st) >= 1
    assert patch["memory_state"].get("memory_confidence") == 0.85


def test_build_l3_memory_patch_no_change_returns_empty():
    state = make_minimal_agent_state()
    state["messages"] = [HumanMessage("嗯")]
    state["memory_state"] = {}
    # 「嗯」不命中任何关键词 → new_lines 空，merged == prior 空 → {}
    assert build_l3_memory_patch(state) == {}


@pytest.mark.asyncio
async def test_short_term_node_returns_same_as_patch_builder():
    state = make_minimal_agent_state()
    state["messages"] = [HumanMessage("拉肚子别吃刺激的")]
    out = await short_term_constraints_node(state)
    assert out == build_l3_memory_patch(state)


def test_augment_query_appends_short_term_and_active_constraints():
    state = make_minimal_agent_state()
    state["memory_state"] = {"short_term_constraints": ["短期：肠胃不适"]}
    state["active_constraints"] = {"allergy": "花生"}
    q = augment_query_for_search("红烧肉", state)
    assert "红烧肉" in q
    assert "[饮食约束]" in q
    assert "肠胃" in q or "短期" in q
    assert "花生" in q


def test_augment_query_empty_base_uses_constraint_only():
    state = make_minimal_agent_state()
    state["memory_state"] = {"short_term_constraints": ["口味：清淡饮食"]}
    q = augment_query_for_search("", state)
    assert q.startswith("[饮食约束]")
    assert "清淡" in q
