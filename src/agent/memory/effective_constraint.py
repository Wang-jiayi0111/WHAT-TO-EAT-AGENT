"""
有效约束 **C**（规格 §3.5）：合并长期画像 + DB 短期状态 + L3 + L2 摘要片段；
供检索 query 增强与 §5.4 硬排除后过滤。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from ...libs.base.settings import Settings
from ...libs.base.user_profiles import UserProfileManager

logger = logging.getLogger(__name__)


def resolve_scope_id(state: Mapping[str, Any], settings: Optional[Settings] = None) -> str:
    """规格 §3.2 / §8：`household.default_id`，否则回落 `active_user_id`。"""
    st = settings or Settings()
    uid = state.get("active_user_id")
    fallback = str(uid).strip() if uid else "default_user"
    return st.get_scope_id(fallback)


def _unique_strs(items: Sequence[Any], *, min_len: int = 1) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in items or []:
        s = str(x).strip()
        if len(s) < min_len or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _merge_temporal(l3_lines: Sequence[str], db_conditions: Sequence[str]) -> List[str]:
    return _unique_strs(list(l3_lines or ()) + list(db_conditions or ()))


def build_effective_constraint(
    state: Mapping[str, Any],
    *,
    profile: Optional[MutableMapping[str, Any]] = None,
    scope_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    合并算法（规格 §3.5）：
    1. 读长期 + DB 短期 + memory_state.short_term_constraints
    2. hard_exclusions = allergens ∪ medical_restrictions（食材级关键词）
    3. temporal_conditions = L3 ∪ DB 活跃短期
    4. summary_snippet：L2 摘要截断
    """
    settings = Settings()
    sid = scope_id or resolve_scope_id(state, settings)

    if profile is None:
        try:
            upm = UserProfileManager(
                db_path=settings.get_user_profiles_db_path(),
                scope_id_for_migration=sid,
            )
            profile = upm.get_user_profile(sid) or {}
        except Exception as e:
            logger.warning("effective_constraint: load profile failed: %s", e)
            profile = {}

    mem = state.get("memory_state") or {}
    l3 = mem.get("short_term_constraints") or []
    if not isinstance(l3, list):
        l3 = []
    l3_strs = _unique_strs([str(x) for x in l3])

    db_short = profile.get("short_term_states") or []
    if not isinstance(db_short, list):
        db_short = []

    temporal_conditions = _merge_temporal(l3_strs, [str(x) for x in db_short])

    allergens = profile.get("allergens") or []
    medical = profile.get("medical_restrictions") or []
    if not isinstance(allergens, list):
        allergens = []
    if not isinstance(medical, list):
        medical = []

    hard_exclusions = _unique_strs(list(allergens) + list(medical), min_len=2)

    tt = profile.get("taste_tags") or {}
    if not isinstance(tt, dict):
        tt = {}
    like = tt.get("like") or []
    dislike = tt.get("dislike") or []
    soft_pos = _unique_strs(list(like))
    soft_neg = _unique_strs(list(dislike))

    for x in profile.get("disliked_foods") or []:
        if x and str(x).strip() not in soft_neg:
            soft_neg.append(str(x).strip())

    dietary_target = (profile.get("dietary_target") or "").strip() or None

    summary_raw = (mem.get("conversation_summary") or state.get("conversation_summary") or "").strip()
    summary_snippet: Optional[str]
    if summary_raw:
        summary_snippet = summary_raw[:500] + ("…" if len(summary_raw) > 500 else "")
    else:
        summary_snippet = None

    return {
        "scope_id": sid,
        "hard_exclusions": hard_exclusions,
        "soft_negative_hints": soft_neg,
        "soft_positive_hints": soft_pos,
        "dietary_target": dietary_target,
        "temporal_conditions": temporal_conditions,
        "summary_snippet": summary_snippet,
    }


