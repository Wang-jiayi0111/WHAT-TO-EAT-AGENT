"""
Agent State Definition for the WHAT-TO-EAT-AGENT system.

This module defines the structure of the state that flows between nodes in the LangGraph workflow.
"""
from typing import Annotated, List, Dict, Union, Optional, Any
import operator  # 必须导入用于列表合并
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict, NotRequired


def merge_slice(
    left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """切片 dict 浅合并（后者覆盖前者）；供 LangGraph Annotated 归约。"""
    l = {} if left is None else dict(left)
    r = {} if right is None else dict(right)
    l.update(r)
    return l


def empty_agent_slices() -> Dict[str, Dict[str, Any]]:
    """首轮 invoke 建议并入的空切片，避免缺键（T-030 阶段 1）。"""
    return {
        "dialog_state": {},
        "memory_state": {},
        "control_state": {},
        "recipe_state": {},
        "inventory_state": {},
        "response_state": {},
        "error_state": {},
    }


def replace_list(old: List, new: List) -> List:
    """替换语义：直接用新值覆盖旧值。"""
    return new

class AgentState(TypedDict):
    """
    WHAT-TO-EAT-AGENT LangGraph 状态。

    方案 A（§1.2.0）：一级 **七切片** 与窄顶层 `active_user_id`。会话业务字段已迁入各切片；
    运行时展平视图由 `state_accessors.get_runtime_bundle` 组装。`messages` 暂驻顶层以保留
    `add_messages`（迁入 `dialog_state` 见后续迭代）。
    """
    # 1. 对话记忆：使用 add_messages 增量累加
    messages: Annotated[List[BaseMessage], add_messages]
    conversation_summary: str           # 对话摘要；镜像至 memory_state.conversation_summary
    
    # 1b 方案 A 七切片（规格 §1.2.0～1.2.1）
    dialog_state: Annotated[Dict[str, Any], merge_slice]
    memory_state: Annotated[Dict[str, Any], merge_slice]
    control_state: Annotated[Dict[str, Any], merge_slice]
    recipe_state: Annotated[Dict[str, Any], merge_slice]
    inventory_state: Annotated[Dict[str, Any], merge_slice]
    response_state: Annotated[Dict[str, Any], merge_slice]
    error_state: Annotated[Dict[str, Any], merge_slice]

    # 2. 任务控制流：整表替换（replace_list）；消费语义见 task_stack.py（FR-04 执行即出队）
    task_stack: Annotated[List[str], replace_list]
    current_task: Optional[str]  # 正在处理的任务 ID
    current_intent: Optional[str] # 兼容字段：与 primary_intent 同步（规格 §11.1 迁移期）

    # 2b 意图结构化输出（FR-01；规格 §11.1；迁入 control_state 见 T-030）
    primary_intent: NotRequired[Optional[str]]
    intents: NotRequired[List[str]]
    secondary_intents: NotRequired[List[str]]
    confidence: NotRequired[float]
    needs_clarification: NotRequired[bool]
    slots: NotRequired[Dict[str, Any]]
    missing_slots: NotRequired[List[str]]

    # 3. 用户上下文
    active_user_id: str
    active_constraints: Dict[str, Any]  # 存储过敏、口味等实时约束
    
    # 4. 专家节点交付物 (显式定义)
    inventory_status: Optional[Dict[str, Any]]          # 库存快照
    research_results: Optional[List[Dict[str, Any]]]    # 检索到的菜谱切片
    shopping_list: Optional[Dict[str, Any]]             # 最终计算出的缺口清单
    meal_plan: Optional[str]                            # 生成的建议文案

    expert_payloads: Dict[str, Any]  # 存储各专家节点的输出结果，供后续节点使用
    
    # 6. 系统控制
    final_response: Optional[str]
    # 阶段1：防止 generator↔route 异常回环
    loop_guard_count: NotRequired[int]