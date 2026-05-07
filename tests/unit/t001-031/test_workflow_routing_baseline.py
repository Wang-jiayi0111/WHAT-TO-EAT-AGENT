"""
T-001：工作流条件边「核心路径」路由快照（无外部依赖、无 LLM）。

与 `docs/规格设计.md` §10「编排」目录映射（`workflow.py`）对齐；变更路由逻辑时请同步更新
`tests/snapshots/workflow_routing_baseline.json`。
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.graph import END

from src.agent.workflow import (
    route_after_clarify,
    route_after_generator,
    route_after_research,
    route_by_task,
)
from src.agent.state_accessors import get_runtime_bundle

from tests.conftest import make_logistics_buffer, make_minimal_agent_state

# 本文件在 tests/unit/t001-031/，快照在 tests/snapshots/
_SNAPSHOT = (
    Path(__file__).resolve().parent.parent.parent / "snapshots" / "workflow_routing_baseline.json"
)


def _ser_route_target(x):
    if x is END:
        return "__END__"
    return x


def _collect_route_by_task() -> dict:
    return {
        "task_search": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_SEARCH"])
            )
        ),
        "task_profile_sync": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_PROFILE_SYNC"])
            )
        ),
        "task_summarize": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_SUMMARIZE"])
            )
        ),
        "task_inv_add": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_INV_ADD"])
            )
        ),
        "task_inv_commit": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_INV_COMMIT"])
            )
        ),
        "task_inv_check": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_INV_CHECK"])
            )
        ),
        "task_gap_calc": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(task_stack=["TASK_GAP_CALC"])
            )
        ),
        "clarify_with_candidates": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(
                    task_stack=["TASK_CLARIFY"],
                    logistics_buffer=make_logistics_buffer(
                        recipe_candidates=[{"id": "1", "name": "x"}]
                    ),
                )
            )
        ),
        "clarify_no_candidates": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(
                    task_stack=["TASK_CLARIFY"],
                    logistics_buffer=make_logistics_buffer(recipe_candidates=[]),
                )
            )
        ),
        "empty_stack": _ser_route_target(
            route_by_task(make_minimal_agent_state(task_stack=[]))
        ),
        "task_search_overrides_inv_check": _ser_route_target(
            route_by_task(
                make_minimal_agent_state(
                    task_stack=["TASK_INV_CHECK", "TASK_SEARCH"],
                )
            )
        ),
    }


def _collect_route_after_research() -> dict:
    return {
        "error_payload": _ser_route_target(
            route_after_research(
                make_minimal_agent_state(
                    task_stack=["TASK_SEARCH"],
                    expert_payloads={"error": "boom"},
                )
            )
        ),
        "has_candidates": _ser_route_target(
            route_after_research(
                make_minimal_agent_state(
                    task_stack=["TASK_SEARCH"],
                    logistics_buffer=make_logistics_buffer(
                        recipe_candidates=[{"id": "a"}],
                    ),
                )
            )
        ),
        "has_requirements": _ser_route_target(
            route_after_research(
                make_minimal_agent_state(
                    task_stack=["TASK_SEARCH"],
                    logistics_buffer=make_logistics_buffer(
                        recipe_requirements=[{"name": "鸡蛋", "qty": 2}],
                    ),
                )
            )
        ),
        "fallback_to_route_by_task_search": _ser_route_target(
            route_after_research(
                make_minimal_agent_state(task_stack=["TASK_SEARCH", "TASK_GAP_CALC"])
            )
        ),
        "fallback_to_route_by_task_search_only": _ser_route_target(
            route_after_research(
                make_minimal_agent_state(task_stack=["TASK_SEARCH"])
            )
        ),
        "idle_stack": _ser_route_target(
            route_after_research(make_minimal_agent_state(task_stack=[]))
        ),
    }


def _collect_route_after_clarify() -> dict:
    return {
        "with_search_task": _ser_route_target(
            route_after_clarify(
                make_minimal_agent_state(task_stack=["TASK_SEARCH"])
            )
        ),
        "no_search_task": _ser_route_target(
            route_after_clarify(
                make_minimal_agent_state(task_stack=["TASK_CLARIFY"])
            )
        ),
    }


def _collect_route_after_generator() -> dict:
    return {
        "loop_guard_force_end": _ser_route_target(
            route_after_generator(
                make_minimal_agent_state(
                    task_stack=["TASK_SEARCH"],
                    loop_guard_count=8,
                )
            )
        ),
        "clarify_wait_user": _ser_route_target(
            route_after_generator(
                make_minimal_agent_state(task_stack=["TASK_CLARIFY"])
            )
        ),
        "empty_stack_end": _ser_route_target(
            route_after_generator(make_minimal_agent_state(task_stack=[]))
        ),
        "nonempty_delegates_to_route_by_task": _ser_route_target(
            route_after_generator(
                make_minimal_agent_state(task_stack=["TASK_SEARCH"])
            )
        ),
    }


def test_minimal_agent_state_fixture(minimal_agent_state):
    """夹具 smoke：与路由用例共用同一工厂语义。"""
    assert minimal_agent_state["task_stack"] == []
    assert get_runtime_bundle(minimal_agent_state)["recipe_candidates"] == []


def test_workflow_routing_matches_snapshot():
    actual = {
        "route_by_task": _collect_route_by_task(),
        "route_after_research": _collect_route_after_research(),
        "route_after_clarify": _collect_route_after_clarify(),
        "route_after_generator": _collect_route_after_generator(),
    }
    expected = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    assert actual == expected
