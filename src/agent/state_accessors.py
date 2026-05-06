"""
方案 A 运行时访问器（T-030 阶段 2～3）。

节点应通过 `get_runtime_bundle(state)` 读取与旧 `logistics_buffer` 等价的展平视图；
写入时使用 `runtime_bundle_to_slice_patches`（见 `state_sync`）拆回各切片。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from .state_sync import (
    materialize_runtime_bundle_from_slices,
    slices_carry_session_payload,
)


def get_runtime_bundle(state: Mapping[str, Any]) -> Dict[str, Any]:
    """
    返回会话运行时展平 bundle（意图实体、菜谱、库存与清单中间态等）。

    - **残留 checkpoint** 仅含 `logistics_buffer` 且无切片业务数据时，直接返回 buffer。
    - 否则切片优先与 buffer 合并（后者多见于迁移期双写）。
    """
    legacy = state.get("logistics_buffer")
    flat = materialize_runtime_bundle_from_slices(state)
    if isinstance(legacy, dict) and legacy and not slices_carry_session_payload(state):
        return dict(legacy)
    if isinstance(legacy, dict) and legacy:
        return {**dict(legacy), **flat}
    return flat
