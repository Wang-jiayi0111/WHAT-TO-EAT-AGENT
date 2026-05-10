"""
WHAT-TO-EAT-AGENT 主工作流

同轮共享状态由 LangGraph **单线程**按边执行，天然满足 FR-51 串行写；多任务顺序由
`task_stack` 与 `router` 的 FR-50 意图仲裁（`intent_priority.sort_intents_by_fr50`）共同决定。

方案 A（T-030 阶段 1）：状态含 **七切片**（`dialog_state`…`error_state`），与顶层扁平字段、
**runtime_bundle**（`state_accessors.get_runtime_bundle`）；详见 `state.py` / `state_sync.py`。

节点执行顺序：
  用户输入
    → conversation_summary  L2：仅压缩/裁剪 messages 与 conversation_summary（规格 §4.2，不误清 task_stack / 切片）
    → short_term            L3：T-013 DB 短期 TTL 清理 → 当轮约束 → memory_state.short_term_constraints（§4.3）
    → router                意图识别，生成 task_stack
    → … → generator → （回复就绪）asyncio.create_task(L4 MemoryKeeper)（规格 §4.5～4.6，T-012）
    → 条件路由（route_by_task）
        TASK_DIRECT_REPLY   → generator（闲聊）→ END
        TASK_SEARCH         → researcher → 条件路由（route_after_research）
                                高置信度（已有 R）→ logistics → generator → END
                                （logistics 内 §1.3 步 5：R 非空则静默拉取 I 并写
                                 cached_shopping_gap / gap_basis，不要求 TASK_GAP_CALC）
                                低置信度 → generator(CLARIFY) → 等待用户
        TASK_CLARIFY        → clarify_resolver → researcher（锁定后重新检索）
        TASK_INV_CHECK      → logistics → END
        TASK_GAP_CALC       → logistics → END
        TASK_INV_COMMIT     → logistics → END
"""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .core.state import AgentState, empty_agent_slices
from .core.state_accessors import get_runtime_bundle
from .nodes.router import router_node
from .nodes.generator import generator_node
from .nodes.researcher import researcher_node
from .nodes.logistics import logistics_manager_node
from .nodes.clarify_resolver import clarify_resolver_node
from .nodes.conversation_summary import conversation_summary_node
from .nodes.short_term import short_term_constraints_node
from src.observability.agent_node_trace import wrap_agent_node

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ════════════════════════════════════════════════════════════
# 条件路由函数
# ════════════════════════════════════════════════════════════
 
def route_by_task(state: AgentState) -> Literal[
    "researcher", "logistics", "generator", "clarify_resolver"
]:
    """
    router 节点后的主路由。
    根据 task_stack 决定下一个节点。
    """
    task_stack = state.get("task_stack", [])
    print(f"🔍 [Router] 识别到task_stack: {task_stack}")

    
    # 菜谱检索
    if "TASK_SEARCH" in task_stack:
        return "researcher"
    
    if "TASK_PROFILE_SYNC" in task_stack:
        return "generator"

    if "TASK_SUMMARIZE" in task_stack:
        return "generator"


    if "TASK_INV_ADD" in task_stack:
        print(f"🔍 [Router→] TASK_INV_ADD → logistics")
        return "logistics"

    if "TASK_INV_COMMIT" in task_stack:
        return "logistics"

    if "TASK_INV_CHECK" in task_stack:
        return "logistics"

    if "TASK_GAP_CALC" in task_stack:
        return "logistics"
 
    # 歧义解析（用户回复候选菜谱选择）
    if "TASK_CLARIFY" in task_stack:
        lb = get_runtime_bundle(state)
        if lb.get("recipe_candidates"):
            return "clarify_resolver"
        return "generator"
 
    # 兜底：闲聊 / 直接回复
    return "generator"

def route_after_research(state: AgentState):
    """
    researcher 节点后的路由。
    - 高置信度（已锁定菜谱）→ logistics 计算购物清单
    - 低置信度（歧义）→ generator 询问用户
    - 出错 → generator（降级说明）
    """
    lb = get_runtime_bundle(state)
 
    # 出错：统一进入 generator 生成可解释降级回复，不直接静默结束
    if state.get("expert_payloads", {}).get("error"):
        return "generator"
 
    # 低置信度，有候选列表
    if lb.get("recipe_candidates"):
        return "generator"
 
    # 高置信度，已有食材清单
    if lb.get("recipe_requirements"):
        return "logistics"
 
    return route_by_task(state)

def route_after_clarify(state: AgentState) -> Literal[
    "researcher", "generator"
]:
    """
    clarify_resolver 后的路由。
    - 解析成功（TASK_SEARCH）→ researcher 获取完整菜谱
    - 解析失败（TASK_CLARIFY）→ generator 重新询问
    """
    task_stack = state.get("task_stack", [])
    if "TASK_SEARCH" in task_stack:
        return "researcher"
    return "generator"

