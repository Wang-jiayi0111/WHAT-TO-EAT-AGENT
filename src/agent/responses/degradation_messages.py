"""
全链路降级用户话术（**FR-61**：服务不可用、生成失败、合并结果为空时**不得**静默结束）。

与 `error_code_user_messages`（规格错误码口径）互补：本模块覆盖「无 error_code / LLM 异常 / 管线未产出文本」类场景。
"""
from __future__ import annotations

from typing import List


def message_llm_call_failed() -> str:
    """意图闲聊、营养问答等依赖 LLM 时调用失败或异常。"""
    return (
        "生成回复时遇到问题（模型暂时不可用或请求超时）。"
        "请稍后再试；若持续出现，请检查网络或模型配置。"
    )


def message_llm_empty_output() -> str:
    """LLM 返回空内容时的兜底。"""
    return (
        "没能生成有效文字回复。"
        "请换一句话再说说您的需求，或稍后再试。"
    )


def message_merged_segments_empty(consumed_tasks: List[str]) -> str:
    """
    成果任务已消费但合并后无可展示文本（§FR-52 合并异常 / 处理器返回空）。
    `consumed_tasks` 仅用于日志侧排查，话术保持用户可理解。
    """
    _ = consumed_tasks
    return (
        "抱歉，本轮内部步骤未产出可见回复（例如中间结果为空）。"
        "请稍后再试；若您在做菜谱检索或库存操作，也可以换一种说法重试。"
    )


def message_recipe_search_service_unavailable() -> str:
    """MCP / 检索接口不可用或返回错误结构（尚无规范 `error_code` 时）。"""
    return (
        "菜谱检索服务暂时不可用，我无法从本地菜谱库拉取结果。"
        "请稍后再试；您也可以先说想吃的口味或食材，我再给您一些不依赖检索的建议。"
    )


def message_generator_empty_turn(task_stack_snapshot: List[str]) -> str:
    """
    generator 入口一轮结束时仍无任何可见回复时的最后兜底（例如 task_stack 与合并逻辑不匹配）。
    """
    _ = task_stack_snapshot
    return (
        "抱歉，本轮没能向您返回可读内容。"
        "请稍后再试，或简短说明您想「找菜」「查库存」还是「生成购物清单」。"
    )
