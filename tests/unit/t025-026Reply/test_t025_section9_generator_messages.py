"""
T-025 §9 错误码话术与可解释回复（FR-60 / §9）
==========================================

**任务**：T-025  
**规格**：FR-60；§9  
**开发记录**：`docs/dev_log.md` [DEV-030]（实现：`src/agent/error_code_user_messages.py`、`generator`）

验收结论写入 **`docs/test_report.md`** [TR-038]。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agent.core.state import empty_agent_slices
from src.agent.core.state_sync import runtime_bundle_to_slice_patches
from src.agent.responses.error_code_user_messages import (
    message_gap_basis_mismatch,
    message_gap_cache_miss,
    message_commit_recipe_mismatch,
    try_error_code_direct_reply,
    user_message_for_inventory_failure,
)
from src.agent.nodes.generator import GeneratorNode, _collect_merged_generator_reply

from tests.conftest import make_logistics_buffer


def test_t025_try_direct_reply_recipe_search_empty_branches() -> None:
    """RECIPE_SEARCH_EMPTY：软重试标记切换长尾说明。"""
    st_soft = {
        "error_state": {"error_code": "RECIPE_SEARCH_EMPTY"},
        "expert_payloads": {"recipe_search_soft_retry_attempted": True},
    }
    t_soft = try_error_code_direct_reply(st_soft)
    assert t_soft and "放宽" in t_soft

    st_plain = {
        "error_state": {"error_code": "RECIPE_SEARCH_EMPTY"},
        "expert_payloads": {},
    }
    t_plain = try_error_code_direct_reply(st_plain)
    assert t_plain and "忌口" in t_plain or "约束" in t_plain


def test_t025_try_direct_reply_static_codes_non_empty() -> None:
    """若干 §9 码返回固定口径文案。"""
    assert try_error_code_direct_reply(
        {"error_state": {"error_code": "RECIPE_SOURCE_NOT_FOUND"}}
    )
    assert try_error_code_direct_reply(
        {"error_state": {"error_code": "RECIPE_PARSE_FAILED"}}
    )
    assert try_error_code_direct_reply(
        {"error_state": {"error_code": "MEMORY_KEEPER_FAILED"}}
    )
    assert try_error_code_direct_reply(
        {"error_state": {"error_code": "CLARIFICATION_REQUIRED"}}
    )


def test_t025_try_direct_reply_gap_codes_match_helpers() -> None:
    """GAP_* 与独立函数一致。"""
    st_miss = {"error_state": {"error_code": "GAP_CACHE_MISS"}}
    assert try_error_code_direct_reply(st_miss) == message_gap_cache_miss()

    st_basis = {"error_state": {"error_code": "GAP_BASIS_MISMATCH"}}
    assert try_error_code_direct_reply(st_basis) == message_gap_basis_mismatch()


def test_t025_try_direct_reply_unknown_or_benign_returns_none() -> None:
    """未知码 / 占位码 → None（交由降级或 LLM）。"""
    assert try_error_code_direct_reply({}) is None
    assert try_error_code_direct_reply({"error_state": {"error_code": ""}}) is None
    assert try_error_code_direct_reply({"error_state": {"error_code": "success"}}) is None


def test_t025_user_message_inventory_failure_hints() -> None:
    """库存失败话术区分扣减/补货语境。"""
    w = user_message_for_inventory_failure(
        "INVENTORY_WRITE_FAILED",
        "详情一行",
        operation_hint="按菜谱扣减库存",
    )
    assert w and "扣减" in w and "详情一行" in w

    u = user_message_for_inventory_failure("INVENTORY_ADD_UNPARSED")
    assert u and "单位" in u


def test_t025_handle_gap_calc_fresh_intro_and_miss() -> None:
    """缺口：`fresh` 可解释句；无清单码走统一 `message_gap_cache_miss`。"""
    gen = GeneratorNode()
    lb_fresh = make_logistics_buffer(
        gap_delivery_mode="fresh",
        shopping_list=[{"name": "蒜", "amount": 2, "unit": "头"}],
        sufficient_items=[],
    )
    st_f = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_fresh),
        "error_state": {},
    }
    out_f = gen.handle_gap_calc(st_f)
    assert "最新" in out_f and "蒜" in out_f

    lb_miss = make_logistics_buffer()
    st_m = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_miss),
        "error_state": {"error_code": "GAP_CACHE_MISS"},
    }
    assert gen.handle_gap_calc(st_m) == message_gap_cache_miss()


def test_t025_handle_inv_commit_section9_branches() -> None:
    """扣减：菜名不一致走 §9；失败走统一写库话术。"""
    gen = GeneratorNode()
    lb_mm = make_logistics_buffer(commit_status="blocked_recipe_mismatch")
    st_mm = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_mm),
    }
    assert gen.handle_inv_commit(st_mm) == message_commit_recipe_mismatch()

    lb_fail = make_logistics_buffer(commit_status="failed", commit_failed_items=["蛋"])
    st_fail = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb_fail),
        "error_state": {"error_code": "INVENTORY_WRITE_FAILED", "error_detail": "x"},
    }
    text = gen.handle_inv_commit(st_fail)
    assert "数据库" in text or "写入" in text
    assert "蛋" in text


def test_t025_handle_summarize_explains_local_source() -> None:
    """步骤摘要标明本地解析来源（FR-60）。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(
        selected_recipe_title="测试菜",
        recipe_cook_step=["热锅", "出锅"],
    )
    st = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
    }
    body = gen.handle_summarize(st)
    assert "测试菜" in body and "本地菜谱解析" in body


