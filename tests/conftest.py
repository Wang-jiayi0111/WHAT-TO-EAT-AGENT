"""
T-001：核心路径 pytest 夹具（最小 AgentState；运行时 bundle 由切片拼装）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# 保证 `from src...` 在 pytest 从任意 cwd 启动时可用
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def make_logistics_buffer(**overrides: Any) -> Dict[str, Any]:
    """构造最小展平 bundle（旧 buffer 形状），再经 `runtime_bundle_to_slice_patches` 写入切片。"""
    base: Dict[str, Any] = {
        "extracted_entities": {},
        "router_reasoning": "",
        "recipe_candidates": [],
        "selected_recipe_id": None,
        "recipe_requirements": [],
        "recipe_cook_step": None,
        "inventory_snapshot": [],
        "ingredient_gaps": [],
        "action_metadata": {},
        "pending_tasks": [],
    }
    base.update(overrides)
    return base


from src.agent.state import empty_agent_slices
from src.agent.state_sync import runtime_bundle_to_slice_patches


def make_minimal_agent_state(
    *,
    task_stack: Optional[List[str]] = None,
    logistics_buffer: Optional[Dict[str, Any]] = None,
    expert_payloads: Optional[Dict[str, Any]] = None,
    loop_guard_count: int = 0,
) -> Dict[str, Any]:
    """
    路由函数仅依赖部分字段；此处提供 TypedDict 未列但节点可能读取的缺省，避免 KeyError。
    """
    lb = logistics_buffer if logistics_buffer is not None else make_logistics_buffer()
    return {
        **empty_agent_slices(),
        **runtime_bundle_to_slice_patches(lb),
        "task_stack": task_stack if task_stack is not None else [],
        "expert_payloads": expert_payloads if expert_payloads is not None else {},
        "loop_guard_count": loop_guard_count,
    }


@pytest.fixture
def minimal_agent_state() -> Dict[str, Any]:
    """空任务栈 + 空切片派生的基线状态。"""
    return make_minimal_agent_state()
