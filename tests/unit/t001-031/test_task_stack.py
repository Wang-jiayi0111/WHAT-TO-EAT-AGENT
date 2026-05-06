"""T-003：task_stack 消费与调度顺序。"""

from src.agent.task_stack import (
    GENERATOR_REPLY_TASK_ORDER,
    consume_tasks,
    first_present,
)


def test_consume_tasks_idempotent():
    s = ["TASK_A", "TASK_B", "TASK_A"]
    assert consume_tasks(s, ["TASK_A"]) == ["TASK_B", "TASK_A"]
    assert consume_tasks(s, ["TASK_A", "TASK_A"]) == ["TASK_B"]
    assert consume_tasks(s, ["UNKNOWN"]) == s


def test_first_present_respects_order():
    stack = ["TASK_SUMMARIZE", "TASK_INV_CHECK"]
    assert first_present(stack, GENERATOR_REPLY_TASK_ORDER) == "TASK_INV_CHECK"
