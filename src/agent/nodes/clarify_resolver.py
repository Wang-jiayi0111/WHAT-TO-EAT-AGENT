"""
ClarifyResolver - 解析用户对候选菜谱的选择

当 task_stack 包含 TASK_CLARIFY 且用户已回复时，
解析用户输入（数字 or 菜名），锁定具体菜谱，
更新运行时 bundle（经切片写回）并把 task_stack 推进到下一步。
"""
import copy
import logging
from typing import Dict, Any, List, Optional

from ..state import AgentState
from ..state_accessors import get_runtime_bundle
from ..state_sync import runtime_bundle_to_slice_patches
from ..task_stack import consume_tasks

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _normalize_candidates(raw_candidates: List[Any]) -> List[Dict[str, Any]]:
    """将候选统一标准化为 [{title: str, raw: Any}]。"""
    normalized: List[Dict[str, Any]] = []
    for item in raw_candidates or []:
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

        if not title:
            continue
        normalized.append({"title": title, "raw": item})
    return normalized


def _parse_user_choice(
    user_input: str,
    candidates: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
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
      - 在运行时 bundle / 切片中锁定选定菜谱
      - task_stack 含 ["TASK_SEARCH"]（触发 researcher 获取详情）

    失败时（无法识别）：
      - 保留 TASK_CLARIFY，让 generator 再次询问
    """
    task_stack = state.get("task_stack", []).copy()

    messages = state.get("messages", [])
    print(f"🔍 [ClarifyResolver] 取到消息{messages}")  # 调试信息

    logistics_buffer = copy.deepcopy(get_runtime_bundle(state))
    raw_candidates = logistics_buffer.get("recipe_candidates", [])
    candidates = _normalize_candidates(raw_candidates)
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

    try:
        chosen = _parse_user_choice(user_input, candidates)
    except Exception as exc:
        logger.warning("[ClarifyResolver] 解析异常，进入澄清兜底: %s", exc)
        chosen = None
    print(f"🔍 [ClarifyResolver] 解析用户选择: {chosen}")  # 调试信息

    if chosen:
        task_stack = consume_tasks(task_stack, ["TASK_CLARIFY"])
        if "TASK_SEARCH" not in task_stack:
            task_stack.append("TASK_SEARCH")  # 选择后直接进入搜索详情阶段

        print(f'[ClarifyResolver] task_stack 更新为: {task_stack}')  # 调试信息
        logger.info(f"[ClarifyResolver] 用户选择: {chosen}")
        new_buffer = {
            **logistics_buffer,
            "selected_recipe_title": chosen.get("title"), # 菜名即 Title
            "recipe_candidates": [],
        }
        
        return {
            "task_stack": task_stack,
            **runtime_bundle_to_slice_patches(new_buffer),
        }
    else:
        logger.info(f"[ClarifyResolver] 无法解析用户输入: {user_input!r}，重新询问")
        lb2 = {
                **logistics_buffer,
                "clarify_error": "invalid_choice",
            }
        return {
            "task_stack": ["TASK_CLARIFY"],  # 保留，让 generator 再次询问
            **runtime_bundle_to_slice_patches(lb2),
        }