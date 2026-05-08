"""
记忆子系统进程内指标（NFR-07）：L2 摘要触发、L3 约束命中、L4 写库成败与耗时 P95。

数值通过结构化日志输出；生产环境可再由日志采集侧聚合。
"""
from __future__ import annotations

import math
import threading
from collections import deque
from typing import Any, Deque, Dict, List

_lock = threading.Lock()

_l2_turns = 0
_l2_compress_triggers = 0
_l3_turns = 0
_l3_hits = 0
_keeper_runs = 0
_keeper_success = 0
_keeper_durations_ms: Deque[float] = deque(maxlen=512)


def record_l2_turn(*, compression_triggered: bool) -> None:
    global _l2_turns, _l2_compress_triggers
    with _lock:
        _l2_turns += 1
        if compression_triggered:
            _l2_compress_triggers += 1


def record_l3_turn(*, constraint_hit: bool) -> None:
    global _l3_turns, _l3_hits
    with _lock:
        _l3_turns += 1
        if constraint_hit:
            _l3_hits += 1


def record_keeper_run(*, success: bool, duration_ms: float) -> None:
    global _keeper_runs, _keeper_success
    with _lock:
        _keeper_runs += 1
        if success:
            _keeper_success += 1
        if duration_ms >= 0:
            _keeper_durations_ms.append(float(duration_ms))


def _percentile_95(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = int(math.ceil(0.95 * len(s))) - 1
    return float(s[max(0, min(len(s) - 1, k))])


def snapshot() -> Dict[str, Any]:
    with _lock:
        durs = list(_keeper_durations_ms)
        l2t = _l2_turns
        l2c = _l2_compress_triggers
        l3t = _l3_turns
        l3h = _l3_hits
        kr = _keeper_runs
        ks = _keeper_success
    return {
        "l2_turns": l2t,
        "l2_summary_compress_triggers": l2c,
        "l2_summary_compress_rate": (l2c / l2t) if l2t else 0.0,
        "l3_turns": l3t,
        "l3_constraint_hits": l3h,
        "l3_constraint_hit_rate": (l3h / l3t) if l3t else 0.0,
        "l4_keeper_runs": kr,
        "l4_keeper_success": ks,
        "l4_keeper_success_rate": (ks / kr) if kr else 0.0,
        "l4_keeper_latency_p95_ms": _percentile_95(durs),
        "l4_keeper_latency_samples": len(durs),
    }