def route_after_generator(state: AgentState):
    """
    generator 后的路由。
    - 如果 generator 处理了 TASK_CLARIFY，继续等待用户选择（保持 TASK_CLARIFY）
    - 否则回到 router 进行新一轮意图识别
    """
    task_stack = state.get("task_stack", [])
    loop_guard_count = state.get("loop_guard_count", 0)

    if loop_guard_count >= 8:
        logger.warning("[Workflow] loop_guard_count exceeded threshold, force END")
        return END

    if "TASK_CLARIFY" in task_stack:
        print(f"🔍 [Generator→] 继续等待用户澄清选择")
        return END  # 等待用户回复，保持当前状态不变
    
    if not task_stack:
        print(f"🔍 [Generator→] 无后续任务，结束当前对话轮")
        return END
    

    return route_by_task(state)

# ════════════════════════════════════════════════════════════
# 构建图
# ════════════════════════════════════════════════════════════

def build_graph(checkpointer=None) -> StateGraph:
    graph = StateGraph(AgentState)
 
    # ── 注册节点 ──────────────────────────────────────────
    graph.add_node(
        "conversation_summary",
        wrap_agent_node("conversation_summary", conversation_summary_node),
    )
    graph.add_node(
        "short_term",
        wrap_agent_node("short_term", short_term_constraints_node),
    )
    graph.add_node("router", wrap_agent_node("router", router_node))
    graph.add_node("researcher", wrap_agent_node("researcher", researcher_node))
    graph.add_node("logistics", wrap_agent_node("logistics", logistics_manager_node))
    graph.add_node("generator", wrap_agent_node("generator", generator_node))
    graph.add_node(
        "clarify_resolver",
        wrap_agent_node("clarify_resolver", clarify_resolver_node),
    )
 
    # ── 入口 ──────────────────────────────────────────────
    graph.set_entry_point("conversation_summary")
 
    # ── 固定边 ────────────────────────────────────────────
    # conversation_summary → short_term（L3）→ router（规格 §4.6；L4 在 generator 后异步）
    graph.add_edge("conversation_summary", "short_term")
    graph.add_edge("short_term", "router")
 
    # ── 主路由（意图识别及后续） ────────────────────────────────────────────
    graph.add_conditional_edges(
        "router",
        route_by_task,
        {
            "researcher":       "researcher",
            "logistics":        "logistics",
            "generator":        "generator",
            "clarify_resolver": "clarify_resolver",
        }
    )
 
    # ── researcher（菜谱查询） 后路由 ──────────────────────────────────
    graph.add_conditional_edges(
        "researcher",
        route_after_research,
        {
            "researcher":       "researcher",   # 加上可能的回环节点
            "logistics":        "logistics",
            "generator":        "generator",
            "clarify_resolver": "clarify_resolver",
            END:         END,
        }
    )
 
    # ── clarify_resolver（澄清） 后路由 ───────────────────────────
    graph.add_conditional_edges(
        "clarify_resolver",
        route_after_clarify,
        {
            "researcher": "researcher",
            "generator":  "generator",
        }
    )

    # ── 查库存后 继续任务分配 ─────────────────────────────────
    graph.add_edge("logistics",  "generator")
    # graph.add_conditional_edges(
    #     "logistics",
    #     route_by_task,  
    #     {
    #         "researcher":       "researcher",
    #         "logistics":        "logistics",
    #         "generator":        "generator",
    #         "clarify_resolver": "clarify_resolver",
    #     }
    # )
 
    # ── 终止边 ────────────────────────────────────────────
    # graph.add_edge("generator",  END)
    graph.add_conditional_edges(
        "generator",
        route_after_generator,
        {
            "researcher":       "researcher",
            "logistics":        "logistics",
            "generator":        "generator",
            "clarify_resolver": "clarify_resolver",
            END:         END,
        }
    )
 
    return graph.compile(checkpointer=checkpointer)
 
# ════════════════════════════════════════════════════════════
# 对外暴露的运行接口
# ════════════════════════════════════════════════════════════

def create_agent(persist: bool = True):
    """
    创建 Agent 实例。
 
    Args:
        persist: 是否开启多轮对话记忆（基于 MemorySaver）
 
    Returns:
        编译好的 CompiledGraph
    """
    checkpointer = MemorySaver() if persist else None
    return build_graph(checkpointer=checkpointer)
 

async def run_turn(
    agent,
    user_message: str,
    thread_id: str = "default",
    user_id: str = "default_user",
) -> str:
    """
    执行单轮对话。

    Args:
        agent:        create_agent() 返回的图实例
        user_message: 用户输入
        thread_id:    对话线程 ID（同一 thread 共享 checkpointer 记忆）
        user_id:      用户 ID

    Returns:
        Agent 最新回复的文本
    """
    from langchain_core.messages import HumanMessage

    from src.observability.runtime_context import bind_invocation_session

    config = {"configurable": {"thread_id": thread_id}}

    try:
        current = await agent.aget_state(config)
        existing_messages = current.values.get("messages", [])
    except Exception:
        existing_messages = []

    input_state = {
        **empty_agent_slices(),
        "messages": [HumanMessage(content=user_message)],
        "active_user_id": user_id,
        "conversation_summary": current.values.get("conversation_summary", "")
        if existing_messages
        else "",
    }

    with bind_invocation_session(thread_id):
        result = await agent.ainvoke(input_state, config)

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            return msg.content
    return ""