def augment_search_query(base_query: str, c: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    """
    检索前将 **C** 注入 query（规格 §5.1 步 2；在 T-010 augment 基础上统一口径）。
    硬排除仍以 §5.4 列表过滤为准，此处仅增强语义与偏好上下文。
    """
    q = (base_query or "").strip()
    chunks: List[str] = []

    dt = c.get("dietary_target")
    if isinstance(dt, str) and dt.strip():
        chunks.append(f"饮食目标：{dt.strip()}")

    sp = c.get("soft_positive_hints") or []
    if isinstance(sp, list) and sp:
        chunks.append("偏好：" + "、".join(str(x) for x in sp[:8]))

    sn = c.get("soft_negative_hints") or []
    if isinstance(sn, list) and sn:
        chunks.append("不喜：" + "、".join(str(x) for x in sn[:8]))

    tc = c.get("temporal_conditions") or []
    if isinstance(tc, list) and tc:
        chunks.append("近期状态：" + "；".join(str(x) for x in tc[:10]))

    hx = c.get("hard_exclusions") or []
    if isinstance(hx, list) and hx:
        chunks.append("禁忌食材（须避开）：" + "、".join(str(x) for x in hx[:12]))

    ss = c.get("summary_snippet")
    if isinstance(ss, str) and ss.strip():
        chunks.append("对话摘要要点：" + ss.strip()[:200])

    ac = state.get("active_constraints") or {}
    if isinstance(ac, dict):
        for k, v in ac.items():
            if v is None:
                continue
            line = f"{k}: {v}".strip()
            if line:
                chunks.append(line)

    if not chunks:
        return q
    tail = " ".join(chunks)
    if not q:
        return f"[饮食约束] {tail}"
    return f"{q} [饮食约束] {tail}"


def _text_matches_kw(title: str, content: str, kw: str) -> bool:
    if not kw or len(kw.strip()) < 2:
        return False
    t, c2 = title or "", content or ""
    k = kw.strip()
    if all(ord(ch) < 128 for ch in k):
        kl = k.lower()
        return kl in t.lower() or kl in c2.lower()
    return k in t or k in c2


def effective_constraint_has_retryable_soft_signals(c: Mapping[str, Any]) -> bool:
    """是否存在可通过「放宽」改善检索的软约束（FR-24；§3.5）。"""
    sn = c.get("soft_negative_hints") or []
    sp = c.get("soft_positive_hints") or []
    tc = c.get("temporal_conditions") or []
    dt = c.get("dietary_target")
    ss = c.get("summary_snippet")
    if isinstance(sn, list) and any(str(x).strip() for x in sn):
        return True
    if isinstance(sp, list) and any(str(x).strip() for x in sp):
        return True
    if isinstance(tc, list) and any(str(x).strip() for x in tc):
        return True
    if isinstance(dt, str) and dt.strip():
        return True
    if isinstance(ss, str) and ss.strip():
        return True
    return False


def relaxed_effective_constraint_for_search_retry(c: Mapping[str, Any]) -> Dict[str, Any]:
    """
    FR-24：保留 hard_exclusions / scope_id，清空检索增强用的软字段后重试阶段一。
    """
    base = dict(c)
    base["soft_negative_hints"] = []
    base["soft_positive_hints"] = []
    base["temporal_conditions"] = []
    base["dietary_target"] = None
    base["summary_snippet"] = None
    return base


def filter_recipes_by_hard_exclusions(
    recipes: List[Dict[str, Any]],
    hard_exclusions: Sequence[str],
) -> List[Dict[str, Any]]:
    """
    规格 §5.4：若 C.hard_exclusions 中任一关键词命中菜名或摘要字段 → 剔除该候选。
    """
    if not recipes or not hard_exclusions:
        return list(recipes)
    kws = [str(x).strip() for x in hard_exclusions if str(x).strip()]
    if not kws:
        return list(recipes)

    kept: List[Dict[str, Any]] = []
    for r in recipes:
        title = str(r.get("title") or "")
        content = str(r.get("content") or r.get("snippet") or "")
        bad = False
        for kw in kws:
            if _text_matches_kw(title, content, kw):
                bad = True
                logger.info(
                    "§5.4 filter: excluded recipe title=%r keyword=%r",
                    title[:80],
                    kw,
                )
                break
        if not bad:
            kept.append(r)
    return kept
