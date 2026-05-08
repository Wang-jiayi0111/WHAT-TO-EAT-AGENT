"""为 LangGraph 节点增加耗时与状态的结构化日志（NFR-06）。"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Mapping, Optional, TypeVar

from src.agent.state import AgentState

from .runtime_context import get_invocation_session_id
from .structured_agent_log import emit_agent_node_span

F = TypeVar("F", bound=Callable[..., Any])


def _error_code_from_result(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    es = result.get("error_state")
    if not isinstance(es, Mapping):
        return None
    code = es.get("error_code")
    if code is None or code == "":
        return None
    return str(code)


def _end_reason_from_result(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    ts = result.get("task_stack")
    if isinstance(ts, list) and ts:
        return f"task_stack_head={ts[0]}"
    if ts == []:
        return "task_stack_empty"
    return None


def wrap_agent_node(name: str, fn: F) -> F:
    """包装异步或同步节点函数，出口打一条 `agent.node_span`。"""
    if asyncio.iscoroutinefunction(fn):

        async def _async_wrapper(state: AgentState, *args: Any, **kwargs: Any) -> Any:
            sid = get_invocation_session_id(state)
            t0 = time.perf_counter()
            status = "ok"
            err_reason: Optional[str] = None
            out: Any = None
            try:
                out = await fn(state, *args, **kwargs)
                return out
            except Exception as e:
                status = "error"
                err_reason = type(e).__name__
                raise
            finally:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                ec = _error_code_from_result(out) if status == "ok" else None
                er = err_reason if status == "error" else _end_reason_from_result(out)
                emit_agent_node_span(
                    session_id=sid,
                    node=name,
                    duration_ms=dt_ms,
                    status=status,
                    error_code=ec,
                    end_reason=er,
                )

        return _async_wrapper  # type: ignore[return-value]

    def _sync_wrapper(state: AgentState, *args: Any, **kwargs: Any) -> Any:
        sid = get_invocation_session_id(state)
        t0 = time.perf_counter()
        status = "ok"
        err_reason: Optional[str] = None
        out: Any = None
        try:
            out = fn(state, *args, **kwargs)
            return out
        except Exception as e:
            status = "error"
            err_reason = type(e).__name__
            raise
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            ec = _error_code_from_result(out) if status == "ok" else None
            er = err_reason if status == "error" else _end_reason_from_result(out)
            emit_agent_node_span(
                session_id=sid,
                node=name,
                duration_ms=dt_ms,
                status=status,
                error_code=ec,
                end_reason=er,
            )

    return _sync_wrapper  # type: ignore[return-value]
