"""
L3 当轮约束节点（规格 §4.3；T-010）。

仅写入 memory_state.short_term_constraints（及可选 memory_confidence）；
不误改 task_stack、recipe_state、inventory_state。

每轮先前序执行 T-013：`user_short_term_states` 过期物理清理（FR-13）。
"""
import logging

from ..effective_constraint import resolve_scope_id
from ..l3_short_term import build_l3_memory_patch
from ..short_term_ttl import run_short_term_ttl_cleanup
from ..state import AgentState

logger = logging.getLogger(__name__)


async def short_term_constraints_node(state: AgentState) -> AgentState:
    """提取最新用户句中的短期约束，合并入 memory_state。"""
    run_short_term_ttl_cleanup(resolve_scope_id(state))
    patch = build_l3_memory_patch(state)
    if patch:
        n = len((patch.get("memory_state") or {}).get("short_term_constraints") or [])
        logger.info("L3 short_term: merged constraints count=%s", n)
    return patch
