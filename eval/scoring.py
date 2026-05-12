"""
T-042：按开发计划 §5.1～5.4 从 E2E 采集 JSON 计算分层指标与 §5.6 加权总分。

说明：
- **效率层**：仅输出原始量（耗时、token、mcp 次数），**不参与**加权总分。
- **幻觉 / 忌口 / 澄清话术 / 回复整体**：默认由 **LLM** 评判（`eval/scoring_llm.py`，单一 prompt：`src/agent/prompts/eval_judge_quality.md`）；可用 `--no-llm` 回退启发式幻觉。
- NDCG@k：fixture 未提供分级相关性标注时记为 **N/A**（§5.1）。
- **`golden_recipe_ids`（检索）**：
  - **召回（recall）**：候选列表中是否出现**任一**金标（OR）；子项 `recall_hit_at_k` / `retrieval_recall` 同源。
  - **准确率（Top-1 accuracy）**：排序**第一条**候选（标题优先，否则首条 id）是否与**任一**金标语干匹配（Hit@1）。
  - 层总分：`0.4×召回 + 0.3×Top1准确率 + 0.3×名次分`（名次分=`1/best_rank`）。
- **清单操作（§7）**：若 `expected.shopping_list_assert` 含约束，则计算 **`shopping_list_ops`** 层（比对末轮 **`inventory_state`**：`shopping_list_overlay`、`cached_shopping_gap`）；并与检索/生成/对话 **四档加权**（见 `DEFAULT_WEIGHTS_WITH_SHOPPING_LIST`）；可设 **`strict: true`** 不满分时总分封顶。
- **多意图（对话层）**：可选 **`expected.intents`**（字符串列表）。与末轮快照 **`intents`** 比对：**顺序无关**；**实际可多可少**，按 **子集召回** 计分——每个期望标签在 `intents` 中至少出现一次即记 1 分，再对去重后的期望列表取平均。若同时声明 **`primary_intent`**，则 **主意图匹配** 与 **多意图召回** 各占一半后平均为对话层 `intent_match` 总分（仅声明其一则只该项生效；均未声明则意图子项记 1.0）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


# 效率层不纳入总分；权重仅覆盖检索 / 生成 / 对话（总和为 1）
DEFAULT_WEIGHTS = {
    "retrieval": 0.35,
    "generation": 0.325,
    "dialogue": 0.325,
}

# 当用例含 `expected.shopping_list_assert` 时，增加「清单操作」一层（与 R+I+gap 严格对齐）
DEFAULT_WEIGHTS_WITH_SHOPPING_LIST = {
    "retrieval": 0.28,
    "generation": 0.27,
    "dialogue": 0.25,
    "shopping_list_ops": 0.20,
}

# 检索层内部：召回 / Top-1 准确率 / 名次分（与 §5.1 表格对齐，三者之和为 1）
RETRIEVAL_AGG_WEIGHT_RECALL = 0.4
RETRIEVAL_AGG_WEIGHT_TOP1_ACCURACY = 0.3
RETRIEVAL_AGG_WEIGHT_RANK = 0.3


def _na(value: Optional[float] = None) -> Dict[str, Any]:
    return {"status": "N/A", "score": value}


def _ok(score: float, **extra: Any) -> Dict[str, Any]:
    out = {"status": "ok", "score": float(max(0.0, min(1.0, score)))}
    out.update(extra)
    return out


def stem_from_golden_id(gid: str) -> str:
    s = str(gid).strip()
    if s.startswith("recipe_id_"):
        return s[len("recipe_id_") :].strip()
    return s


def _candidate_titles_and_ids_from_turn_snapshots(
    turns: Sequence[Mapping[str, Any]],
) -> Tuple[List[str], List[str]]:
    titles: List[str] = []
    ids: List[str] = []
    for t in turns:
        snap = t.get("snapshot") or {}
        ep = snap.get("expert_payloads") or {}
        rb = snap.get("runtime_bundle") or {}
        rs = snap.get("recipe_state") or {}
        for r in ep.get("search_results") or []:
            if isinstance(r, dict):
                tid = str(r.get("id") or "").strip()
                tt = str(r.get("title") or "").strip()
                if tid:
                    ids.append(tid)
                if tt:
                    titles.append(tt)
        for c in rb.get("recipe_candidates") or rs.get("recipe_candidates") or []:
            if isinstance(c, dict):
                tt = str(c.get("title") or c.get("name") or "").strip()
                if tt:
                    titles.append(tt)
            else:
                s = str(c).strip()
                if s:
                    titles.append(s)
        locked = rs.get("recipe_title_locked") or rs.get("selected_recipe_title")
        if locked:
            titles.append(str(locked).strip())
        detail = ep.get("recipe_detail")
        if isinstance(detail, dict) and detail.get("title"):
            titles.append(str(detail["title"]).strip())
    # 去重保序
    seen: set[str] = set()
    ut: List[str] = []
    for x in titles:
        if x and x not in seen:
            seen.add(x)
            ut.append(x)
    ui: List[str] = []
    seen_i: set[str] = set()
    for x in ids:
        if x and x not in seen_i:
            seen_i.add(x)
            ui.append(x)
    return ut, ui


def _match_golden_to_rank(
    golden_stem: str, titles: Sequence[str], ids: Sequence[str]
) -> Tuple[bool, Optional[int]]:
    """returns (hit, 1-based rank or None)"""
    g = golden_stem.strip().lower()
    if not g:
        return False, None
    # id 路径匹配（chunk uuid 或文件路径）
    for i, rid in enumerate(ids):
        if g in str(rid).lower().replace("\\", "/"):
            return True, i + 1
    for rank, title in enumerate(titles, start=1):
        tl = str(title).lower()
        if g in tl or tl in g:
            return True, rank
    return False, None


def _top1_matches_any_golden(
    titles: Sequence[str], ids: Sequence[str], goldens: Sequence[str]
) -> bool:
    """检索 Top-1 准确率：首条候选标题（若无则首条 id）是否匹配任一 `golden_recipe_ids` 词干。"""
    if not goldens:
        return False
    probes: List[str] = []
    if titles:
        probes.append(str(titles[0]))
    if ids:
        probes.append(str(ids[0]))
    for raw in probes:
        pl = str(raw).lower().replace("\\", "/")
        for gid in goldens:
            stem = stem_from_golden_id(str(gid)).strip().lower()
            if not stem:
                continue
            if stem in pl or pl in stem:
                return True
    return False


def score_retrieval_layer(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    *,
    retrieval_must_hit: bool = True,
) -> Dict[str, Any]:
    goldens = list(expected.get("golden_recipe_ids") or [])
    titles, ids = _candidate_titles_and_ids_from_turn_snapshots(turns)
    if not goldens:
        return {
            "layer": "retrieval",
            "aggregate_score": None,
            "hard_fail": False,
            "submetrics": {
                "recall_hit_at_k": _na(),
                "retrieval_recall": _na(),
                "retrieval_accuracy_top1": _na(),
                "golden_rank": _na(),
                "mrr": _na(),
                "ndcg_at_k": _na(),
                "note": "无 golden_recipe_ids，检索层不参加均分",
            },
        }

    matched_count = 0
    ranks: List[int] = []
    first_hit_reciprocal = 0.0
    for gid in goldens:
        stem = stem_from_golden_id(gid)
        hit, rank = _match_golden_to_rank(stem, titles, ids)
        if hit and rank is not None:
            matched_count += 1
            ranks.append(rank)
            if first_hit_reciprocal == 0.0:
                first_hit_reciprocal = 1.0 / float(rank)

    # 召回：多金标 OR——任一出现在候选中即视为召回成功（§5.1 Hit@k）
    any_hit = matched_count >= 1
    recall_score = 1.0 if any_hit else 0.0
    # Top-1 准确率：首条候选是否为金标之一
    top1_acc = 1.0 if _top1_matches_any_golden(titles, ids, goldens) else 0.0
    # 单用例 MRR：按金标列表顺序首个命中的倒数（§5.1）
    mrr = first_hit_reciprocal if goldens else 0.0
    best_rank = min(ranks) if ranks else None
    rank_score = 1.0 / float(best_rank) if best_rank else 0.0

    aggregate = (
        RETRIEVAL_AGG_WEIGHT_RECALL * recall_score
        + RETRIEVAL_AGG_WEIGHT_TOP1_ACCURACY * top1_acc
        + RETRIEVAL_AGG_WEIGHT_RANK * rank_score
    )
    hard_fail = bool(retrieval_must_hit and goldens and not any_hit)

    return {
        "layer": "retrieval",
        "aggregate_score": aggregate,
        "hard_fail": hard_fail,
        "submetrics": {
            "recall_hit_at_k": _ok(
                recall_score,
                matched_golden_count=matched_count,
                golden_variant_count=len(goldens),
                semantics="OR_any_golden",
            ),
            "retrieval_recall": _ok(
                recall_score,
                matched_golden_count=matched_count,
                golden_variant_count=len(goldens),
                semantics="OR_any_golden",
            ),
            "retrieval_accuracy_top1": _ok(
                top1_acc,
                top1_title_sample=titles[0] if titles else None,
                top1_id_sample=ids[0] if ids else None,
            ),
            "golden_rank": _ok(
                rank_score,
                best_rank_1based=best_rank,
                candidate_titles_sample=titles[:12],
            ),
            "mrr": _ok(mrr),
            "ndcg_at_k": _na(),
            "note": "NDCG 需 fixture 分级相关性；当前未提供 → N/A",
        },
    }


def _ingredient_names_from_r(detail: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    ing = detail.get("ingredients")
    if isinstance(ing, list):
        for row in ing:
            if isinstance(row, dict) and row.get("name"):
                out.add(str(row["name"]).strip().lower())
    return out


def _latest_recipe_detail(
    turns: Sequence[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    for t in reversed(turns):
        ep = (t.get("snapshot") or {}).get("expert_payloads") or {}
        d = ep.get("recipe_detail")
        if isinstance(d, dict) and (d.get("title") or d.get("ingredients")):
            return d
    return None


def _heuristic_hallucination_submetrics(
    detail: Mapping[str, Any], reply_all: str
) -> Tuple[Dict[str, Any], Optional[float]]:
    ing_names = _ingredient_names_from_r(detail)
    halluc_count = 0
    checked = 0
    if ing_names and reply_all.strip():
        for w in re.findall(r"[\u4e00-\u9fff]{2,12}", reply_all):
            wl = w.lower()
            if len(wl) < 2:
                continue
            checked += 1
            if not any(wl in n or n in wl for n in ing_names):
                if any(x in wl for x in ("盐", "糖", "油", "水", "葱", "姜", "蒜")):
                    continue
                halluc_count += 1
        denom = max(1, checked)
        halluc_rate = min(1.0, halluc_count / float(denom))
        sub = _ok(1.0 - halluc_rate, raw_halluc_tokens=halluc_count, checked_tokens=checked)
        return sub, halluc_rate
    return _na(), None


def score_generation_layer(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    *,
    llm_bundle: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    detail = _latest_recipe_detail(turns)
    reply_all = "\n".join(str(t.get("assistant_reply") or "") for t in turns)

    if not isinstance(detail, dict):
        return {
            "layer": "generation",
            "aggregate_score": None,
            "submetrics": {
                "r_accuracy": _na(),
                "llm_hallucination": _na(),
                "format_compliance": _na(),
                "note": "无 recipe_detail（R），生成层规则子项 N/A",
            },
        }

    goldens = [stem_from_golden_id(g) for g in (expected.get("golden_recipe_ids") or [])]
    title = str(detail.get("title") or "").strip().lower()
    acc = 0.0
    if goldens:
        acc = 1.0 if any(g.lower() in title or title in g.lower() for g in goldens if g) else 0.5
    else:
        acc = 1.0

    steps = detail.get("steps")
    fmt = 1.0 if isinstance(detail.get("ingredients"), list) and isinstance(steps, list) else 0.7

    sub_heur, _ = _heuristic_hallucination_submetrics(detail, reply_all)

    llm_ok = (
        llm_bundle is not None
        and llm_bundle.get("status") == "ok"
        and isinstance(llm_bundle.get("scores"), dict)
    )
    scores = (llm_bundle or {}).get("scores") or {} if llm_ok else {}

    if llm_ok:
        h_llm = float(scores.get("hallucination", 0.0))
        r_ov = float(scores.get("reply_overall", 0.0))
        gen_agg = 0.20 * acc + 0.15 * fmt + 0.35 * h_llm + 0.30 * r_ov
        sub_llm_h = _ok(h_llm, source="llm")
        sub_reply = _ok(r_ov, source="llm")
    else:
        h_score = float(sub_heur.get("score") or 0.0) if sub_heur.get("status") == "ok" else 0.0
        gen_agg = (
            0.45 * acc + 0.35 * h_score + 0.20 * fmt
            if sub_heur.get("status") == "ok"
            else (0.55 * acc + 0.45 * fmt)
        )
        sub_llm_h = _na()
        sub_reply = _na()
        if llm_bundle is not None and llm_bundle.get("status") != "ok":
            sub_llm_h = {
                "status": "error",
                "score": None,
                "error": llm_bundle.get("error"),
            }

    out_sub: Dict[str, Any] = {
        "r_accuracy": _ok(acc, recipe_title=title),
        "hallucination_llm": sub_llm_h if llm_ok else _na(),
        "hallucination_heuristic_fallback": sub_heur,
        "reply_overall_llm": sub_reply if llm_ok else _na(),
        "format_compliance": _ok(fmt),
    }
    if not llm_ok and isinstance(llm_bundle, dict) and llm_bundle.get("status") == "error":
        out_sub["llm_judge_error"] = llm_bundle.get("error")

    return {
        "layer": "generation",
        "aggregate_score": gen_agg,
        "submetrics": out_sub,
    }


def _snapshot_intents_list(last_snap: Mapping[str, Any]) -> List[str]:
    """末轮快照中的意图列表（顶层或 control_state）。"""
    raw = last_snap.get("intents")
    if not raw and isinstance(last_snap.get("control_state"), dict):
        raw = (last_snap.get("control_state") or {}).get("intents")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        s = str(x).strip()
        if s:
            out.append(s)
    return out


def _expected_intents_unique(expected: Mapping[str, Any]) -> List[str]:
    raw = expected.get("intents")
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(str(x).strip() for x in raw if str(x).strip()))


def compute_intent_alignment_score(
    expected: Mapping[str, Any], last_snap: Mapping[str, Any]
) -> Tuple[float, Dict[str, Any]]:
    """
    对话层意图对齐分 ∈ [0,1]。

    - 若声明 ``expected.primary_intent``：主意图须与 ``last_snap.primary_intent`` 全等，贡献一项 0/1。
    - 若声明非空 ``expected.intents``：对去重后的每个期望标签，须在 ``last_snap.intents``（顺序无关）中出现；
      子集召回 = 命中数 / 期望去重个数；实际 ``intents`` 可含额外标签。
    - 两项均声明时取算术平均；仅一项声明时该项即总分；均未声明则总分 1.0（不约束意图）。
    """
    act_pi = str(last_snap.get("primary_intent") or "").strip()
    exp_pi = str(expected.get("primary_intent") or "").strip()
    exp_ints = _expected_intents_unique(expected)
    act_ints = _snapshot_intents_list(last_snap)
    act_set = set(act_ints)

    parts: List[float] = []
    detail: Dict[str, Any] = {
        "expected_primary": exp_pi or None,
        "actual_primary": act_pi or None,
        "expected_intents": exp_ints,
        "actual_intents": act_ints,
    }

    if exp_pi:
        pm = 1.0 if exp_pi == act_pi else 0.0
        parts.append(pm)
        detail["primary_match"] = pm

    if exp_ints:
        hits = sum(1 for e in exp_ints if e in act_set)
        recall = hits / len(exp_ints)
        parts.append(recall)
        detail["intents_subset_recall"] = recall
        detail["intents_hits"] = hits
        detail["intents_expected_n"] = len(exp_ints)

    if not parts:
        detail["mode"] = "unconstrained"
        return 1.0, detail

    detail["mode"] = "constrained"
    return sum(parts) / float(len(parts)), detail


def score_dialogue_layer(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    *,
    llm_bundle: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    last_snap = (turns[-1].get("snapshot") or {}) if turns else {}
    intent_ok, intent_detail = compute_intent_alignment_score(expected, last_snap)

    exp_clar = bool(expected.get("needs_clarification"))
    act_clar = bool(last_snap.get("needs_clarification"))
    ts = list(last_snap.get("task_stack") or [])
    clarify_evidence = exp_clar == act_clar or (exp_clar and ("TASK_CLARIFY" in ts))
    clar_ok_rule = 1.0 if clarify_evidence else 0.0
    clar_applicable = exp_clar or act_clar

    scenario = str(expected.get("scenario_category") or "")
    ctx_expected = list(expected.get("context_preserved") or [])
    replies = [str(t.get("assistant_reply") or "") for t in turns]
    mem = (turns[-1].get("snapshot") or {}).get("memory_state_excerpt") or {}
    stc = " ".join(str(x) for x in (mem.get("short_term_constraints") or []))
    blob = "\n".join(replies) + "\n" + stc

    if scenario == "multi_turn" and ctx_expected:
        hits = sum(1 for phrase in ctx_expected if phrase and str(phrase) in blob)
        ctx_score = hits / len(ctx_expected)
    else:
        ctx_score = None

    sub_ctx = _ok(ctx_score) if ctx_score is not None else _na()
    ctx_part = float(sub_ctx["score"]) if sub_ctx.get("status") == "ok" else 1.0

    reply_final = replies[-1] if replies else ""
    oc = list(expected.get("output_contains") or [])
    ox = list(expected.get("output_excludes") or [])
    kw_ok = 1.0
    if oc:
        hit_kw = sum(1 for k in oc if k and str(k) in reply_final)
        kw_ok = hit_kw / len(oc)
    bad = sum(1 for k in ox if k and str(k) in reply_final)
    kw_pen = 1.0 if bad == 0 else max(0.0, 1.0 - 0.25 * bad)
    kw_blend = 0.5 * kw_ok + 0.5 * kw_pen

    llm_ok = (
        llm_bundle is not None
        and llm_bundle.get("status") == "ok"
        and isinstance(llm_bundle.get("scores"), dict)
    )
    scores = (llm_bundle or {}).get("scores") or {} if llm_ok else {}

    if llm_ok:
        d_tab = float(scores.get("dietary_taboo", 0.0))
        c_qual = (
            float(scores.get("clarification_quality", 1.0))
            if clar_applicable
            else 1.0
        )
        dlg = (
            0.28 * intent_ok
            + 0.27 * d_tab
            + 0.25 * c_qual
            + 0.10 * ctx_part
            + 0.10 * kw_blend
        )
        sub_diet = _ok(d_tab, source="llm")
        sub_clar = _ok(c_qual, source="llm", clarification_applicable=clar_applicable)
    else:
        dlg = (
            0.35 * intent_ok
            + 0.25 * clar_ok_rule
            + 0.15 * ctx_part
            + 0.25 * kw_blend
        )
        sub_diet = _na()
        sub_clar = _ok(clar_ok_rule)

    intent_extras = {
        k: intent_detail[k]
        for k in (
            "expected_primary",
            "actual_primary",
            "primary_match",
            "expected_intents",
            "actual_intents",
            "intents_subset_recall",
            "intents_hits",
            "intents_expected_n",
            "mode",
        )
        if k in intent_detail
    }
    sub_out: Dict[str, Any] = {
        "intent_match": _ok(intent_ok, **intent_extras),
        "dietary_taboo_llm": sub_diet if llm_ok else _na(),
        "clarification_quality_llm": sub_clar if llm_ok else _na(),
        "clarification_alignment_rule": _ok(clar_ok_rule),
        "context_preserved": sub_ctx,
        "output_keywords": _ok(
            0.5 * kw_ok + 0.5 * kw_pen, contains_hits=oc, excludes_violations=bad
        ),
    }
    if not llm_ok and isinstance(llm_bundle, dict) and llm_bundle.get("status") == "error":
        sub_out["llm_judge_error"] = llm_bundle.get("error")

    return {
        "layer": "dialogue",
        "aggregate_score": dlg,
        "submetrics": sub_out,
    }


def _sum_tokens_from_turns(turns: Sequence[Mapping[str, Any]]) -> Optional[int]:
    total = 0
    found = False
    for t in turns:
        snap = t.get("snapshot") or {}
        for m in snap.get("messages_tail") or []:
            rm = m.get("response_metadata") or {}
            if not isinstance(rm, dict):
                continue
            for key in ("token_usage", "usage"):
                u = rm.get(key)
                if isinstance(u, dict):
                    tot = u.get("total_tokens") or u.get("totalTokenCount")
                    if tot is not None:
                        total += int(tot)
                        found = True
    return total if found else None


def score_efficiency_layer(turns: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """仅汇总原始观测值，不产生 aggregate_score，不参与总分。"""
    total_ms = sum(float(t.get("wall_time_ms") or 0.0) for t in turns)
    tok = _sum_tokens_from_turns(turns)
    last = turns[-1].get("snapshot") if turns else {}
    mcp_ev = (last or {}).get("mcp_evidence") if isinstance(last, dict) else {}
    mcp_n = mcp_ev.get("inferred_total") if isinstance(mcp_ev, dict) else None
    mcp_seq = mcp_ev.get("inferred_sequence") if isinstance(mcp_ev, dict) else None

    metrics: Dict[str, Any] = {
        "total_wall_ms": round(total_ms, 3),
        "tokens_total_from_messages": tok,
        "mcp_inferred_total": mcp_n,
        "mcp_inferred_sequence": mcp_seq,
    }
    return {
        "layer": "efficiency",
        "aggregate_score": None,
        "included_in_overall": False,
        "metrics": metrics,
        "submetrics": {
            "note": "效率为观测项，不参与加权总分；原始量见 metrics",
        },
    }


def _name_fuzzy_match(target: str, candidate: str) -> bool:
    t, c = target.strip().lower(), candidate.strip().lower()
    return bool(t and c and (t in c or c in t))


def _overlay_remove_keys(overlay: Any) -> List[str]:
    keys: List[str] = []
    if not isinstance(overlay, list):
        return keys
    for op in overlay:
        if not isinstance(op, dict):
            continue
        if op.get("op") == "remove" or op.get("remove") is not None:
            k = op.get("key") or op.get("name") or op.get("ingredient") or op.get("remove")
            if k is not None and str(k).strip():
                keys.append(str(k).strip())
    return keys


def _gap_row_names(rows: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            out.append(str(row["name"]).strip())
    return out


def score_shopping_list_ops_layer(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    基于末轮 `inventory_state` 校验清单操作（§7.3～7.4）。
    需在 fixture.expected 中配置 `shopping_list_assert`；采集须含完整 `inventory_state`（T-041 快照）。
    """
    spec_raw = expected.get("shopping_list_assert")
    if not isinstance(spec_raw, dict):
        return {
            "layer": "shopping_list_ops",
            "aggregate_score": None,
            "submetrics": {"note": "未配置 shopping_list_assert，本层不参与总分"},
        }

    spec = {k: v for k, v in spec_raw.items() if k != "strict"}
    strict = bool(spec_raw.get("strict"))

    constraint_keys = (
        "overlay_remove_keys_contain",
        "gap_shopping_names_contain",
        "gap_missing_names_contain",
        "gap_cache_present",
        "overlay_ops_min",
    )
    if not any(k in spec for k in constraint_keys):
        return {
            "layer": "shopping_list_ops",
            "aggregate_score": None,
            "submetrics": {"note": "shopping_list_assert 为空约束，本层不参与总分"},
        }

    if not turns:
        return {
            "layer": "shopping_list_ops",
            "aggregate_score": 0.0,
            "hard_fail": strict,
            "submetrics": {"error": "无 turns"},
        }

    snap = turns[-1].get("snapshot") or {}
    inv = snap.get("inventory_state")
    if not isinstance(inv, dict):
        return {
            "layer": "shopping_list_ops",
            "aggregate_score": 0.0,
            "hard_fail": strict,
            "submetrics": {
                "error": "末轮 snapshot 缺少 inventory_state；请使用新版 state_capture 并重跑 E2E",
            },
        }

    overlay = inv.get("shopping_list_overlay") or []
    gap = inv.get("cached_shopping_gap") or {}
    gap_sl_names = _gap_row_names(gap.get("shopping_list"))
    miss_names = _gap_row_names(gap.get("missing_items"))
    merged_gap_names = list({*gap_sl_names, *miss_names})
    remove_keys = _overlay_remove_keys(overlay)

    checks: List[Tuple[str, float]] = []

    want_rm = list(spec.get("overlay_remove_keys_contain") or [])
    for w in want_rm:
        ok = any(_name_fuzzy_match(str(w), k) for k in remove_keys)
        checks.append((f"overlay_remove⊇{w}", 1.0 if ok else 0.0))

    want_gap = list(spec.get("gap_shopping_names_contain") or [])
    for w in want_gap:
        ok = any(_name_fuzzy_match(str(w), n) for n in merged_gap_names + gap_sl_names)
        checks.append((f"gap_name⊇{w}", 1.0 if ok else 0.0))

    want_miss = list(spec.get("gap_missing_names_contain") or [])
    for w in want_miss:
        ok = any(_name_fuzzy_match(str(w), n) for n in miss_names)
        checks.append((f"gap_missing⊇{w}", 1.0 if ok else 0.0))

    if "gap_cache_present" in spec:
        present = bool(gap) and isinstance(gap, dict)
        want = bool(spec["gap_cache_present"])
        checks.append(
            ("gap_cache_present", 1.0 if present == want else 0.0),
        )

    if "overlay_ops_min" in spec:
        try:
            m = int(spec["overlay_ops_min"])
        except (TypeError, ValueError):
            m = 0
        checks.append(("overlay_ops_min", 1.0 if len(overlay) >= m else 0.0))

    if not checks:
        return {
            "layer": "shopping_list_ops",
            "aggregate_score": None,
            "submetrics": {"note": "无可用约束项"},
        }

    agg = sum(s for _, s in checks) / float(len(checks))
    return {
        "layer": "shopping_list_ops",
        "aggregate_score": round(agg, 6),
        "hard_fail": bool(strict and agg < 1.0),
        "submetrics": {
            "checks": [{"name": n, "score": s} for n, s in checks],
            "overlay_remove_keys_observed": remove_keys,
            "gap_shopping_names_observed": gap_sl_names,
            "gap_missing_names_observed": miss_names,
            "overlay_len_observed": len(overlay) if isinstance(overlay, list) else 0,
            "strict": strict,
        },
    }


