"""
task_stack 消费语义（FR-04；规格 §12.4）

- **唯一名称**：全项目只用 `task_stack`，禁止 `task_queue` 等别名（与 dev_agent_prompt 一致）。
- **执行即出队**：节点在完成对本标记的本轮处理后，从列表中移除对应条目（首次匹配移除）。
- **有序列表**：`task_stack` 为 list，顺序可用于多意图优先级（FR-50 细化为 T-007）；路由见 `workflow.route_by_task`。
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

# 与 workflow.route_by_task 中非 clarify / researcher 路径的相对优先级对齐（越前越高）
ROUTER_TASK_PRIORITY: Tuple[str, ...] = (
    "TASK_SEARCH",
    "TASK_PROFILE_SYNC",
    "TASK_SUMMARIZE",
    "TASK_INV_ADD",
    "TASK_INV_COMMIT",
    "TASK_INV_CHECK",
    "TASK_GAP_CALC",
    "TASK_CLARIFY",
)

# generator 内处理「成果汇报」类任务时的调度顺序（TASK_CLARIFY 在 generator 内单独最高优先级）
GENERATOR_REPLY_TASK_ORDER: Tuple[str, ...] = (
    "TASK_INV_ADD",
    "TASK_INV_CHECK",
    "TASK_INV_COMMIT",
    "TASK_GAP_CALC",
    "TASK_DIRECT_REPLY",
    "TASK_PROFILE_SYNC",
    "TASK_SUMMARIZE",
)


def consume_tasks(stack: Sequence[str], consumed: Iterable[str]) -> List[str]:
    """
    返回新列表：从 stack 中依次移除 consumed 里每个标记的**第一次**出现；
    若某标记不存在则跳过（幂等、安全重复调用）。
    """
    out = list(stack)
    for token in consumed:
        if token in out:
            out.remove(token)
    return out


def first_present(stack: Sequence[str], candidates: Sequence[str]) -> str | None:
    """返回 candidates 中第一个也在 stack 中出现的标记。"""
    s = set(stack)
    for c in candidates:
        if c in s:
            return c
    return None
