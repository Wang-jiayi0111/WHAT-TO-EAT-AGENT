"""
ClarifyResolver - 解析用户对候选菜谱的选择

当 task_stack 包含 TASK_CLARIFY 且用户已回复时，
解析用户输入（数字 or 菜名），锁定具体菜谱，
更新 logistics_buffer 并把 task_stack 推进到下一步。
"""
import logging
from typing import Dict, Any, List, Optional

from ..state import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _parse_user_choice(
    user_input: str,
    candidates: List[str]  
) -> Optional[str]:
    """
    解析用户的选择，支持：
    - 数字："1" / "第一个" / "第1个"
    - 菜名关键词："南派" / "南派红烧肉"

    Returns:
        匹配到的候选菜谱 dict，或 None（无法识别）
    """
    text = user_input.strip()

    # 尝试数字匹配
    digit_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                 "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    for ch, num in digit_map.items():
        text = text.replace(f"第{ch}个", str(num)).replace(ch, str(num))

    import re
    num_match = re.search(r"\d+", text)
    if num_match:
        idx = int(num_match.group()) - 1  # 转为 0-based
        print(f'🔍 [ClarifyResolver] 解析到数字选择: {idx+1}')  # 调试信息
        if 0 <= idx < len(candidates):
            return candidates[idx]

    # 尝试菜名关键词匹配
    text_lower = text.lower()
    for candidate in candidates:
        title = candidate.get("title", "").lower()
        if text_lower in title or title in text_lower:
            return candidate

    return None


def clarify_resolver_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph 节点：解析用户对歧义菜谱的选择。

    触发条件：上一轮 task_stack 含 TASK_CLARIFY，
              且用户已发来新的回复消息。

    成功时：
      - logistics_buffer["selected_recipe_id"] 锁定为用户选择的菜谱
      - task_stack 更新为 ["TASK_SEARCH"]（触发 researcher 获取详情）

    失败时（无法识别）：
      - 保留 TASK_CLARIFY，让 generator 再次询问
    """
    task_stack = state.get("task_stack", []).copy()
    curr_task = "TASK_CLARIFY"

    messages = state.get("messages", [])
    print(f"🔍 [ClarifyResolver] 取到消息{messages}")  # 调试信息

    logistics_buffer = state.get("logistics_buffer", {})
    candidates: List[str] = logistics_buffer.get("recipe_candidates", [])
    print(f"🔍 [ClarifyResolver] 取到候选菜谱{candidates}")  # 调试信息

    if not candidates:
        logger.warning("[ClarifyResolver] 没有候选菜谱，跳过")
        return {}

    if not messages:
        return {}

    # 取最新一条用户消息
    latest = messages[-1]
    user_input = latest.content if hasattr(latest, "content") else str(latest)
    
    print(f"🔍 [ClarifyResolver] 最新消息: {latest}" + f"用户输入: {user_input}")  # 调试信息

    chosen = _parse_user_choice(user_input, candidates)
    print(f"🔍 [ClarifyResolver] 解析用户选择: {chosen}")  # 调试信息

    if chosen:
        task_stack.remove(curr_task)
        task_stack.append("TASK_SEARCH")  # 选择后直接进入搜索详情阶段

        print(f'[ClarifyResolver] task_stack 更新为: {task_stack}')  # 调试信息
        logger.info(f"[ClarifyResolver] 用户选择: {chosen}")
        new_buffer = {
            **logistics_buffer,
            "selected_recipe_title": chosen, # 菜名即 Title
            "recipe_candidates": [],
        }
        
        return {
            "logistics_buffer": new_buffer,
            "task_stack": task_stack,
        }
    else:
        logger.info(f"[ClarifyResolver] 无法解析用户输入: {user_input!r}，重新询问")
        return {
            "task_stack": ["TASK_CLARIFY"],  # 保留，让 generator 再次询问
        }