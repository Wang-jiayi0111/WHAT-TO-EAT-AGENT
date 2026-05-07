import logging
from typing import Dict, Any, List
from pathlib import Path
from string import Template

# 导入项目内部依赖
from ..state import AgentState
from ..intent_priority import sort_intents_by_fr50
from ..slot_filling import (
    apply_slot_guards_to_task_stack,
    compute_missing_slots,
    merge_slots,
    normalize_legacy_entities_to_slots,
)
from .schema import IntentResult
from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings

# 配置日志
logger = logging.getLogger(__name__)

_RESTOCK_CONFIRM_PHRASES = frozenset(
    (
        "确认",
        "确定",
        "好的",
        "好",
        "行",
        "嗯",
        "可以",
        "入库",
        "就这样",
        "没错",
        "ok",
        "yes",
    )
)


def _is_restock_confirmation_message(text: str) -> bool:
    """§6.5.3：待补货预览时，短句确认（与 LLM 输出的 restock_confirm 槽位等价入口）。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in _RESTOCK_CONFIRM_PHRASES:
        return True
    compact = "".join(t.split())
    if compact in _RESTOCK_CONFIRM_PHRASES:
        return True
    if "确认" in t or "确定" in t:
        if len(t) <= 24:
            return True
    return False


def _restock_pending_confirm_shortcut(state: AgentState) -> Dict[str, Any] | None:
    """待确认的 add_preview + 用户短句确认 → 本轮直接走 TASK_INV_ADD + restock_confirm。"""
    if "TASK_CLARIFY" in state.get("task_stack", []):
        return None
    inv = state.get("inventory_state") or {}
    if inv.get("add_status") != "pending":
        return None
    preview = inv.get("add_preview") or {}
    if not preview.get("items"):
        return None
    if preview.get("unresolved"):
        return None
    messages = state.get("messages") or []
    if not messages:
        return None
    last = messages[-1]
    content = getattr(last, "content", str(last))
    if not _is_restock_confirmation_message(str(content)):
        return None
    details: Dict[str, Any] = {
        "intent": "inventory_add",
        "primary_intent": "inventory_add",
        "intents": ["inventory_add"],
        "secondary_intents": [],
        "confidence": 1.0,
        "needs_clarification": False,
        "task_stack": ["TASK_INV_ADD"],
        "entities": {},
        "slots": {"restock_confirm": True},
        "missing_slots": [],
        "reasoning": "rule: pending add_preview + confirm utterance (§6.5.3)",
    }
    return {
        "current_intent": "inventory_add",
        **details,
        "slots": {"restock_confirm": True},
        "control_state": _control_state_patch(state, details),
    }


class IntentClassifier:
    """
    意图识别与任务分发核心类。

    多意图：模型输出的 `intents` 顺序仅作参考，路由层按 FR-50 调用
    `sort_intents_by_fr50` 后再生成 `primary_intent` 与 `task_stack`（T-007）。
    """

    # 意图到任务标签的映射表
    INTENT_TASK_MAPPING = {
        "profile_sync": ["TASK_PROFILE_SYNC"],      # 同步/更新偏好
        "recipe_search": ["TASK_SEARCH"],           # 查询菜单
        "inventory_commit": ["TASK_INV_COMMIT"],    # 确认菜单更新库存
        "inventory_check": ["TASK_INV_CHECK"],      # 查询库存
        "inventory_add": ["TASK_INV_ADD"],          # 增加库存
        "shopping_list": ["TASK_GAP_CALC"],         # 生成清单
        "dietary_advice": ["TASK_DIRECT_REPLY"],    # 营养健康问答（不检索菜谱）
        "help": ["TASK_DIRECT_REPLY"],              # 使用帮助 / 能做什么
        "out_of_scope": ["TASK_DIRECT_REPLY"],      # 超出业务范围婉拒
        "recipe_adopt": ["TASK_DIRECT_REPLY"],       # 确认采纳当前推荐菜谱
        "user_clarify": ["TASK_CLARIFY"],           # 向用户追问
        "general_chat": ["TASK_DIRECT_REPLY"],       # 日常闲聊
    }

    def __init__(self):
        try:
            settings = Settings()
            self.clarify_threshold = settings.get_intent_clarify_threshold()
            # 获取主力模型并注入结构化输出能力
            base_llm = LLMFactory.get_llm(settings)
            self.llm = base_llm.with_structured_output(IntentResult)
            
            # 加载外部 Prompt 模板
            prompt_path = Path(__file__).parent.parent / "prompts" / "intent_prompt.md"
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.template = f.read()
        except Exception as e:
            logger.error(f"IntentClassifier 初始化失败: {e}")
            raise

    def get_intent_details(self, state: AgentState) -> Dict[str, Any]:
        """
        调用 LLM 识别意图并映射任务栈
        """
        # 获取最新的一条用户消息
        latest_message = state["messages"][-1].content if state["messages"] else ""

        # 取最近 N 轮消息（排除最后一条，避免重复）
        recent_messages = state.get("messages", [])[:-1][-4:]  # 最多取最近4条
        if recent_messages:
            history_lines = []
            for msg in recent_messages:
                role = "用户" if msg.type == "human" else "助手"
                history_lines.append(f"{role}: {msg.content}")
            recent_history = "\n".join(history_lines)
        else:
            recent_history = "无"
        
        # 准备 Prompt 变量
        prompt = Template(self.template).safe_substitute(
            active_user_id=state.get("active_user_id", "default_user"),
            history_summary=state.get("conversation_summary", "无历史对话背景"),
            recent_history=recent_history, 
            user_input=latest_message
        )

        try:
            # 1. 执行 LLM 推理
            result: IntentResult = self.llm.invoke(prompt)
            logger.info(f"思考过程: {result.reasoning}")

            entities = dict(result.entities or {})
            raw_intents: List[str] = (
                list(result.intents) if result.intents else ["general_chat"]
            )
            # FR-50：多意图按优先级重排；primary 取仲裁后的首意图（非 LLM 原始顺序）
            intents_list = sort_intents_by_fr50(raw_intents)
            primary = intents_list[0]
            secondary = intents_list[1:]
            conf = float(result.confidence)

            slots = normalize_legacy_entities_to_slots(entities, intents_list)
            slots = merge_slots(slots, dict(result.slots or {}))
            rule_missing = compute_missing_slots(intents_list, slots, state)
            model_missing = list(result.missing_slots or [])
            missing = sorted(set(rule_missing) | set(model_missing))

            # 2. 置信度阈值 → needs_clarification（intent.confidence.clarify_threshold；FR-03 不写库类展开）
            if conf < self.clarify_threshold:
                return {
                    "intent": primary,
                    "primary_intent": primary,
                    "intents": intents_list,
                    "secondary_intents": secondary,
                    "confidence": conf,
                    "needs_clarification": True,
                    # 仅澄清，不映射 TASK_INV_* / PROFILE 写路径，避免低置信误写库
                    "task_stack": ["TASK_CLARIFY"],
                    "entities": entities,
                    "slots": slots,
                    "missing_slots": missing,
                    "reasoning": f"置信度低 ({conf} < {self.clarify_threshold}): {result.reasoning}",
                }

            # 3. 动态合成任务栈（顺序与 intents_list 一致 → FR-51）；§11.5 缺口裁剪并必要时插入 TASK_CLARIFY
            final_tasks = apply_slot_guards_to_task_stack(
                intents_list, self.INTENT_TASK_MAPPING, missing
            )
            needs_clarification = bool(missing)

            print(
                f"🔍 [Router] FR-50 仲裁后意图: {intents_list}（原始: {raw_intents}），"
                f"映射任务栈: {final_tasks}，missing_slots={missing}"
            )
            return {
                "intent": primary,
                "primary_intent": primary,
                "intents": intents_list,
                "secondary_intents": secondary,
                "confidence": conf,
                "needs_clarification": needs_clarification,
                "task_stack": final_tasks,
                "entities": entities,
                "slots": slots,
                "missing_slots": missing,
                "reasoning": result.reasoning,
            }

        except Exception as e:
            # 添加这一行，在测试终端中查看具体报错
            print(f"\n❌ LLM 调用失败，具体原因: {str(e)}")

            logger.error(f"意图识别过程崩溃: {e}")
            return {
                "intent": "general_chat",
                "primary_intent": "general_chat",
                "intents": ["general_chat"],
                "secondary_intents": [],
                "confidence": 0.0,
                "needs_clarification": True,
                "task_stack": ["TASK_DIRECT_REPLY"],
                "entities": {},
                "slots": {},
                "missing_slots": [],
                "reasoning": "系统解析异常，转入人工/简单模式",
            }

# 单例化分类器
_classifier = IntentClassifier()


def _control_state_patch(state: AgentState, details: Dict[str, Any]) -> Dict[str, Any]:
    """写入 control_state 切片（规格 §1.2.0），含路由实体与推理摘要。"""
    intent = details["intent"]
    patch: Dict[str, Any] = {
        "primary_intent": details.get("primary_intent", intent),
        "secondary_intents": list(details.get("secondary_intents") or []),
        "intents": list(details.get("intents") or [intent]),
        "task_stack": list(details["task_stack"]),
        "current_task": state.get("current_task"),
        "needs_clarification": details["needs_clarification"],
        "loop_guard_count": int(state.get("loop_guard_count") or 0),
        "slots": dict(details.get("slots") or {}),
        "missing_slots": list(details.get("missing_slots") or []),
        "confidence": float(details["confidence"]),
    }
    ent = details.get("entities")
    if ent is not None:
        patch["extracted_entities"] = dict(ent)
    if details.get("reasoning") is not None:
        patch["router_reasoning"] = str(details.get("reasoning") or "")
    return patch


def router_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 路由节点入口。

    输出对齐 FR-01 / 规格 §11.1：primary_intent、intents、confidence、needs_clarification，
    以及 §11.2 slots、§11.5 missing_slots 与任务栈守卫（T-031）。
    """
    if not state.get("messages"):
        stub = {
            "intent": "general_chat",
            "primary_intent": "general_chat",
            "intents": ["general_chat"],
            "secondary_intents": [],
            "confidence": 1.0,
            "needs_clarification": False,
            "task_stack": ["TASK_DIRECT_REPLY"],
            "slots": {},
            "missing_slots": [],
            "entities": {},
            "reasoning": "",
        }
        return {
            "current_intent": "general_chat",
            **stub,
            "control_state": _control_state_patch(state, stub),
        }

    shortcut = _restock_pending_confirm_shortcut(state)
    if shortcut is not None:
        logger.info("[Router] §6.5 补货预览待确认 → 规则命中确认短句，直出 TASK_INV_ADD")
        return shortcut

    # 执行意图识别
    task_stack = state.get("task_stack", [])
    print(f"🔍 [Router] 当前 task_stack: {task_stack}")

    if "TASK_CLARIFY" in task_stack:
        print("🔍 [Router] 检测到系统处于澄清等待状态，跳过 LLM 意图识别，直接放行！")
        return {}

    print(f"🔍 [Router] 识别用户意图，当前消息: {state['messages'][-1].content}")
    details = _classifier.get_intent_details(state)

    entities = details.get("entities") or {}
    slots_out = details.get("slots") or {}
    # 更新全局状态（扁平 + control_state 双写）
    return {
        "current_intent": details["intent"],
        "primary_intent": details.get("primary_intent", details["intent"]),
        "intents": details.get("intents", [details["intent"]]),
        "secondary_intents": details.get("secondary_intents", []),
        "confidence": details["confidence"],
        "needs_clarification": details["needs_clarification"],
        "task_stack": details["task_stack"],
        "slots": slots_out,
        "missing_slots": details.get("missing_slots", []),
        "control_state": _control_state_patch(state, details),
    }