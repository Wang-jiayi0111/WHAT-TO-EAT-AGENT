"""
Generator Node - 处理两类场景：
1. TASK_DIRECT_REPLY：元意图（help / out_of_scope / dietary_advice）、闲聊、recipe_adopt 占位回复等
2. TASK_CLARIFY：菜谱歧义，向用户展示候选列表并询问选择
"""
import copy
import logging
from collections import Counter
from typing import Dict, Any, List
from pathlib import Path
from langchain_core.messages import AIMessage

from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings
from ..effective_constraint import resolve_scope_id
from ..state import AgentState
from ..state_accessors import get_runtime_bundle
from ..degradation_messages import (
    message_generator_empty_turn,
    message_llm_call_failed,
    message_llm_empty_output,
    message_merged_segments_empty,
)
from ..error_code_user_messages import (
    message_commit_recipe_mismatch,
    message_gap_cache_miss,
    message_inventory_write_failed,
    try_error_code_direct_reply,
    user_message_for_inventory_failure,
)
from ..state_sync import runtime_bundle_to_slice_patches
from ..task_stack import consume_tasks
from .memory_keeper import schedule_memory_keeper_after_reply


def _generator_slice_patch(content: str, task_stack: List[str], loop_guard: int) -> Dict[str, Any]:
    return {
        "response_state": {"final_response": content},
        "control_state": {"loop_guard_count": loop_guard, "task_stack": list(task_stack)},
    }

