"""
对话窗口 + 语义压缩（L2）

策略：
- 保留最近 WINDOW_SIZE 条消息作为「热记忆」（原始对话，供 LLM 直接阅读）
- 超出窗口的消息触发语义压缩，生成 summary 融合进已有摘要
- 摘要写入顶层 `conversation_summary` 并镜像 `memory_state.conversation_summary`
- 长期偏好画像由 memory_keeper（L4）写入 SQLite（跨会话）

规格 §4.2：本节点**仅**维护 messages 裁剪与 conversation_summary；
禁止修改 task_stack、recipe_state、inventory_state 等业务现场（含澄清态）。
"""

import logging
from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings
from ..state import AgentState
from src.observability.memory_metrics import record_l2_turn

logger = logging.getLogger(__name__)

COMPRESS_PROMPT = """\
你是一个对话摘要助手。以下是一段用户与膳食助手的对话历史。
请将其压缩为一段简洁的摘要，保留以下关键信息：
1. 用户表达过的饮食偏好、禁忌、过敏原
2. 用户的健康目标或身体状态
3. 本次对话已完成的任务（如：已推荐了红烧肉食谱）
4. 用户对结果的反馈（满意/不满意/修改要求）

不要保留闲聊内容。输出纯文本，不要加标题或列表符号。

对话历史：
{conversation}

已有的历史摘要（如果有，请将新内容融合进去，不要简单拼接）：
{existing_summary}
"""


class ConversationSummaryManager:
    """
    负责管理对话窗口和语义压缩。
    作为工具类被 LangGraph 节点调用，不直接作为节点。
    """

    def __init__(self):
        settings = Settings()
        self.llm = LLMFactory.get_llm(settings)
        self.window_size = settings.get_memory_summary_window_size()
        self.compress_trigger = settings.get_memory_summary_compress_trigger()

    def needs_compression(self, messages: List[BaseMessage]) -> bool:
        """判断是否需要触发压缩。"""
        return len(messages) > self.compress_trigger

    def _format_messages_for_compression(self, messages: List[BaseMessage]) -> str:
        """将消息列表格式化为纯文本，用于压缩。"""
        lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                lines.append(f"用户：{msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"助手：{msg.content}")
        return "\n".join(lines)

    async def compress(
        self,
        messages_to_compress: List[BaseMessage],
        existing_summary: str = ""
    ) -> str:
        """
        对指定消息列表进行语义压缩，融合已有 summary。

        Args:
            messages_to_compress: 需要被压缩的消息（窗口之外的旧消息）
            existing_summary: 已有的历史摘要

        Returns:
            新的融合摘要字符串
        """
        conversation_text = self._format_messages_for_compression(messages_to_compress)

        prompt = COMPRESS_PROMPT.format(
            conversation=conversation_text,
            existing_summary=existing_summary if existing_summary else "（无）"
        )

        try:
            response = await self.llm.ainvoke(prompt)
            new_summary = response.content.strip()
            logger.info(f"语义压缩完成，摘要长度: {len(new_summary)} 字符")
            return new_summary
        except Exception as e:
            logger.error(f"语义压缩失败: {e}")
            # 压缩失败时降级：直接拼接文本摘要
            return (existing_summary + "\n" + conversation_text[-500:]).strip()

    async def maybe_compress(
        self,
        messages: List[BaseMessage],
        existing_summary: str = ""
    ) -> tuple[List[BaseMessage], str]:
        """
        主入口：判断是否需要压缩，并返回新的消息列表和 summary。

        Returns:
            (trimmed_messages, updated_summary)
            - trimmed_messages: 保留最近 window_size 条
            - updated_summary: 更新后的摘要
        """
        if not self.needs_compression(messages):
            return messages, existing_summary

        # 超出窗口的旧消息 → 压缩
        messages_to_compress = messages[: -self.window_size]
        # 保留最近的窗口
        trimmed_messages = messages[-self.window_size :]

        logger.info(
            f"触发语义压缩: 总消息 {len(messages)} 条，"
            f"压缩 {len(messages_to_compress)} 条，"
            f"保留 {len(trimmed_messages)} 条"
        )

        new_summary = await self.compress(messages_to_compress, existing_summary)
        return trimmed_messages, new_summary

    def build_context_messages(
        self,
        messages: List[BaseMessage],
        summary: str,
        system_prompt: str = ""
    ) -> List[BaseMessage]:
        """
        构建注入 summary 的完整上下文消息列表，供 LLM 推理使用。

        结构：
          [SystemMessage: system_prompt]
          [SystemMessage: 历史摘要]     ← 仅当 summary 非空时注入
          [最近 N 条原始 messages]
        """
        context: List[BaseMessage] = []

        if system_prompt:
            context.append(SystemMessage(content=system_prompt))

        if summary:
            summary_message = SystemMessage(
                content=(
                    "以下是本次对话的历史摘要，请结合它来理解用户的背景和已有共识：\n\n"
                    f"{summary}"
                )
            )
            context.append(summary_message)

        context.extend(messages)
        return context


async def conversation_summary_node(state: AgentState) -> AgentState:
    """
    LangGraph 节点：L2 对话摘要（规格 §4.2）。

    每轮入口在 router 之前运行：按需压缩窗口外消息、更新摘要并裁剪 messages。
    规格 §4.2 禁止：修改 task_stack、recipe_state、inventory_state 等（本节点不再返回这些键）。
    """
    messages = state.get("messages", [])
    mem = state.get("memory_state") or {}
    existing_summary = mem.get("conversation_summary") or state.get("conversation_summary") or ""

    if not messages:
        return {}

    try:
        manager = ConversationSummaryManager()
        will_compress = manager.needs_compression(messages)
        trimmed, summary = await manager.maybe_compress(messages, existing_summary)
        record_l2_turn(compression_triggered=will_compress)
        return {
            "messages": trimmed,
            "conversation_summary": summary,
            # merge_slice：仅覆盖摘要字段，保留 short_term_constraints 等 L3 字段
            "memory_state": {"conversation_summary": summary},
        }
    except Exception as e:
        logger.error(f"conversation_summary_node 执行失败: {e}", exc_info=True)
        return {}