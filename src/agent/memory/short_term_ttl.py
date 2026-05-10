"""
短期状态 TTL 与物理清理（FR-13；规格 §3.4；T-013）。

每轮在 L3 前对当前 SCOPE_ID 执行 `user_short_term_states` 过期行删除，
避免长期污染 **C** 的 temporal 来源；与 `get_active_short_term_states` 懒标记互补。
"""
from __future__ import annotations

import logging

from ...libs.base.settings import Settings
from ...libs.base.user_profiles import UserProfileManager

logger = logging.getLogger(__name__)


def run_short_term_ttl_cleanup(scope_id: str) -> int:
    """
    物理删除本 scope 下已过期/已失活的短期状态行。返回删除行数。
    若配置关闭 `memory.short_term_ttl.purge_expired_on_turn` 则 no-op。
    """
    settings = Settings()
    if not settings.should_purge_short_term_expired_on_turn():
        return 0
    sid = (scope_id or "").strip() or "default_user"
    try:
        upm = UserProfileManager(
            db_path=settings.get_user_profiles_db_path(),
            scope_id_for_migration=settings.get_scope_id(),
        )
        n = upm.purge_expired_states(sid)
        if n:
            logger.info(
                "T-013 short_term TTL purge: removed %s row(s) scope_id=%r",
                n,
                sid,
            )
        return n
    except Exception as e:
        logger.warning("T-013 short_term TTL purge failed scope_id=%r: %s", sid, e)
        return 0
