"""
E2E 用例 `e2e_seed`：在**首轮** `ainvoke` 前将业务切片与 `task_stack` 等合并进输入状态，
便于清单类用例具备稳定的 R/I/gap/overlay 起点（规格 §7，与 runner 配合）。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, Optional

_SLICE_KEYS = (
    "dialog_state",
    "memory_state",
    "control_state",
    "recipe_state",
    "inventory_state",
    "response_state",
    "error_state",
)

_TOP_COPY_KEYS = ("task_stack", "conversation_summary")


def merge_e2e_seed_into_input_state(
    input_state: Dict[str, Any],
    seed: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """深合并 seed 到各切片；不覆盖 `messages`。"""
    if not seed:
        return input_state
    out = copy.deepcopy(input_state)
    for sk in _SLICE_KEYS:
        block = seed.get(sk)
        if isinstance(block, dict) and block:
            cur = dict(out.get(sk) or {})
            cur.update(copy.deepcopy(block))
            out[sk] = cur
    for tk in _TOP_COPY_KEYS:
        if tk in seed:
            out[tk] = copy.deepcopy(seed[tk])
    return out