def overall_score(
    layers: Mapping[str, Mapping[str, Any]],
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    *,
    hard_fail_retrieval: bool = False,
    hard_fail_shopping_list_ops: bool = False,
) -> Tuple[float, Dict[str, Any]]:
    wsum = 0.0
    acc = 0.0
    detail: Dict[str, Any] = {}
    for key, w in weights.items():
        L = layers.get(key) or {}
        s = L.get("aggregate_score")
        if s is None:
            detail[key] = {"weight": w, "used": False, "reason": "layer score N/A"}
            continue
        acc += float(w) * float(s)
        wsum += float(w)
        detail[key] = {"weight": w, "used": True, "layer_score": float(s)}
    if wsum <= 0:
        return 0.0, detail
    raw = acc / wsum
    if hard_fail_retrieval:
        raw = min(raw, 0.35)
    if hard_fail_shopping_list_ops:
        raw = min(raw, 0.35)
    return raw, detail


def score_capture_payload(
    payload: Mapping[str, Any],
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    retrieval_must_hit: bool = True,
    use_llm_judge: bool = True,
) -> Dict[str, Any]:
    fixture = payload.get("fixture") or {}
    expected = fixture.get("expected") or {}
    turns = list(payload.get("turns") or [])

    if payload.get("error"):
        return {
            "case_id": payload.get("case_id"),
            "status": "error",
            "error": payload.get("error"),
            "overall_score": 0.0,
        }

    llm_bundle: Optional[Dict[str, Any]] = None
    if use_llm_judge:
        from eval.scoring_llm import invoke_llm_quality_judge

        detail_for_llm = _latest_recipe_detail(turns)
        llm_bundle = invoke_llm_quality_judge(expected, turns, detail_for_llm)

    r_layer = score_retrieval_layer(expected, turns, retrieval_must_hit=retrieval_must_hit)
    g_layer = score_generation_layer(expected, turns, llm_bundle=llm_bundle)
    d_layer = score_dialogue_layer(expected, turns, llm_bundle=llm_bundle)
    e_layer = score_efficiency_layer(turns)
    sl_layer = score_shopping_list_ops_layer(expected, turns)

    layers = {
        "retrieval": r_layer,
        "generation": g_layer,
        "dialogue": d_layer,
        "shopping_list_ops": sl_layer,
        "efficiency": e_layer,
    }
    w_apply = (
        dict(DEFAULT_WEIGHTS_WITH_SHOPPING_LIST)
        if sl_layer.get("aggregate_score") is not None
        else dict(weights)
    )
    score_layers = {
        "retrieval": r_layer,
        "generation": g_layer,
        "dialogue": d_layer,
    }
    if sl_layer.get("aggregate_score") is not None:
        score_layers["shopping_list_ops"] = sl_layer
    hard_shop = bool(sl_layer.get("hard_fail"))
    ov, wdetail = overall_score(
        score_layers,
        w_apply,
        hard_fail_retrieval=bool(r_layer.get("hard_fail") and retrieval_must_hit),
        hard_fail_shopping_list_ops=hard_shop,
    )

    out: Dict[str, Any] = {
        "case_id": payload.get("case_id"),
        "source_file": payload.get("source_file"),
        "status": "ok",
        "overall_score": round(ov, 6),
        "weights_applied": w_apply,
        "weight_detail": wdetail,
        "layers": layers,
        "hard_fail_retrieval": bool(r_layer.get("hard_fail")),
        "hard_fail_shopping_list_ops": hard_shop,
    }
    if llm_bundle is not None:
        out["llm_judge"] = llm_bundle
    return out


