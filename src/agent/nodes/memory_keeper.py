import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from ...libs.base.user_profiles import UserProfileManager
from ...libs.adapters.llm.llm_factory import LLMFactory
from ..state import AgentState
from .schema import MemoryKeeperOutput
from ...libs.base.settings import Settings
from ..state import AgentState

logger = logging.getLogger(__name__)

class MemoryKeeper:
    """
    记忆守护者：后台静默分析对话，提取用户画像并写入数据库。
    不直接参与对话，只做信息提取与存储。
    """
    def __init__(self, db_path: str = "data/db/user_profiles.db"):
        try:
            settings = Settings()

            self.user_profile_manager = UserProfileManager(db_path=db_path)
            base_llm = LLMFactory.get_llm(settings)
            self.llm = base_llm.with_structured_output(MemoryKeeperOutput)

            prompt_path = Path(__file__).parent.parent / "prompts" / "memory_prompt.md"
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
            logger.info("MemoryKeeper 初始化成功")

        except Exception as e:
            logger.error(f"Memory Keeper 初始化失败: {e}")
            raise

    def _format_conversation(self, messages: List[BaseMessage], window: int = 6) -> str:
        """
        将最近 N 条消息格式化为对话文本，供 LLM 分析。
        只取最近的窗口，避免 token 浪费。
        """
        recent = messages[-window:] if len(messages) > window else messages
        lines = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                lines.append(f"用户：{msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"助手：{msg.content}")
        return "\n".join(lines)
 
    def _format_existing_profile(self, profile: Optional[Dict]) -> str:
        """将已有用户画像格式化为文本，注入 prompt 供 LLM 做对比。"""
        if not profile:
            return "（当前无已存档的用户画像）"
        return json.dumps(profile, ensure_ascii=False, indent=2)
    
    def _merge_list(self, existing: list, new_items: list) -> list:
        """列表取并集，去重。"""
        merged = list(existing)
        for item in new_items:
            if item and item not in merged:
                merged.append(item)
        return merged
 
    async def analyze(self, messages: List[BaseMessage], user_id: str) -> MemoryKeeperOutput:
        """
        调用 LLM 分析对话，返回结构化的提取结果。
        """
        existing_profile = self.user_profile_manager.get_user_profile(user_id)
        conversation_text = self._format_conversation(messages)
        profile_text = self._format_existing_profile(existing_profile)
 
        full_prompt = (
            f"{self.system_prompt}\n\n"
            f"# 已有用户画像（供对比，避免重复写入）\n{profile_text}\n\n"
            f"# 最新对话记录\n{conversation_text}"
        )
 
        result = await self.llm.ainvoke(full_prompt)
        logger.error(f"DEBUG LLM结果: {result}") 
        
        if hasattr(result, 'parsed') and isinstance(result.parsed, dict):
            return MemoryKeeperOutput(**result.parsed)
        if hasattr(result, 'parsed') and isinstance(result.parsed, MemoryKeeperOutput):
            return result.parsed
        return result
    
    def _apply_long_term_updates(self, user_id: str, long_term: Dict, intent_type: str) -> bool:
        """
        将长期画像更新写入数据库。
        - passive_extract：并集合并，不覆盖已有数据
        - explicit_correction：显式修正，直接覆盖对应字段
        """
        try:
            existing = self.user_profile_manager.get_user_profile(user_id) or {}
 
            if intent_type == "explicit_correction":
                # 显式修正：直接覆盖用户指定的字段
                updated = dict(existing)
                if long_term.get("allergens") is not None:
                    updated["allergens"] = long_term["allergens"]
                if long_term.get("medical_restrictions"):
                    updated["medical_restrictions"] = long_term["medical_restrictions"]
                if long_term.get("dietary_target"):
                    updated["dietary_target"] = long_term["dietary_target"]
                if long_term.get("cooking_habits"):
                    updated["cooking_habits"] = long_term["cooking_habits"]
 
                taste = long_term.get("taste_tags", {})
                if taste.get("like") or taste.get("dislike"):
                    existing_taste = existing.get("taste_tags", {"like": [], "dislike": []})
                    updated["taste_tags"] = {
                        "like": taste.get("like", existing_taste.get("like", [])),
                        "dislike": taste.get("dislike", existing_taste.get("dislike", []))
                    }
            else:
                # 被动提取：并集合并
                updated = dict(existing)
                updated["allergens"] = self._merge_list(
                    existing.get("allergens", []),
                    long_term.get("allergens", [])
                )
                updated["medical_restrictions"] = self._merge_list(
                    existing.get("medical_restrictions", []),
                    long_term.get("medical_restrictions", [])
                )
                updated["cooking_habits"] = self._merge_list(
                    existing.get("cooking_habits", []),
                    long_term.get("cooking_habits", [])
                )
                if long_term.get("dietary_target") and not existing.get("dietary_target"):
                    updated["dietary_target"] = long_term["dietary_target"]
 
                taste = long_term.get("taste_tags", {})
                existing_taste = existing.get("taste_tags", {"like": [], "dislike": []})
                updated["taste_tags"] = {
                    "like": self._merge_list(
                        existing_taste.get("like", []),
                        taste.get("like", [])
                    ),
                    "dislike": self._merge_list(
                        existing_taste.get("dislike", []),
                        taste.get("dislike", [])
                    )
                }
 
            updated["last_updated"] = datetime.now().isoformat()
            self.user_profile_manager.upsert_long_term_profile(user_id, updated)
            logger.info(f"用户 {user_id} 长期画像已更新（{intent_type}）")
            return True
        
        except Exception as e:
            logger.error(f"写入长期画像失败: {e}")
            return False
 

    def _apply_short_term_states(self, user_id: str, short_term: Dict) -> bool:
        try:
            conditions = short_term.get("conditions", [])
            if not conditions:
                return True

            for condition in conditions:
                # 确保是字符串
                if isinstance(condition, dict):
                    condition = condition.get("condition", str(condition))
                # 逐条写入，add_short_term_state 内部已处理去重
                self.user_profile_manager.add_short_term_state(user_id, str(condition))

            logger.info(f"用户 {user_id} 短期状态已写入: {conditions}")
            return True

        except Exception as e:
            logger.error(f"写入短期状态失败: {e}")
            return False


async def memory_keeper_node(state: AgentState) -> AgentState:
    """
    LangGraph 节点入口。
    后台静默运行，不修改消息列表，只更新数据库并将短期状态注入 logistics_buffer。
    """
    messages: List[BaseMessage] = state.get("messages", [])
    user_id: str = state.get("active_user_id", "default_user")
 
    # 消息不足时跳过分析
    if not messages:
        logger.info("MemoryKeeper: 消息为空，跳过")
        return {}
 
    try:
        keeper = MemoryKeeper()
        result: MemoryKeeperOutput = await keeper.analyze(messages, user_id)
 
        logger.info(f"MemoryKeeper 分析结果: has_update={result.has_update}, "
                    f"intent={result.intent_type}, reasoning={result.reasoning}")
 
        if not result.has_update:
            logger.info("MemoryKeeper: 无新偏好，跳过写库")
            return {}
 
        # 写入长期画像
        if result.long_term_updates:
            long_term_dict = result.long_term_updates.model_dump() \
                if hasattr(result.long_term_updates, 'model_dump') \
                else dict(result.long_term_updates)
            keeper._apply_long_term_updates(user_id, long_term_dict, result.intent_type)
 
        # 写入短期状态，并注入 logistics_buffer 供当次推理使用
        short_term_injected = []
        if result.short_term_states and result.short_term_states.is_temporary:
            short_term_dict = result.short_term_states.model_dump() \
                if hasattr(result.short_term_states, 'model_dump') \
                else dict(result.short_term_states)
            keeper._apply_short_term_states(user_id, short_term_dict)
            short_term_injected = result.short_term_states.conditions or []
 
        # 将短期状态注入当次 logistics_buffer，让 researcher 节点能感知
        if short_term_injected:
            logistics_buffer = state.get("logistics_buffer", {})
            existing_constraints = logistics_buffer.get("short_term_constraints", [])
            logistics_buffer["short_term_constraints"] = list(
                set(existing_constraints + short_term_injected)
            )
            return {"logistics_buffer": logistics_buffer}
 
        return {}
 
    except Exception as e:
        logger.error(f"MemoryKeeper 节点执行失败: {e}", exc_info=True)
        # 节点失败不阻断主流程，返回空 state 更新
        return {}
    