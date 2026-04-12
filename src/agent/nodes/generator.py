"""
Generator Node - 处理两类场景：
1. TASK_DIRECT_REPLY：用户闲聊，直接用 LLM 生成回复
2. TASK_CLARIFY：菜谱歧义，向用户展示候选列表并询问选择
"""
import logging
from typing import Dict, Any, List
from pathlib import Path
from langchain_core.messages import AIMessage

from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings
from ..state import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CHITCHAT_SYSTEM_PROMPT = """\
你是一个温暖、专业的家庭膳食助手，擅长回答饮食、烹饪、营养相关的问题。
请用自然、亲切的语气回复用户，保持简洁。
如果用户的问题与饮食无关，可以友好地回应用户的问题。
"""


class GeneratorNode:

    def __init__(self):
        settings = Settings()
        self.llm = LLMFactory.get_llm(settings)

    def _build_chitchat_prompt(self, state: AgentState) -> List[Dict]:
        """构建闲聊的消息列表，注入历史摘要。"""
        messages = [{"role": "system", "content": CHITCHAT_SYSTEM_PROMPT}]

        # 注入语义压缩的历史摘要
        summary = state.get("conversation_summary", "")
        if summary:
            messages.append({
                "role": "system",
                "content": f"以下是本次对话的历史背景摘要：\n{summary}"
            })

        # 注入原始消息窗口
        for msg in state.get("messages", []):
            if hasattr(msg, "type"):
                role = "user" if msg.type == "human" else "assistant"
            else:
                role = "user"
            messages.append({"role": role, "content": msg.content})

        return messages

    def _build_clarify_message(self, candidates: List[Dict]) -> str:
        """
        根据候选菜谱列表生成歧义询问文本。

        candidates 格式（来自 logistics_buffer["recipe_candidates"]）：
        ["南派红烧肉", "毛氏红烧肉", "外婆红烧肉"]
        """
        logger.info(f"[logger-Generator] 构建歧义询问消息，候选菜谱: {candidates}")
        print(f"[Generator] 构建歧义询问消息，候选菜谱: {candidates}")  # 调试信息 --- IGNORE ---
        lines = ["我找到了以下几个相关菜谱，请问您想做哪一个？\n"]
        for i, recipe_name in enumerate(candidates, start=1):
            lines.append(f"  {i}. {recipe_name}")
        lines.append("\n请回复数字或菜名即可。")
        print(f"[Generator] 构建的歧义询问消息:\n{lines}")  # 调试信息 --- IGNORE ---
        return "\n".join(lines)

    async def handle_chitchat(self, state: AgentState) -> str:
        """调用 LLM 生成闲聊回复。"""
        messages = self._build_chitchat_prompt(state)
        response = await self.llm.ainvoke(messages)
        return response.content.strip()

    def handle_clarify(self, state: AgentState) -> str:
        """生成歧义询问文本，不需要调用 LLM。"""
        candidates = state.get("logistics_buffer", {}).get("recipe_candidates", [])
        if not candidates:
            state.get("task_stack", []).remove("TASK_CLARIFY") 
            return "抱歉，我没有找到合适的菜谱，请换个关键词再试试？"
        return self._build_clarify_message(candidates)

    def handle_inv_check(self, state: AgentState) -> str:
        """格式化库存快照返回给用户。"""
        snapshot = state.get("logistics_buffer", {}).get("inventory_snapshot", {})
        if not snapshot:
            return "您的厨房库存目前是空的，还没有添加任何食材。"

        lines = ["您家目前的库存食材如下：\n"]
        for name, info in snapshot.items():
            lines.append(f"  · {name}：{info['amount']} {info['unit']}")
        lines.append(f"\n共 {len(snapshot)} 种食材。")
        return "\n".join(lines)

    def handle_gap_calc(self, state: AgentState) -> str:
        """格式化购物清单返回给用户。"""
        lb = state.get("logistics_buffer", {})
        shopping_list = lb.get("shopping_list", [])
        sufficient = lb.get("sufficient_items", [])

        if not shopping_list:
            return "好消息！您家的食材已经够用，不需要额外购买。"

        lines = ["根据菜谱需求，您还需要购买以下食材：\n"]
        for item in shopping_list:
            lines.append(f"  · {item['name']}：{item['amount']} {item['unit']}")

        if sufficient:
            lines.append(f"\n以下食材库存充足，无需购买：")
            for item in sufficient:
                lines.append(f"  ✓ {item['name']}")

        return "\n".join(lines)

    def handle_inv_commit(self, state: AgentState) -> str:
        """库存扣减完成后的确认回复。"""
        status = state.get("logistics_buffer", {}).get("commit_status", "")
        if status == "success":
            return "好的，已记录本次烹饪，库存已更新。"
        elif status == "skipped":
            return "没有找到需要扣减的食材信息，库存未变动。"
        else:
            return "库存更新时遇到一些问题，请稍后再试。"
        
    def handle_inv_add(self, state: AgentState) -> str:
        status = state.get("logistics_buffer", {}).get("add_status", "")
        entities = state.get("logistics_buffer", {}).get("extracted_entities", {})
        ingredients = entities.get("ingredients", [])
        if status == "success" and ingredients:
            items_str = "、".join(ingredients)
            return f"好的，已将 {items_str} 添加到您的库存中。"
        elif status == "skipped":
            return "没有识别到具体食材，库存未变动，您可以告诉我买了哪些东西。"
        else:
            return "库存更新时遇到问题，请稍后再试。"
        
    def handle_profile_sync(self, state: AgentState) -> str:
        """偏好同步完成后给用户确认。"""
        # memory_keeper 已经写库，这里只需要生成确认文本
        messages = state.get("messages", [])
        last_user_msg = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                last_user_msg = msg.content
                break
        return f"好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。"
    
    def handle_summarize(self, state: AgentState) -> str:
        """获取菜谱的详情后，向用户回复"""
        lb = state.get("logistics_buffer", {})
        recipe_title = lb.get("selected_recipe_title", "未知菜谱")
        step = lb.get("recipe_cook_step", [])

        if not step:
            return f"菜谱{recipe_title}详情获取成功，但没有找到具体的烹饪步骤信息。"
        else:
            lines = [f"菜谱{recipe_title}烹饪步骤如下：\n"]
            for s in step:
                lines.append(f"  · {s}")
            return "\n".join(lines)