def score_run_directory(
    run_dir: Path,
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    retrieval_must_hit: bool = True,
    use_llm_judge: bool = True,
) -> Dict[str, Any]:
    cap_dir = run_dir / "captures"
    results: List[Dict[str, Any]] = []
    if not cap_dir.is_dir():
        raise FileNotFoundError(f"未找到 captures 目录: {cap_dir}")

    for fp in sorted(cap_dir.glob("*.json")):
        payload = json.loads(fp.read_text(encoding="utf-8"))
        results.append(
            score_capture_payload(
                payload,
                weights=weights,
                retrieval_must_hit=retrieval_must_hit,
                use_llm_judge=use_llm_judge,
            )
        )

    oks = [r["overall_score"] for r in results if r.get("status") == "ok"]
    mean_ov = sum(oks) / len(oks) if oks else 0.0

    # 集级 MRR（§5.1）：对有金标的用例取 MRR 再平均
    mrr_vals: List[float] = []
    for r in results:
        if r.get("status") != "ok":
            continue
        sm = (r.get("layers") or {}).get("retrieval", {}).get("submetrics") or {}
        mrr_m = sm.get("mrr") or {}
        if mrr_m.get("status") == "ok" and mrr_m.get("score") is not None:
            mrr_vals.append(float(mrr_m["score"]))

    return {
        "run_dir": str(run_dir.resolve()),
        "weights": dict(weights),
        "case_count": len(results),
        "mean_overall_score": round(mean_ov, 6),
        "mean_mrr_retrieval": round(sum(mrr_vals) / len(mrr_vals), 6) if mrr_vals else None,
        "cases": results,
    }


