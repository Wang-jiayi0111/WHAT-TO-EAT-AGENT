import logging
from typing import Dict, Any, List
from pathlib import Path
from string import Template

# 导入项目内部依赖
from ..state import AgentState
from .schema import IntentResult
from ...libs.adapters.llm.llm_factory import LLMFactory
from ...libs.base.settings import Settings

# 配置日志
logger = logging.getLogger(__name__)

class IntentClassifier:
    """
    意图识别与任务分发核心类
    """

    # 意图到任务标签的映射表
    INTENT_TASK_MAPPING = {
        "profile_sync": ["TASK_PROFILE_SYNC"],      # 同步/更新偏好
        "recipe_search": ["TASK_SEARCH"],           # 查询菜单  
        "inventory_check": ["TASK_INV_CHECK"],      # 查询库存
        "inventory_commit": ["TASK_INV_COMMIT"],    # 确认菜单更新库存
        "inventory_add":    ["TASK_INV_ADD"],       # 增加库存
        "shopping_list": ["TASK_GAP_CALC"],         # 生成清单 
        "user_clarify": ["TASK_CLARIFY"],           # 向用户追问
        "general_chat": ["TASK_DIRECT_REPLY"]       # 日常闲聊
    }

    def __init__(self):
        try:
            settings = Settings()
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

            # 2. 置信度阈值拦截
            if result.confidence < 0.6:
                return {
                    "intent": "clarify",
                    "task_stack": ["TASK_CLARIFY"],
                    "entities": result.entities,
                    "reasoning": f"置信度低 ({result.confidence}): {result.reasoning}"
                }

            # 3. 动态合成任务栈
            final_tasks = []
            for intent in result.intents:
                tasks = self.INTENT_TASK_MAPPING.get(intent, ["TASK_DIRECT_REPLY"])
                for t in tasks:
                    if t not in final_tasks: # 去重
                        final_tasks.append(t)

            print(f"🔍 [Router] 识别到意图: {result.intents}, 映射任务栈: {final_tasks}")
            return {
                "intent": result.intents[0] if result.intents else "general_chat",
                "task_stack": final_tasks,
                "entities": result.entities,
                "reasoning": result.reasoning
            }

        except Exception as e:
            # 添加这一行，在测试终端中查看具体报错
            print(f"\n❌ LLM 调用失败，具体原因: {str(e)}") 
            
            logger.error(f"意图识别过程崩溃: {e}")
            return {
                "intent": "general_chat",
                "task_stack": ["TASK_DIRECT_REPLY"],
                "entities": {},
                "reasoning": "系统解析异常，转入人工/简单模式"
            }

# 单例化分类器
_classifier = IntentClassifier()

def router_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 路由节点入口
    """
    if not state.get("messages"):
        return {"current_intent": "general_chat", "task_stack": ["TASK_DIRECT_REPLY"]}

    # 执行意图识别
    task_stack = state.get("task_stack", [])
    print(f"🔍 [Router] 当前 task_stack: {task_stack}")

    if "TASK_CLARIFY" in task_stack:
        print("🔍 [Router] 检测到系统处于澄清等待状态，跳过 LLM 意图识别，直接放行！")
        return {}
    
    print(f"🔍 [Router] 识别用户意图，当前消息: {state['messages'][-1].content}")
    details = _classifier.get_intent_details(state)

    # 更新全局状态
    return {
        "current_intent": details["intent"],
        "task_stack": details["task_stack"],
        "logistics_buffer": {
            "extracted_entities": details.get("entities", {}),
            "router_reasoning": details.get("reasoning", "未提供推理理由")
        }
    }