def test_t025_handle_summarize_ingredients_when_user_asks_what_to_buy() -> None:
    """问「需要什么食材」时应输出用料而非烹饪步骤。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(
        selected_recipe_title="蛋糕",
        recipe_requirements=[{"name": "面粉", "amount": 200.0, "unit": "g"}],
        recipe_cook_step=["打蛋", "烘烤"],
    )
    st = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "messages": [HumanMessage(content="需要什么食材")],
    }
    body = gen.handle_summarize(st)
    assert "用料清单" in body and "面粉" in body and "200" in body
    assert "烹饪步骤" not in body


def test_t025_handle_summarize_steps_when_user_asks_how_to_cook() -> None:
    """追问做法时应输出步骤而非用料。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(
        selected_recipe_title="蛋糕",
        recipe_requirements=[{"name": "面粉", "amount": 200.0, "unit": "g"}],
        recipe_cook_step=["打蛋", "烘烤"],
    )
    st = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "messages": [HumanMessage(content="具体怎么做")],
    }
    body = gen.handle_summarize(st)
    assert "烹饪步骤" in body and "打蛋" in body
    assert "用料清单" not in body


@pytest.mark.asyncio
async def test_t025_direct_reply_prefers_section9_over_degraded() -> None:
    """TASK_DIRECT_REPLY：存在 §9 话术时优先于 `degraded_reply`。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(degraded_reply="【降级占位不应展示】")
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "error_state": {"error_code": "GAP_CACHE_MISS"},
    }
    merged, _ = await _collect_merged_generator_reply(
        gen,
        state,
        ["TASK_DIRECT_REPLY"],
        lb,
    )
    assert "【降级占位不应展示】" not in merged
    assert merged.strip() == message_gap_cache_miss().strip()


@pytest.mark.asyncio
async def test_t025_direct_reply_degraded_when_no_section9() -> None:
    """无已知码时仍可走降级正文。"""
    gen = GeneratorNode()
    lb = make_logistics_buffer(degraded_reply="降级正文")
    state = {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "error_state": {},
    }
    with patch.object(
        GeneratorNode,
        "handle_direct_reply",
        new_callable=AsyncMock,
        return_value="不应出现",
    ):
        merged, _ = await _collect_merged_generator_reply(
            gen,
            state,
            ["TASK_DIRECT_REPLY"],
            lb,
        )
    assert merged == "降级正文"
