"""
Agent State Definition for the WHAT-TO-EAT-AGENT system.

This module defines the structure of the state that flows between nodes in the LangGraph workflow.
"""
from typing import Annotated, List, Dict, Union, Optional, Any
import operator  # 必须导入用于列表合并
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

class LogisticsBuffer(TypedDict):
    """后勤缓冲区详细定义"""
    # --- 1. 意图提取的原始实体 (从 Router 传入) --- 
    # - ingredients: 提到的食材列表 (如: ["鸡蛋", "西红柿"])。
    # - recipe_name: 提到的具体菜名 (如: "红烧肉")。
    # - target_member: 涉及的家庭成员 ID (默认为 {active_user_id})。
    # - check_inventory: 布尔值，是否需要检查库存。
    extracted_entities: Dict[str, Any] 
    router_reasoning: str                       # 路由推理逻辑

    # --- 2. 检索与锁定 (由 Researcher 填充) ---
    recipe_candidates: List[Dict[str, Any]]     # 待选菜谱列表
    selected_recipe_id: Optional[str]           # 确定的菜谱路径或 ID
    
    
    # --- 3. 标准菜谱需求 R (由 TASK_SEARCH 填充) ---
    recipe_requirements: List[Dict[str, Any]]   # 结构化食材清单 R
    recipe_cook_step: Optional[str]             # 结构化烹饪步骤描述


    # --- 4. 库存数据 I (由 TASK_INV_CHECK 填充) ---
    inventory_snapshot: List[Dict[str, Any]] 
    
    # --- 5. 清单数据 (I-R) (由 TASK_GAP_CALC 生成) ---
    ingredient_gaps: List[Dict[str, Any]] 
    
    # --- 6. 执行元数据 (记录事务 ID 或扣减确认状态) ---
    action_metadata: Dict[str, Any]

    pending_tasks: List[str]                    # 暂存的任务列表

def replace_list(old: List, new: List) -> List:
    """替换语义：直接用新值覆盖旧值。"""
    return new

class AgentState(TypedDict):
    """
    优化后的 WHAT-TO-EAT-AGENT 状态定义
    """
    # 1. 对话记忆：使用 add_messages 增量累加
    messages: Annotated[List[BaseMessage], add_messages]
    conversation_summary: str           # 对话摘要，供后续节点快速理解上下文 
    
    # 2. 任务控制流：使用 operator.add 确保任务可以被追加而非覆盖
    task_stack: Annotated[List[str], replace_list]
    current_task: Optional[str]  # 正在处理的任务 ID
    current_intent: Optional[str] # 识别出的主意图 (SEARCH/INVENTORY 等)

    # 3. 用户上下文
    active_user_id: str
    active_constraints: Dict[str, Any]  # 存储过敏、口味等实时约束
    
    # 4. 业务数据缓冲区 
    logistics_buffer: LogisticsBuffer
    
    # 5. 专家节点交付物 (显式定义)
    inventory_status: Optional[Dict[str, Any]]          # 库存快照
    research_results: Optional[List[Dict[str, Any]]]    # 检索到的菜谱切片
    shopping_list: Optional[Dict[str, Any]]             # 最终计算出的缺口清单
    meal_plan: Optional[str]                            # 生成的建议文案

    expert_payloads: Dict[str, Any]  # 存储各专家节点的输出结果，供后续节点使用
    
    # 6. 系统控制
    final_response: Optional[str]