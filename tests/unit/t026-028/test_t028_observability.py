"""
T-028 结构化日志与记忆指标（NFR-06 / NFR-07）
==========================================

**任务**：T-028  
**规格**：NFR-06、NFR-07  
**开发记录**：`docs/dev_log.md` [DEV-034]

`memory_metrics` 为进程内全局计数器；各用例通过 **`importlib.reload`** 隔离。

验收结论写入 **`docs/test_report.md`** [TR-042]。
"""

from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock, patch

import pytest

from src.libs.base.settings import Settings


@pytest.fixture
def fresh_memory_metrics():
    import src.observability.memory_metrics as mm

    importlib.reload(mm)
    return mm


def test_t028_settings_observability_flags_default_on() -> None:
    """默认 `setting.yaml` 打开结构化日志与记忆指标。"""
    s = Settings()
    assert s.observability_enabled() is True
    assert s.observability_structured_agent_log() is True
    assert s.observability_memory_metrics_log() is True


def test_t028_runtime_bind_invocation_session() -> None:
    from src.observability.runtime_context import (
        bind_invocation_session,
        get_invocation_session_id,
    )

    assert get_invocation_session_id({}) == "unknown"
    assert get_invocation_session_id({"active_user_id": "scope_a"}) == "scope_a"
    with bind_invocation_session("thread-xyz"):
        assert get_invocation_session_id({}) == "thread-xyz"
    assert get_invocation_session_id({}) == "unknown"


def test_t028_memory_metrics_snapshot_rates(fresh_memory_metrics) -> None:
    mm = fresh_memory_metrics
    for _ in range(3):
        mm.record_l2_turn(compression_triggered=False)
    mm.record_l2_turn(compression_triggered=True)
    snap = mm.snapshot()
    assert snap["l2_turns"] == 4
    assert snap["l2_summary_compress_triggers"] == 1
    assert abs(snap["l2_summary_compress_rate"] - 0.25) < 1e-6

    mm.record_l3_turn(constraint_hit=False)
    mm.record_l3_turn(constraint_hit=True)
    mm.record_l3_turn(constraint_hit=True)
    snap2 = mm.snapshot()
    assert snap2["l3_turns"] == 3
    assert snap2["l3_constraint_hits"] == 2
    assert abs(snap2["l3_constraint_hit_rate"] - 2 / 3) < 1e-6

    mm.record_keeper_run(success=True, duration_ms=10.0)
    mm.record_keeper_run(success=False, duration_ms=20.0)
    mm.record_keeper_run(success=True, duration_ms=30.0)
    snap3 = mm.snapshot()
    assert snap3["l4_keeper_runs"] == 3
    assert snap3["l4_keeper_success"] == 2
    assert abs(snap3["l4_keeper_success_rate"] - 2 / 3) < 1e-6
    assert snap3["l4_keeper_latency_p95_ms"] >= 10.0
    assert snap3["l4_keeper_latency_samples"] == 3


def test_t028_wrap_sync_node_emits_span() -> None:
    from src.observability.agent_node_trace import wrap_agent_node

    with patch("src.observability.agent_node_trace.emit_agent_node_span") as emit:
        fn = lambda state: {"task_stack": ["TASK_SEARCH"], "error_state": {}}
        wrapped = wrap_agent_node("demo_sync", fn)
        wrapped({"active_user_id": "sess-1"})

    emit.assert_called_once()
    kw = emit.call_args.kwargs
    assert kw["session_id"] == "sess-1"
    assert kw["node"] == "demo_sync"
    assert kw["status"] == "ok"
    assert kw["duration_ms"] >= 0
    assert kw.get("error_code") is None


def test_t028_wrap_sync_node_propagates_error_code() -> None:
    from src.observability.agent_node_trace import wrap_agent_node

    with patch("src.observability.agent_node_trace.emit_agent_node_span") as emit:
        fn = lambda state: {
            "task_stack": [],
            "error_state": {"error_code": "GAP_CACHE_MISS"},
        }
        wrap_agent_node("with_code", fn)({})

    kw = emit.call_args.kwargs
    assert kw["error_code"] == "GAP_CACHE_MISS"


def test_t028_wrap_sync_node_exception_marks_error() -> None:
    from src.observability.agent_node_trace import wrap_agent_node

    def boom(_state):
        raise ValueError("x")

    with patch("src.observability.agent_node_trace.emit_agent_node_span") as emit:
        wrapped = wrap_agent_node("bad", boom)
        with pytest.raises(ValueError):
            wrapped({})

    kw = emit.call_args.kwargs
    assert kw["status"] == "error"
    assert kw["end_reason"] == "ValueError"


@pytest.mark.asyncio
async def test_t028_wrap_async_node_emits_span() -> None:
    from src.observability.agent_node_trace import wrap_agent_node

    async def node(_state):
        return {"task_stack": []}

    with patch("src.observability.agent_node_trace.emit_agent_node_span") as emit:
        wrapped = wrap_agent_node("demo_async", node)
        await wrapped({"active_user_id": "async-sess"})

    kw = emit.call_args.kwargs
    assert kw["node"] == "demo_async"
    assert kw["session_id"] == "async-sess"
    assert kw["status"] == "ok"


def test_t028_emit_memory_metrics_json_line(fresh_memory_metrics) -> None:
    import src.observability.structured_agent_log as sal

    importlib.reload(sal)
    mm = fresh_memory_metrics
    mm.record_l2_turn(compression_triggered=True)

    mock_log = MagicMock()
    with patch.object(sal, "_LOG", mock_log):
        sal.emit_memory_metrics("json-test", extra={"k": "v"})

    mock_log.info.assert_called_once()
    raw = mock_log.info.call_args[0][0]
    payload = json.loads(raw)
    assert payload["event"] == "agent.memory_metrics"
    assert payload["session_id"] == "json-test"
    assert payload["l2_turns"] == 1
    assert payload["extra"]["k"] == "v"


def test_t028_emit_node_span_respects_settings_off(fresh_memory_metrics) -> None:
    import src.observability.structured_agent_log as sal

    importlib.reload(sal)
    _ = fresh_memory_metrics

    mock_log = MagicMock()
    with patch.object(sal, "_LOG", mock_log):
        with patch.object(
            Settings,
            "observability_structured_agent_log",
            return_value=False,
        ):
            sal.emit_agent_node_span(
                session_id="s",
                node="n",
                duration_ms=1.0,
                status="ok",
            )
    mock_log.info.assert_not_called()
