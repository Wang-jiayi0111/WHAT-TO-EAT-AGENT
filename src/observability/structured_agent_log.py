"""NFR-06：单行 JSON 日志，便于日志系统按字段检索。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from src.libs.base.settings import Settings

_LOG = logging.getLogger("what_to_eat.agent_trace")


def _settings_allow_structured() -> bool:
    try:
        return Settings().observability_structured_agent_log()
    except Exception:
        return True


def _settings_allow_metrics() -> bool:
    try:
        return Settings().observability_memory_metrics_log()
    except Exception:
        return True


def emit_agent_node_span(
    *,
    session_id: str,
    node: str,
    duration_ms: float,
    status: str,
    error_code: Optional[str] = None,
    end_reason: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not _settings_allow_structured():
        return
    payload: Dict[str, Any] = {
        "event": "agent.node_span",
        "session_id": session_id,
        "node": node,
        "duration_ms": round(duration_ms, 2),
        "status": status,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    if end_reason is not None:
        payload["end_reason"] = end_reason
    if extra:
        payload["extra"] = extra
    _LOG.info(json.dumps(payload, ensure_ascii=False))


def emit_memory_metrics(session_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
    if not _settings_allow_metrics():
        return
    from .memory_metrics import snapshot

    payload: Dict[str, Any] = {
        "event": "agent.memory_metrics",
        "session_id": session_id,
        **snapshot(),
    }
    if extra:
        payload["extra"] = extra
    _LOG.info(json.dumps(payload, ensure_ascii=False))