async def generator_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 节点入口。

    路由：
      TASK_DIRECT_REPLY → 闲聊，LLM 生成回复
      TASK_CLARIFY      → 歧义，展示候选菜谱列表
    """
    task_stack: List[str] = state.get("task_stack", []).copy()
    lb: Dict = state.get("logistics_buffer", {})

    print(f"🔍 [Generator] task_stack: {task_stack}")          
    print(f"🔍 [Generator] logistics_buffer 状态: {list(lb.keys())}")

    generator = GeneratorNode()
    reply = ""

    # ════════════════════════════════════════════════════════════
    # 1. 最高优先级：处理打断/阻塞型任务 (如歧义澄清)
    # ════════════════════════════════════════════════════════════
    if "TASK_CLARIFY" in task_stack:
        # 如果有澄清任务，必须立即停止其他汇报，优先向用户提问
        logger.info("[Generator] 处理歧义澄清任务")
        clarify_reply = generator.handle_clarify(state)
        new_message = AIMessage(content=clarify_reply)
        if "TASK_SEARCH" in task_stack:
            task_stack.remove("TASK_SEARCH")  # 同时移除触发澄清的搜索任务，避免重复搜索

        print(f"🔍 [Generator] 最终返回: task_stack={task_stack}")
        return {"messages": list(state.get("messages", [])) + [new_message],
                "task_stack": task_stack
                }


    # ════════════════════════════════════════════════════════════
    # 2. 成果收集：扫描各大 Buffer，收集所有后台完成的工作汇报
    # ════════════════════════════════════════════════════════════


    if "TASK_INV_ADD" in task_stack:
        reply = generator.handle_inv_add(state)
        task_stack.remove("TASK_INV_ADD")  # 处理完成后移除任务


    elif "TASK_INV_CHECK" in task_stack:      
        reply = generator.handle_inv_check(state)
        task_stack.remove("TASK_INV_CHECK")  # 处理完成后移除任务

    elif "TASK_INV_COMMIT" in task_stack:     
        reply = generator.handle_inv_commit(state)
        task_stack.remove("TASK_INV_COMMIT")  # 处理完成后移除任务

    elif "TASK_GAP_CALC" in task_stack:
        reply = generator.handle_gap_calc(state)
        task_stack.remove("TASK_GAP_CALC")  # 处理完成后移除任务

    elif "TASK_DIRECT_REPLY" in task_stack:
        reply = await generator.handle_chitchat(state)
        task_stack.remove("TASK_DIRECT_REPLY")  # 处理完成后移除任务

    elif "TASK_PROFILE_SYNC" in task_stack:
        reply = generator.handle_profile_sync(state)
        task_stack.remove("TASK_PROFILE_SYNC")  # 处理完成后移除任务

    elif "TASK_SUMMARIZE" in task_stack:
        reply = generator.handle_summarize(state)
        # task_stack.remove("TASK_SUMMARIZE")  # 处理完成后移除任务

        if lb.get("pending_tasks"):
            logger.info(f"[Generator] 处理完 summarize 后，发现 pending_tasks: {lb['pending_tasks']}")
            # 将 pending_tasks 中的任务重新加入 task_stack
            for t in lb["pending_tasks"]:
                if t not in task_stack:
                    task_stack.append(t)
            logger.info(f"[Generator] summarize 处理完成后，task_stack 更新为: {task_stack}")
        lb.get("pending_tasks", []).clear()

    else:
        logger.warning(f"[Generator] 未知 task_stack: {task_stack}")
        return {}

    logger.info(f"[Generator] task_stack 处理完成，还存在任务: {task_stack}")
    new_message = AIMessage(content=reply)
    updated_messages = list(state.get("messages", [])) + [new_message]

    print(f"🔍 [Generator] 最终返回: task_stack={task_stack}")
    return {
        "messages": updated_messages,
        "task_stack": task_stack,
        "logistics_buffer": lb
            }