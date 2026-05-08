"""
规格定义的错误码 → 用户可见话术（**FR-60**：可理解、可操作）。

与 `docs/规格设计.md` 错误码章节对齐；扩展码（实现侧）：`COMMIT_RECIPE_MISMATCH`。
"""
from __future__ import annotations

from typing import Any, Mapping, Optional


def message_recipe_search_empty(*, soft_retry_attempted: bool = False) -> str:
    """`RECIPE_SEARCH_EMPTY`"""
    if soft_retry_attempted:
        return (
            "在当前条件下没有找到匹配的菜谱；系统已自动放宽口味偏好、近期饮食状态与摘要中的偏好描述后再次检索，仍未找到结果。"
            "您可以换个菜名或说法再试；若有食材禁忌，结果也会被过滤，可选范围会相应变窄。"
        )
    return (
        "暂时没有找到匹配的菜谱。您可以换个菜名、口味或食材关键词再试试；"
        "若有忌口或过敏等硬约束，可选范围也会变窄。"
    )


def message_recipe_source_not_found() -> str:
    """`RECIPE_SOURCE_NOT_FOUND`"""
    return (
        "没有在本地找到该菜谱的完整文档，暂时无法读取用料清单。"
        "请核对菜名或换一道菜后再试。"
    )


def message_recipe_parse_failed() -> str:
    """`RECIPE_PARSE_FAILED`"""
    return (
        "菜谱文档已找到，但未能解析出可靠的用料清单，暂时无法生成购物建议或按菜谱扣减库存。"
        "请换一道菜或稍后再试。"
    )


def message_inventory_write_failed(
    error_detail: Optional[str] = None,
    *,
    operation_hint: str = "写入库存",
) -> str:
    """`INVENTORY_WRITE_FAILED`（扣减 / 补货共用码，用 operation_hint 区分语境）。"""
    base = (
        f"**未能成功{operation_hint}**（本地数据库写入失败）。"
        "请稍后再试；若多次失败，请检查本机 `inventory.db` 是否可写。"
    )
    d = (error_detail or "").strip()
    if d and d not in base:
        return f"{base}\n\n详情：{d}"
    return base


def message_inventory_add_unparsed() -> str:
    """`INVENTORY_ADD_UNPARSED`"""
    return (
        "没能从您的话里确定买了哪些食材、各多少量（需带单位）。"
        "请再说具体一点，例如「买了鸡蛋 12 个」。"
    )


def message_memory_keeper_failed() -> str:
    """`MEMORY_KEEPER_FAILED`（L4 异步；通常不阻断主回复）。"""
    return (
        "饮食偏好后台同步未全部完成，不影响本轮对话。"
        "若您担心未保存，可以再简要重复一次忌口或偏好。"
    )


def message_clarification_required() -> str:
    """`CLARIFICATION_REQUIRED`（元澄清 / 槽位缺失时的兜底，多数场景由专用节点覆盖）。"""
    return (
        "还需要您补充或确认一项信息，我才能继续。"
        "您可以按上一条提示回复，或再说得具体一点。"
    )


def message_gap_cache_miss() -> str:
    """`GAP_CACHE_MISS`"""
    return (
        "当前还没有可用的菜谱用料清单，无法按菜谱计算购物缺口。"
        "请先检索并锁定一道菜，或告诉我您要做的菜名。"
    )


def message_gap_basis_mismatch() -> str:
    """`GAP_BASIS_MISMATCH`（多见于缓存失效后已重算；可向用户解释「已按最新情况」）。"""
    return (
        "菜谱需求或库存刚更新，已按**最新**菜谱与库存重新计算购物清单。"
    )


def message_commit_recipe_mismatch() -> str:
    """`COMMIT_RECIPE_MISMATCH`（§6.3 菜名锚点与锁定菜谱不一致）。"""
    return (
        "您提到的菜名与当前锁定的菜谱不一致。"
        "请先选定要做的那一道，菜名与当前菜谱一致后再扣减库存。"
    )


def _unwrap_state(state: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]]:
    es = state.get("error_state") or {}
    ep = state.get("expert_payloads") or {}
    code = str(es.get("error_code") or ep.get("error_code") or "").strip()
    detail = str(es.get("error_detail") or "").strip()
    return code, detail, ep


def try_error_code_direct_reply(state: Mapping[str, Any]) -> Optional[str]:
    """
    当本轮为 `TASK_DIRECT_REPLY` 且存在已知规格错误码时，返回统一口径用户话术；
    否则返回 None，由 `degraded_reply` / LLM 分支接管。
    """
    code, detail, ep = _unwrap_state(state)
    if not code or code in ("None", "unknown", "recoverable_error", "success"):
        return None

    if code == "RECIPE_SEARCH_EMPTY":
        return message_recipe_search_empty(
            soft_retry_attempted=bool(ep.get("recipe_search_soft_retry_attempted")),
        )
    if code == "RECIPE_SOURCE_NOT_FOUND":
        return message_recipe_source_not_found()
    if code == "RECIPE_PARSE_FAILED":
        return message_recipe_parse_failed()
    if code == "MEMORY_KEEPER_FAILED":
        return message_memory_keeper_failed()
    if code == "CLARIFICATION_REQUIRED":
        return message_clarification_required()
    if code == "GAP_CACHE_MISS":
        return message_gap_cache_miss()
    if code == "GAP_BASIS_MISMATCH":
        return message_gap_basis_mismatch()

    return None


def user_message_for_inventory_failure(
    error_code: Optional[str],
    error_detail: Optional[str] = None,
    *,
    operation_hint: str = "写入库存",
) -> Optional[str]:
    """供 logistics 成果任务（扣减/补货）使用。"""
    c = str(error_code or "").strip()
    if c == "INVENTORY_WRITE_FAILED":
        return message_inventory_write_failed(error_detail, operation_hint=operation_hint)
    if c == "INVENTORY_ADD_UNPARSED":
        return message_inventory_add_unparsed()
    return None