def _fmt_layer_score(case: Mapping[str, Any], layer_key: str) -> str:
    L = (case.get("layers") or {}).get(layer_key) or {}
    s = L.get("aggregate_score")
    if s is None:
        return "—"
    try:
        return f"{float(s):.4f}"
    except (TypeError, ValueError):
        return "—"


def render_scores_markdown(report: Mapping[str, Any]) -> str:
    """将 `score_run_directory` 返回的字典渲染为人类可读的 Markdown。"""
    lines: List[str] = [
        "# E2E 评估报告（score_run）",
        "",
        "> 由 `python -m eval.score_run` 生成；机器可读全量见同目录 **`scores.json`**。",
        "",
        "## 汇总",
        "",
        f"- **run 目录**：`{report.get('run_dir', '')}`",
        f"- **用例数**：{report.get('case_count', 0)}",
        f"- **平均分 overall**：**{report.get('mean_overall_score')}**",
    ]
    mmr = report.get("mean_mrr_retrieval")
    if mmr is not None:
        lines.append(f"- **平均检索 MRR**：{mmr}")
    w = report.get("weights") or {}
    sl_any = any(
        (c.get("layers") or {}).get("shopping_list_ops", {}).get("aggregate_score")
        is not None
        for c in (report.get("cases") or [])
    )
    sum_lines = [
        f"- **加权权重**（效率层仅观测，不计分）：检索 {w.get('retrieval', '—')} · 生成 {w.get('generation', '—')} · 对话 {w.get('dialogue', '—')}",
        "- **检索层 aggregate**（单用例）：**0.4×召回 + 0.3×Top1准确率 + 0.3×名次分**；分项见 `scores.json` → `layers.retrieval.submetrics`。",
        "- **清单操作层**：若用例含 `shopping_list_assert` 且可计分，则 **`layers.shopping_list_ops`** 参与总分（权重见该条 **`weights_applied`**）。",
    ]
    if sl_any:
        sum_lines.append(
            "- **说明**：本 run 中至少一条用例启用了 **四分权重**（含 `shopping_list_ops`）；顶层 `weights` 仍为 CLI 默认三分档，请以各条 `cases[].weights_applied` 为准。"
        )
    sum_lines.extend(
        [
            "",
            "## 逐用例得分",
            "",
            "| case_id | 状态 | overall | 检索 | 生成 | 对话 | LLM 评测 |",
            "|---------|------|---------|------|------|------|----------|",
        ]
    )
    lines.extend(sum_lines)
    for c in report.get("cases") or []:
        cid = str(c.get("case_id") or "—")
        st = str(c.get("status") or "—")
        ov = c.get("overall_score")
        ov_s = f"{float(ov):.4f}" if ov is not None and st == "ok" else ("—" if st != "error" else "0.0")
        r = _fmt_layer_score(c, "retrieval")
        g = _fmt_layer_score(c, "generation")
        d = _fmt_layer_score(c, "dialogue")
        lj = c.get("llm_judge") or {}
        if isinstance(lj, dict):
            llm_st = str(lj.get("status") or "—")
            if llm_st == "ok" and isinstance(lj.get("scores"), dict):
                sc = lj["scores"]
                llm_cell = f"ok（H {sc.get('hallucination', '—')} / 忌口 {sc.get('dietary_taboo', '—')} / 澄清 {sc.get('clarification_quality', '—')} / 整体 {sc.get('reply_overall', '—')}）"
            elif llm_st == "error":
                llm_cell = f"error：`{str(lj.get('error', ''))[:80]}`"
            else:
                llm_cell = llm_st
        else:
            llm_cell = "—"
        lines.append(
            f"| {cid} | {st} | {ov_s} | {r} | {g} | {d} | {llm_cell} |"
        )
    lines.extend(
        [
            "",
            "## 效率观测（不计入 overall）",
            "",
            "各用例明细见 **`scores.json`** → `cases[].layers.efficiency.metrics`（`total_wall_ms`、`tokens_total_from_messages`、`mcp_inferred_*`）。",
            "",
            "## 原始采集",
            "",
            "每条用例的轨迹与快照：`captures/<case_id>.json`。",
            "",
        ]
    )
    return "\n".join(lines)
