import asyncio
import logging
import json
import time
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.observability.memory_metrics import record_keeper_run

from ...libs.base.user_profiles import UserProfileManager
from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings
from ..state import AgentState
from .schema import MemoryKeeperOutput
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryKeeper:
    """
    记忆守护者：后台静默分析对话，提取用户画像并写入数据库。
    不直接参与对话，只做信息提取与存储。
    """

    def __init__(self, db_path: Optional[str] = None):
        try:
            settings = Settings()
            self.user_profile_manager = UserProfileManager(
                db_path=db_path or settings.get_user_profiles_db_path(),
                scope_id_for_migration=settings.get_scope_id(),
            )
            base_llm = LLMFactory.get_llm(settings)
            self.llm = base_llm.with_structured_output(MemoryKeeperOutput)

            prompt_path = Path(__file__).parent.parent / "prompts" / "memory_prompt.md"
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
            self._short_term_ttl_days = settings.get_short_term_ttl_days()
            logger.info("MemoryKeeper 初始化成功")

        except Exception as e:
            logger.error("Memory Keeper 初始化失败: %s", e)
            raise

    def _format_conversation(self, messages: List[BaseMessage], window: int = 6) -> str:
        recent = messages[-window:] if len(messages) > window else messages
        lines = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                lines.append(f"用户：{msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"助手：{msg.content}")
        return "\n".join(lines)

    def _format_existing_profile(self, profile: Optional[Dict]) -> str:
        if not profile:
            return "（当前无已存档的用户画像）"
        return json.dumps(profile, ensure_ascii=False, indent=2)

    async def analyze(self, messages: List[BaseMessage], user_id: str) -> MemoryKeeperOutput:
        existing_profile = self.user_profile_manager.get_user_profile(user_id)
        conversation_text = self._format_conversation(messages)
        profile_text = self._format_existing_profile(existing_profile)

        full_prompt = (
            f"{self.system_prompt}\n\n"
            f"# 已有用户画像（供对比，避免重复写入）\n{profile_text}\n\n"
            f"# 最新对话记录\n{conversation_text}"
        )

        result = await self.llm.ainvoke(full_prompt)
        logger.debug("MemoryKeeper LLM 结果: %s", result)

        if hasattr(result, "parsed") and isinstance(result.parsed, dict):
            return MemoryKeeperOutput(**result.parsed)
        if hasattr(result, "parsed") and isinstance(result.parsed, MemoryKeeperOutput):
            return result.parsed
        return result

    def _apply_long_term_updates(self, user_id: str, long_term: Dict, intent_type: str) -> bool:
        """§3.3 / IR-05：合并策略与幂等写入由 UserProfileManager.apply_long_term_patch 统一实现。"""
        try:
            patch = dict(long_term)
            patch.pop("last_updated", None)
            ok = self.user_profile_manager.apply_long_term_patch(user_id, patch, intent_type)
            if ok:
                logger.info("用户 %s 长期画像已更新或已为幂等跳过（%s）", user_id, intent_type)
            return ok

        except Exception as e:
            logger.error("写入长期画像失败: %s", e)
            return False

    def _apply_short_term_states(self, user_id: str, short_term: Dict) -> bool:
        try:
            conditions = short_term.get("conditions", [])
            if not conditions:
                return True

            for condition in conditions:
                if isinstance(condition, dict):
                    condition = condition.get("condition", str(condition))
                self.user_profile_manager.add_short_term_state(
                    user_id,
                    str(condition),
                    ttl_days=self._short_term_ttl_days,
                )

            logger.info("用户 %s 短期状态已写入: %s", user_id, conditions)
            return True

        except Exception as e:
            logger.error("写入短期状态失败: %s", e)
            return False


def serialize_messages_for_keeper(messages: Sequence[BaseMessage]) -> List[Dict[str, str]]:
    """不可变快照：仅 human/ai 文本（规格 §4.5）。"""
    out: List[Dict[str, str]] = []
    for m in messages or []:
        if isinstance(m, HumanMessage):
            c = m.content
            out.append({"role": "human", "content": c if isinstance(c, str) else str(c)})
        elif isinstance(m, AIMessage):
            c = m.content
            out.append({"role": "ai", "content": c if isinstance(c, str) else str(c)})
    return out


def messages_from_keeper_snapshot(raw: Sequence[Dict[str, Any]]) -> List[BaseMessage]:
    out: List[BaseMessage] = []
    for item in raw or []:
        role = item.get("role")
        content = item.get("content") or ""
        if role == "human":
            out.append(HumanMessage(content=str(content)))
        elif role == "ai":
            out.append(AIMessage(content=str(content)))
    return out


def build_memory_keeper_snapshot(
    scope_id: str,
    messages: Sequence[BaseMessage],
) -> Dict[str, Any]:
    """L4 异步任务输入快照（禁止传入可变共享 state 对象）。"""
    return {
        "scope_id": scope_id,
        "messages": serialize_messages_for_keeper(messages),
    }


async def run_memory_keeper_persist(scope_id: str, messages: List[BaseMessage]) -> None:
    """分析并写库；异常向上抛出，由 run_memory_keeper_safe 捕获（规格 §4.5）。"""
    if not messages:
        logger.info("MemoryKeeper: 消息为空，跳过")
        return

    settings = Settings()
    keeper = MemoryKeeper(db_path=settings.get_user_profiles_db_path())
    result: MemoryKeeperOutput = await keeper.analyze(messages, scope_id)

    logger.info(
        "MemoryKeeper 分析结果: has_update=%s, intent=%s, reasoning=%s",
        result.has_update,
        result.intent_type,
        result.reasoning,
    )

    if not result.has_update:
        logger.info("MemoryKeeper: 无新偏好，跳过写库")
        return

    if result.long_term_updates:
        if hasattr(result.long_term_updates, "model_dump"):
            if result.intent_type == "explicit_correction":
                long_term_dict = result.long_term_updates.model_dump(exclude_unset=True)
            else:
                long_term_dict = result.long_term_updates.model_dump()
        else:
            long_term_dict = dict(result.long_term_updates)
        keeper._apply_long_term_updates(scope_id, long_term_dict, result.intent_type)

    if result.short_term_states and result.short_term_states.is_temporary:
        short_term_dict = (
            result.short_term_states.model_dump()
            if hasattr(result.short_term_states, "model_dump")
            else dict(result.short_term_states)
        )
        keeper._apply_short_term_states(scope_id, short_term_dict)


async def run_memory_keeper_safe(snapshot: Dict[str, Any]) -> None:
    """
    L4 异步安全壳：规格 §4.5 — error_code=MEMORY_KEEPER_FAILED，禁止影响主回复。
    """
    t0 = time.perf_counter()
    ok = False
    try:
        scope_id = str(snapshot.get("scope_id") or "default_user").strip() or "default_user"
        raw = snapshot.get("messages") or []
        messages = messages_from_keeper_snapshot(raw)
        await run_memory_keeper_persist(scope_id, messages)
        ok = True
    except Exception as e:
        # 规格 §9：MEMORY_KEEPER_FAILED
        logger.error(
            "MEMORY_KEEPER_FAILED error_code=MEMORY_KEEPER_FAILED detail=%s",
            e,
            exc_info=True,
        )
    finally:
        record_keeper_run(
            success=ok,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
        )


def schedule_memory_keeper_after_reply(scope_id: str, messages: Sequence[BaseMessage]) -> None:
    """
    generator 在产出待发送内容后调用：asyncio.create_task（规格 §4.5～4.6）。
    """
    snap = build_memory_keeper_snapshot(scope_id, messages)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("L4 keeper: 无运行中事件循环，跳过异步任务")
        return
    loop.create_task(run_memory_keeper_safe(snap))


async def memory_keeper_node(state: AgentState) -> AgentState:
    """
    兼容入口：同步执行一轮 L4（测试或手工调用）。
    主流程已改为 generator 后 schedule_memory_keeper_after_reply（T-012）。
    """
    from ..effective_constraint import resolve_scope_id

    scope_id = resolve_scope_id(state)
    messages = list(state.get("messages") or [])
    await run_memory_keeper_safe(build_memory_keeper_snapshot(scope_id, messages))
    return {}
