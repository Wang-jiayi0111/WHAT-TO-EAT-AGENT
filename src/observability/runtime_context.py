"""LangGraph 节点内可用的会话标识（与 configurable.thread_id 对齐）。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Mapping, Optional

_SESSION_ID: ContextVar[Optional[str]] = ContextVar("wte_session_id", default=None)


def get_invocation_session_id(state: Optional[Mapping[str, Any]] = None) -> str:
    sid = _SESSION_ID.get()
    if sid and str(sid).strip():
        return str(sid).strip()
    if isinstance(state, Mapping):
        uid = state.get("active_user_id")
        if uid is not None and str(uid).strip():
            return str(uid).strip()
    return "unknown"


@contextmanager
def bind_invocation_session(session_id: str) -> Iterator[None]:
    """在 `ainvoke` / `astream` 外包一层，使节点日志带上 thread_id。"""
    tok = _SESSION_ID.set((session_id or "").strip() or "default")
    try:
        yield
    finally:
        _SESSION_ID.reset(tok)