# FR-52：按 task_stack 从左到右依次产出话术段，再合并为单条 AIMessage
MERGEABLE_GENERATOR_TASKS = frozenset(
    {
        "TASK_INV_ADD",
        "TASK_INV_CHECK",
        "TASK_INV_COMMIT",
        "TASK_GAP_CALC",
        "TASK_DIRECT_REPLY",
        "TASK_PROFILE_SYNC",
        "TASK_SUMMARIZE",
    }
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CHITCHAT_SYSTEM_PROMPT = """\
你是一个温暖、专业的家庭膳食助手，擅长回答饮食、烹饪、营养相关的问题。
请用自然、亲切的语气回复用户，保持简洁。
如果用户的问题与饮食无关，可以友好地回应用户的问题。
"""

# FR-02 / 规格 §11.3：元意图固定话术（help、out_of_scope）
HELP_REPLY_TEXT = """你好！我是膳食助手，可以帮你：
· 按口味、食材或菜名**找菜谱**，并结合你家**库存**给建议；
· **查库存**、记**补货**与做饭后的**扣减**；
· 生成**购物缺口清单**（在菜谱与库存就绪后）；
· 记录**饮食偏好与忌口**（过敏等）。

直接说你想吃什么、家里有什么，或问「能做什么」都可以。"""

OUT_OF_SCOPE_REPLY_TEXT = (
    "我主要帮你做饭谱推荐、库存与买菜清单、饮食偏好这类家事膳食问题。"
    "这个问题超出了我的能力范围，换个和吃饭、买菜、菜谱相关的话题我可以陪你聊。"
)

DIETARY_ADVICE_SYSTEM_PROMPT = """\
你是可靠的家庭营养与膳食顾问，回答用户的饮食健康、营养素、忌口搭配等问题。
要求：语气亲切、简洁；涉及医疗诊断或处方时必须提醒用户遵医嘱，不得替代专业诊疗。
若用户问题与膳食无关，简短引导回膳食场景。
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

    def _normalize_candidate_titles(self, candidates: List[Any]) -> List[str]:
        """兼容 list[str]/list[dict]/混合脏数据，统一提取候选标题。"""
        normalized: List[str] = []
        for item in candidates or []:
            if isinstance(item, str):
                title = item.strip()
            elif isinstance(item, dict):
                title = str(
                    item.get("title")
                    or item.get("name")
                    or item.get("recipe_name")
                    or ""
                ).strip()
            else:
                title = str(item).strip()
            if title and title not in normalized:
                normalized.append(title)
        return normalized

    def _build_clarify_message(self, candidates: List[Any]) -> str:
        """
        根据候选菜谱列表生成歧义询问文本。

        candidates 格式（来自运行时 bundle 的 recipe_candidates）：
        ["南派红烧肉", "毛氏红烧肉", "外婆红烧肉"]
        """
        logger.info(f"[logger-Generator] 构建歧义询问消息，候选菜谱: {candidates}")
        print(f"[Generator] 构建歧义询问消息，候选菜谱: {candidates}")  # 调试信息 --- IGNORE ---
        lines = ["我找到了以下几个相关菜谱（按检索相关性排序），请问您想做哪一个？\n"]
        normalized_titles = self._normalize_candidate_titles(candidates)
        for i, recipe_name in enumerate(normalized_titles, start=1):
            lines.append(f"  {i}. {recipe_name}")
        lines.append("\n请回复序号数字（如 1）或菜名即可。")
        print(f"[Generator] 构建的歧义询问消息:\n{lines}")  # 调试信息 --- IGNORE ---
        return "\n".join(lines)

    async def handle_chitchat(self, state: AgentState) -> str:
        """调用 LLM 生成闲聊回复。"""
        messages = self._build_chitchat_prompt(state)
        response = await self.llm.ainvoke(messages)
        return response.content.strip()

    def handle_help(self) -> str:
        """使用帮助（意图 help → TASK_DIRECT_REPLY）。"""
        return HELP_REPLY_TEXT

    def handle_out_of_scope(self) -> str:
        """明确超范围（意图 out_of_scope）。"""
        return OUT_OF_SCOPE_REPLY_TEXT

    def handle_recipe_adopt_reply(self, state: AgentState) -> str:
        """recipe_adopt：§6.3 采纳当前锁定菜谱 → `recipe_use_confirmed` 由本节点切片补丁置位。"""
        lb = get_runtime_bundle(state)
        title = lb.get("selected_recipe_title") or lb.get("recipe_title_locked")
        if title:
            return (
                f"好的，我们就按「{title}」准备。"
                "做完饭后跟我说一声，我可以按这份菜谱帮你扣减库存。"
            )
        return (
            "好的，已记下您采纳当前这道菜。"
            "做完饭后告诉我，我可以按菜谱帮你更新库存。"
        )

    def _extract_slots(self, state: AgentState) -> Dict[str, Any]:
        return dict(
            state.get("slots")
            or get_runtime_bundle(state).get("extracted_entities")
            or {}
        )

    def _build_dietary_advice_prompt(self, state: AgentState) -> List[Dict]:
        messages = [{"role": "system", "content": DIETARY_ADVICE_SYSTEM_PROMPT}]
        slots = self._extract_slots(state)
        diet_topic = slots.get("diet_topic")
        if diet_topic:
            messages.append({
                "role": "system",
                "content": f"用户关注的子主题（若有）：{diet_topic}",
            })
        summary = state.get("conversation_summary", "")
        if summary:
            messages.append({
                "role": "system",
                "content": f"对话摘要：\n{summary}",
            })
        for msg in state.get("messages", []):
            if hasattr(msg, "type"):
                role = "user" if msg.type == "human" else "assistant"
            else:
                role = "user"
            messages.append({"role": role, "content": msg.content})
        return messages

    async def handle_dietary_advice(self, state: AgentState) -> str:
        """营养/健康类问答（dietary_advice），不触发检索（规格 §11.3）。"""
        messages = self._build_dietary_advice_prompt(state)
        response = await self.llm.ainvoke(messages)
        return response.content.strip()

    async def handle_direct_reply(self, state: AgentState) -> str:
        """TASK_DIRECT_REPLY 内按 primary_intent 分支（T-006 / §11.4）。"""
        primary = (
            state.get("primary_intent")
            or state.get("current_intent")
            or "general_chat"
        )
        try:
            if primary == "help":
                return self.handle_help()
            if primary == "out_of_scope":
                return self.handle_out_of_scope()
            if primary == "recipe_adopt":
                return self.handle_recipe_adopt_reply(state)
            if primary == "dietary_advice":
                text = await self.handle_dietary_advice(state)
            else:
                text = await self.handle_chitchat(state)
            out = (text or "").strip()
            if not out:
                return message_llm_empty_output()
            return out
        except Exception:
            logger.exception("[Generator] handle_direct_reply 异常（FR-61 降级）")
            return message_llm_call_failed()

    def handle_clarify(self, state: AgentState) -> str:
        """生成歧义询问文本（FR-22：有限候选 + 序号/菜名选择提示）。不需要调用 LLM。"""
        lb = get_runtime_bundle(state)
        candidates = lb.get("recipe_candidates", [])
        normalized_titles = self._normalize_candidate_titles(candidates)
        if not normalized_titles:
            return "抱歉，我没有找到合适的菜谱，请换个关键词再试试？"
        body = self._build_clarify_message(candidates)
        if lb.get("clarify_error") == "invalid_choice":
            return (
                "抱歉，没能识别您的选择。请回复列表中的序号（1～"
                f"{len(normalized_titles)}），或直接输入菜名（可输入部分关键词）。\n\n"
                + body
            )
        return body

    def handle_inv_check(self, state: AgentState) -> str:
        """格式化库存快照返回给用户。"""
        snapshot = get_runtime_bundle(state).get("inventory_snapshot", {})
        if not snapshot:
            return "您的厨房库存目前是空的，还没有添加任何食材。"

        lines = ["您家目前的库存食材如下：\n"]
        for name, info in snapshot.items():
            lines.append(f"  · {name}：{info['amount']} {info['unit']}")
        lines.append(f"\n共 {len(snapshot)} 种食材。")
        return "\n".join(lines)

    def handle_gap_calc(self, state: AgentState) -> str:
        """§7.3 / FR-40～42：购物缺口展示（缓存命中与 GAP_CACHE_MISS）。"""
        lb = get_runtime_bundle(state)
        es = state.get("error_state") or {}
        code = str(es.get("error_code") or "")
        mode = str(lb.get("gap_delivery_mode") or "")

        if mode == "empty" or code == "GAP_CACHE_MISS":
            return message_gap_cache_miss()

        shopping_list = lb.get("shopping_list", [])
        sufficient = lb.get("sufficient_items", [])

        if not shopping_list:
            return "好消息！按当前菜谱与库存，您家的食材已经够用，不需要额外购买。"

        intro = "根据当前锁定菜谱与库存换算，您还需要购买以下食材：\n"
        if mode == "cache":
            intro = (
                "按当前菜谱与库存校验，**与缓存一致**，直接使用已算好的缺口清单：\n"
            )
        elif mode == "fresh":
            intro = (
                "已按**最新库存**与菜谱用料重新计算缺口，待购清单如下：\n"
            )
        lines = [intro]
        ov = lb.get("shopping_list_overlay") or []
        if isinstance(ov, list) and ov:
            lines.append("（以下待购行已包含你对清单的手动调整。）\n")
        for item in shopping_list:
            lines.append(f"  · {item['name']}：{item['amount']} {item['unit']}")

        if sufficient:
            lines.append("\n以下食材库存充足，无需购买：")
            for item in sufficient:
                lines.append(f"  ✓ {item['name']}")

        return "\n".join(lines)

    def handle_inv_commit(self, state: AgentState) -> str:
        """§6.3 / §6.4：扣减结果话术（须先 recipe_use_confirmed）。"""
        status = get_runtime_bundle(state).get("commit_status", "")
        if status == "success":
            return "好的，已按当前锁定的菜谱扣减库存。"
        if status == "skipped":
            return "当前没有可用的菜谱用料清单（**R** 为空），库存未变动。"
        if status == "blocked_no_confirm":
            return (
                "按菜谱扣减前需要先确认您要用的是当前这道菜——可以说「就做这道」或「确认用当前菜谱」；"
                "确认后再告诉我「做好了」或让我扣库存即可。"
            )
        if status == "blocked_recipe_mismatch":
            return message_commit_recipe_mismatch()
        if status == "partial_success":
            lb = get_runtime_bundle(state)
            succ = lb.get("commit_succeeded_items") or []
            fail = lb.get("commit_failed_items") or []
            parts = [
                "按菜谱扣减时**未能全部写入库存**（§6.4），请不要当作已全部扣减成功。"
            ]
            if succ:
                parts.append("已成功扣减：" + "、".join(succ) + "。")
            if fail:
                parts.append("**未能写入扣减**的食材：" + "、".join(fail) + "。")
            parts.append("请稍后重试或检查本地库存数据库。")
            return "".join(parts)
        if status == "failed":
            lb = get_runtime_bundle(state)
            fail = lb.get("commit_failed_items") or []
            es = state.get("error_state") or {}
            detail = str(es.get("error_detail") or "").strip()
            base = message_inventory_write_failed(
                detail or None, operation_hint="按菜谱扣减库存"
            )
            if fail:
                base += "\n\n未能完成扣减的食材：" + "、".join(fail) + "。"
            return base
        return "库存更新时遇到一些问题，请稍后再试。"
        
    def handle_inv_add(self, state: AgentState) -> str:
        lb = get_runtime_bundle(state)
        status = lb.get("add_status", "")
        preview = lb.get("add_preview") or {}
        items_pv = preview.get("items") or []
        unresolved = preview.get("unresolved") or []

        if status == "pending" and items_pv:
            lines = [
                "即将按以下条目更新库存（确认后写入；也可直接回复「确认」）：",
            ]
            for it in items_pv:
                mode = (it.get("merge_mode") or "add").strip().lower()
                op = "累加" if mode == "add" else "设为"
                lines.append(
                    f"  · {it.get('name')}：{op} {it.get('delta_or_value')} {it.get('unit')}"
                )
            if unresolved:
                lines.append(
                    "以下条目信息不完整，请补充数量与单位："
                    + "、".join(str(u) for u in unresolved)
                )
            return "\n".join(lines)

        if status == "pending" and not items_pv and unresolved:
            return (
                "补货信息不完整，请说明每种食材买了多少（需带单位），"
                "例如「买了鸡蛋 12 个」。"
            )

        if status == "success":
            added = lb.get("added_items") or []
            if added:
                parts = [
                    f"{x.get('name')} {x.get('delta_or_value')}{x.get('unit')}"
                    for x in added
                ]
                return "好的，已确认并更新库存：" + "、".join(parts) + "。"
            return "好的，已更新库存。"

        if status == "partial_success":
            succ = lb.get("add_succeeded_items") or []
            fail = lb.get("add_failed_items") or []
            es = state.get("error_state") or {}
            detail = es.get("error_detail") or ""
            head = "补货**未全部写入成功**（§6.5.5），请勿当作已全部入库。"
            if succ:
                head += "已成功入库：" + "、".join(succ) + "。"
            if fail:
                head += "**未能写入**：" + "、".join(fail) + "。"
            if detail and detail not in head:
                head += detail
            return head

        if status == "failed":
            es = state.get("error_state") or {}
            code = str(es.get("error_code") or "")
            detail = str(es.get("error_detail") or "")
            mapped = user_message_for_inventory_failure(
                code or None,
                detail or None,
                operation_hint="补货入库",
            )
            if mapped:
                return mapped
            return "库存更新失败，请稍后再试。"

        if status == "skipped":
            return (
                "没有识别到可入库的食材与数量，您可以说明买了什么、各多少（带单位）。"
            )

        return "库存更新遇到问题，请稍后再试。"
        
    def handle_profile_sync(self, state: AgentState) -> str:
        """偏好同步意图的确认话术（L4 在回复后异步写库，见 schedule_memory_keeper_after_reply）。"""
        messages = state.get("messages", [])
        last_user_msg = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                last_user_msg = msg.content
                break
        return f"好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。"
    
    def handle_summarize(self, state: AgentState) -> str:
        """获取菜谱的详情后，向用户回复"""
        lb = get_runtime_bundle(state)
        recipe_title = lb.get("selected_recipe_title", "未知菜谱")
        step = lb.get("recipe_cook_step", [])

        if not step:
            return (
                f"已从菜谱库解析「{recipe_title}」，但未找到可用的烹饪步骤段落；"
                "您可以换一道菜或稍后再试。"
            )
        else:
            lines = [f"以下为「{recipe_title}」的烹饪步骤（来自本地菜谱解析）：\n"]
            for s in step:
                lines.append(f"  · {s}")
            return "\n".join(lines)


async def _collect_merged_generator_reply(
    generator: "GeneratorNode",
    state: AgentState,
    task_stack: List[str],
    lb: Dict[str, Any],
) -> tuple[str, List[str]]:
    """
    按 task_stack 顺序扫描可合并的成果任务，逐段生成并用换行合并（FR-52）。
    非本集合内的 token 保留在栈内顺序不变。
    """
    segments: List[str] = []
    consumed: List[str] = []
    summarize_pending_batches: List[List[str]] = []

    for token in task_stack:
        if token not in MERGEABLE_GENERATOR_TASKS:
            continue

        if token == "TASK_INV_ADD":
            segments.append(generator.handle_inv_add(state))
        elif token == "TASK_INV_CHECK":
            segments.append(generator.handle_inv_check(state))
        elif token == "TASK_INV_COMMIT":
            segments.append(generator.handle_inv_commit(state))
        elif token == "TASK_GAP_CALC":
            segments.append(generator.handle_gap_calc(state))
        elif token == "TASK_DIRECT_REPLY":
            sec9 = try_error_code_direct_reply(state)
            degraded_reply = get_runtime_bundle(state).get("degraded_reply")
            if sec9:
                segments.append(sec9)
            elif degraded_reply:
                segments.append(degraded_reply)
            else:
                segments.append(await generator.handle_direct_reply(state))
        elif token == "TASK_PROFILE_SYNC":
            segments.append(generator.handle_profile_sync(state))
        elif token == "TASK_SUMMARIZE":
            segments.append(generator.handle_summarize(state))
            pend = lb.get("pending_tasks") or []
            if pend:
                logger.info(
                    "[Generator] 处理完 summarize 后，发现 pending_tasks: %s",
                    pend,
                )
                summarize_pending_batches.append(list(pend))
            lb.get("pending_tasks", []).clear()

        consumed.append(token)

    parts = [str(s).strip() for s in segments if s is not None and str(s).strip()]
    merged = "\n\n".join(parts)

    if consumed and not merged:
        logger.warning(
            "[Generator] 成果类任务合并话术为空，使用 FR-61 兜底: consumed=%s",
            consumed,
        )
        merged = message_merged_segments_empty(consumed)

    removal_left = Counter(consumed)
    new_stack: List[str] = []
    for t in task_stack:
        if removal_left[t] > 0:
            removal_left[t] -= 1
            continue
        new_stack.append(t)

    for batch in summarize_pending_batches:
        for t in batch:
            if t not in new_stack:
                new_stack.append(t)
    if summarize_pending_batches:
        logger.info(
            "[Generator] summarize 处理完成后，task_stack 更新为: %s",
            new_stack,
        )

    return merged, new_stack


async def generator_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 节点入口。

    路由：
      TASK_DIRECT_REPLY → 闲聊，LLM 生成回复
      TASK_CLARIFY      → 歧义，展示候选菜谱列表
    """
    task_stack: List[str] = state.get("task_stack", []).copy()
    incoming_task_stack: List[str] = list(task_stack)
    lb: Dict[str, Any] = copy.deepcopy(get_runtime_bundle(state))

    print(f"🔍 [Generator] task_stack: {task_stack}")          
    print(f"🔍 [Generator] runtime_bundle 状态: {list(lb.keys())}")

    generator = GeneratorNode()
    reply = ""
    loop_guard_count = int(state.get("loop_guard_count", 0)) + 1

    # ════════════════════════════════════════════════════════════
    # 1. 最高优先级：处理打断/阻塞型任务 (如歧义澄清)
    # ════════════════════════════════════════════════════════════
    if "TASK_CLARIFY" in task_stack:
        # 如果有澄清任务，必须立即停止其他汇报，优先向用户提问
        logger.info("[Generator] 处理歧义澄清任务")
        clarify_reply = generator.handle_clarify(state)
        lb_out = copy.deepcopy(lb)
        if lb_out.get("clarify_error"):
            lb_out["clarify_error"] = None
        new_message = AIMessage(content=clarify_reply)
        cand_raw = lb.get("recipe_candidates", [])
        has_candidates = bool(generator._normalize_candidate_titles(cand_raw))
        if has_candidates:
            # 等待用户选择：保留 TASK_CLARIFY；去掉 TASK_SEARCH 以免回路重复检索
            task_stack = consume_tasks(task_stack, ["TASK_SEARCH"])
        else:
            # 无可选候选：结束澄清轮次，消费 CLARIFY（及 SEARCH）
            task_stack = consume_tasks(task_stack, ["TASK_CLARIFY", "TASK_SEARCH"])

        print(f"🔍 [Generator] 最终返回: task_stack={task_stack}")
        updated_messages = list(state.get("messages", [])) + [new_message]
        schedule_memory_keeper_after_reply(resolve_scope_id(state), updated_messages)
        ret = {
            "messages": updated_messages,
            "task_stack": task_stack,
            **_generator_slice_patch(clarify_reply, task_stack, loop_guard_count),
            **runtime_bundle_to_slice_patches(lb_out),
        }
        return ret


    # ════════════════════════════════════════════════════════════
    # 2. 成果收集：按 task_stack 顺序合并多条成果话术（FR-52），执行即出队本轮已处理项
    # ════════════════════════════════════════════════════════════

    reply, task_stack = await _collect_merged_generator_reply(
        generator, state, task_stack, lb
    )

    if not reply:
        logger.warning(
            "[Generator] FR-61：合并回复仍为空，使用全链路兜底；incoming_stack=%s remaining=%s",
            incoming_task_stack,
            task_stack,
        )
        reply = message_generator_empty_turn(incoming_task_stack)

    logger.info(f"[Generator] task_stack 处理完成，还存在任务: {task_stack}")
    new_message = AIMessage(content=reply)
    updated_messages = list(state.get("messages", [])) + [new_message]
    schedule_memory_keeper_after_reply(resolve_scope_id(state), updated_messages)

    print(f"🔍 [Generator] 最终返回: task_stack={task_stack}")
    slice_patches = runtime_bundle_to_slice_patches(lb)
    inv_patch = dict(slice_patches.get("inventory_state") or {})
    intents_round = list(state.get("intents") or [])
    if "recipe_adopt" in intents_round or state.get("primary_intent") == "recipe_adopt":
        inv_patch["recipe_use_confirmed"] = True  # 规格 §6.3：采纳后置位
        slice_patches["inventory_state"] = inv_patch
    return {
        "messages": updated_messages,
        "task_stack": task_stack,
        "loop_guard_count": loop_guard_count,
        **slice_patches,
        **_generator_slice_patch(reply, task_stack, loop_guard_count),
    }