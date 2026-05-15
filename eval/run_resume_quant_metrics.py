#!/usr/bin/env python3
"""
简历/答辩用「项目 2」量化指标一站式采集（与既有 eval/run_e2e.py 解耦）。

覆盖：
  1) 对话与任务：意图三分类准确率、多轮澄清收敛率；（可选）检索子模块 Recall@K/MRR@K
  2) 记忆与状态：跨会话有效约束命中率、L2 滚动摘要压缩比与关键词保留率
  3) 库存：当前库食材种类数、单位换算表规模、购物清单与黄金集一致率

用法（在项目根目录）::

  python eval/run_resume_quant_metrics.py
  python eval/run_resume_quant_metrics.py --with-llm --with-retrieval --json-out eval/out/resume_quant.json

环境：
  - ``--with-llm``：需配置与线上一致的 LLM（见 config/setting.yaml；通常 DASHSCOPE_API_KEY）
  - ``--with-retrieval``：需 DASHSCOPE_API_KEY + 已建好的 Chroma/BM25（同 eval/run_retrieval_metrics.py）
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from langchain_core.messages import AIMessage, HumanMessage

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 意图三分类（与简历表述「检索 / 库存 / 闲聊」对齐）────────────────────────
_BUCKET_RETRIEVAL: Set[str] = {"recipe_search", "recipe_adopt", "user_clarify"}
_BUCKET_INVENTORY: Set[str] = {
    "inventory_check",
    "inventory_add",
    "inventory_commit",
    "shopping_list",
}
_BUCKET_CHAT: Set[str] = {
    "general_chat",
    "help",
    "out_of_scope",
    "dietary_advice",
    "profile_sync",
}


def _primary_bucket(primary: str) -> str:
    if primary in _BUCKET_RETRIEVAL:
        return "retrieval"
    if primary in _BUCKET_INVENTORY:
        return "inventory"
    if primary in _BUCKET_CHAT:
        return "chat"
    return "other"


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _messages_total_chars(msgs: Sequence[Any]) -> int:
    from src.agent.nodes.conversation_summary import ConversationSummaryManager

    m = ConversationSummaryManager()
    return len(m._format_messages_for_compression(list(msgs)))


def _norm_shopping_rows(rows: List[Dict[str, Any]]) -> List[Tuple[str, float, str]]:
    out: List[Tuple[str, float, str]] = []
    for r in rows or []:
        name = str(r.get("name") or "").strip()
        if not name:
            continue
        try:
            amt = float(r.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        unit = str(r.get("unit") or "").strip()
        out.append((name, round(amt, 3), unit))
    out.sort(key=lambda x: x[0])
    return out


def _shopping_match(
    got: List[Dict[str, Any]],
    exp: List[Dict[str, Any]],
    *,
    amount_tol: float = 0.51,
) -> bool:
    g = _norm_shopping_rows(got)
    e = _norm_shopping_rows(exp)
    if len(g) != len(e):
        return False
    for (n1, a1, u1), (n2, a2, u2) in zip(g, e):
        if n1 != n2 or u1 != u2:
            return False
        if abs(a1 - a2) > amount_tol:
            return False
    return True


def _clarify_like(details: Mapping[str, Any]) -> bool:
    tasks = list(details.get("task_stack") or [])
    if "TASK_CLARIFY" in tasks:
        return True
    if details.get("needs_clarification"):
        return True
    ms = details.get("missing_slots") or []
    return bool(ms)


def _import_run_benchmark():
    path = ROOT / "eval" / "run_retrieval_metrics.py"
    spec = importlib.util.spec_from_file_location("_retrieval_metrics_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_benchmark


def _bm25_recipe_stats(bm25_path: Path) -> Dict[str, Any]:
    if not bm25_path.is_file():
        return {"fts_rows": 0, "distinct_recipe_ids": 0, "error": "bm25 db missing"}
    conn = sqlite3.connect(str(bm25_path))
    cur = conn.cursor()
    fts = 0
    dr = 0
    try:
        cur.execute("SELECT COUNT(*) FROM recipe_fts")
        fts = int(cur.fetchone()[0])
    except sqlite3.Error as e:
        return {"fts_rows": 0, "distinct_recipe_ids": 0, "error": str(e)}
    try:
        cur.execute("SELECT COUNT(DISTINCT recipe_id) FROM recipe_fts")
        dr = int(cur.fetchone()[0])
    except sqlite3.Error:
        dr = 0
    conn.close()
    return {"fts_rows": fts, "distinct_recipe_ids": dr}


def _make_state_base(
    *,
    messages: List[Any],
    conversation_summary: str = "",
    active_user_id: str = "resume_quant_eval",
    memory_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from tests.conftest import make_minimal_agent_state

    s = make_minimal_agent_state()
    s["messages"] = list(messages)
    s["active_user_id"] = active_user_id
    s["conversation_summary"] = conversation_summary
    if memory_state is not None:
        s["memory_state"] = {**(s.get("memory_state") or {}), **memory_state}
    return s


def run_deterministic_block(doc: Dict[str, Any]) -> Dict[str, Any]:
    """不调用 LLM / Embedding 的指标。"""
    from src.agent.memory.effective_constraint import build_effective_constraint
    from src.agent.nodes.logistics import LogisticsManager
    from src.libs.base.inventory import InventoryManager
    from src.libs.base.settings import Settings
    from src.libs.utils.ingredient_normalize import _load_alias_map
    from src.libs.utils.unit_converter import CONVERSION

    settings = Settings(str(ROOT / "config" / "setting.yaml"))
    inv_m = InventoryManager(household_id=settings.get_scope_id())
    inv_snapshot = inv_m.get_inventory_snapshot_i()
    n_inv_kinds = len(inv_snapshot)

    alias_n = len(_load_alias_map())
    unit_n = len(CONVERSION)

    bm25_path = ROOT / "data" / "db" / "bm25_index.db"
    bm25_stats = _bm25_recipe_stats(bm25_path)

    lm = LogisticsManager(household_id=settings.get_scope_id())
    shop_cases = doc.get("shopping_list_gold") or []
    shop_ok = 0
    shop_rows: List[Dict[str, Any]] = []
    for c in shop_cases:
        cid = c.get("id")
        req = c.get("required") or []
        inv = c.get("inventory") or {}
        exp = c.get("expected_shopping") or []
        got = lm.calculate_shopping_gap(req, inv).get("shopping_list") or []
        ok = _shopping_match(got, exp)
        if ok:
            shop_ok += 1
        shop_rows.append({"id": cid, "match": ok, "expected": exp, "got": got})

    shop_acc = shop_ok / max(len(shop_cases), 1)

    cs_cases = doc.get("cross_session_constraint_gold") or []
    cs_ok = 0
    cs_rows: List[Dict[str, Any]] = []
    for c in cs_cases:
        cid = c.get("id")
        profile = dict(c.get("profile") or {})
        mem = dict(c.get("memory_state") or {})
        summary = (mem.get("conversation_summary") or "").strip()
        state = _make_state_base(
            messages=[HumanMessage(content="推荐一道家常菜")],
            conversation_summary=summary,
            active_user_id=str(c.get("active_user_id") or "resume_eval_scope"),
            memory_state=mem,
        )
        ec = build_effective_constraint(state, profile=profile)
        hx = list(ec.get("hard_exclusions") or [])
        tc = list(ec.get("temporal_conditions") or [])
        hx_join = "、".join(hx)
        tc_join = "；".join(tc)

        hard_ok = True
        for kw in c.get("must_hit_hard_exclusions") or []:
            if str(kw).strip() and str(kw).strip() not in hx_join:
                hard_ok = False
                break

        temp_ok = True
        any_kw = c.get("must_hit_temporal_any")
        if isinstance(any_kw, list) and any_kw:
            temp_ok = any(str(k).strip() and str(k).strip() in tc_join for k in any_kw)

        row_ok = hard_ok and temp_ok
        if row_ok:
            cs_ok += 1
        cs_rows.append(
            {
                "id": cid,
                "match": row_ok,
                "hard_exclusions": hx,
                "temporal_conditions": tc,
            }
        )

    cs_rate = cs_ok / max(len(cs_cases), 1)

    return {
        "inventory_and_units": {
            "inventory_distinct_ingredient_kinds_in_scope": n_inv_kinds,
            "ingredient_alias_table_entries": alias_n,
            "unit_converter_supported_unit_strings": unit_n,
            "bm25_index": bm25_stats,
            "note": "inventory 种类数为当前 household scope 下快照；菜谱侧覆盖可参考 bm25 distinct_recipe_ids。",
        },
        "shopping_list_vs_gold": {
            "num_cases": len(shop_cases),
            "matches": shop_ok,
            "accuracy": round(shop_acc * 100.0, 2),
            "per_case": shop_rows,
        },
        "cross_session_effective_constraint": {
            "num_cases": len(cs_cases),
            "hits": cs_ok,
            "hit_rate_percent": round(cs_rate * 100.0, 2),
            "per_case": cs_rows,
        },
    }


async def run_l2_block(doc: Dict[str, Any]) -> Dict[str, Any]:
    from src.agent.nodes.conversation_summary import ConversationSummaryManager

    spec = doc.get("l2_summary_must_preserve") or {}
    seed = spec.get("seed_turns") or []
    extra_pairs = int(spec.get("extra_chitchat_pairs") or 0)
    must_kw = [str(x) for x in (spec.get("must_preserve_substrings") or []) if str(x).strip()]

    msgs: List[Any] = []
    for t in seed:
        role = str(t.get("role") or "").lower()
        content = str(t.get("content") or "")
        if role == "human":
            msgs.append(HumanMessage(content=content))
        else:
            msgs.append(AIMessage(content=content))
    for i in range(extra_pairs):
        msgs.append(HumanMessage(content=f"闲聊{i}：今天有点累。"))
        msgs.append(AIMessage(content=f"助手{i}：注意休息。"))

    manager = ConversationSummaryManager()
    if not manager.needs_compression(msgs):
        return {
            "skipped": True,
            "reason": f"消息条数 {len(msgs)} 未超过 compress_trigger={manager.compress_trigger}",
        }

    raw_chars = _messages_total_chars(msgs)
    trimmed, summary = await manager.maybe_compress(msgs, existing_summary="")
    kept_chars = _messages_total_chars(trimmed)
    summary_chars = len(summary or "")
    after_chars = kept_chars + summary_chars
    ratio_pct = (after_chars / raw_chars * 100.0) if raw_chars else 0.0

    s_low = (summary or "").lower()
    kept_blob = manager._format_messages_for_compression(list(trimmed)).lower()
    merged_low = (s_low + "\n" + kept_blob).lower()

    kw_hits = []
    for kw in must_kw:
        kw_hits.append({"keyword": kw, "in_summary": kw in s_low, "in_summary_or_window": kw in merged_low})

    retained = sum(1 for x in kw_hits if x["in_summary_or_window"])
    retain_rate = retained / max(len(must_kw), 1)
    retained_in_summary = sum(1 for x in kw_hits if x["in_summary"])
    retain_summary_only = retained_in_summary / max(len(must_kw), 1)

    return {
        "skipped": False,
        "num_messages_before": len(msgs),
        "num_messages_after": len(trimmed),
        "summary_char_len": summary_chars,
        "raw_dialog_chars_before_compress": raw_chars,
        "after_compress_context_chars_summary_plus_window": after_chars,
        "rolling_summary_compression_ratio_percent_of_raw": round(ratio_pct, 2),
        "must_preserve_keyword_hits": kw_hits,
        "keyword_retention_rate_anywhere_in_context_percent": round(retain_rate * 100.0, 2),
        "keyword_retention_rate_in_summary_only_percent": round(retain_summary_only * 100.0, 2),
        "summary_text_preview": (summary or "")[:400],
    }


def run_llm_intent_block(doc: Dict[str, Any]) -> Dict[str, Any]:
    from src.agent.nodes.router import IntentClassifier

    clf = IntentClassifier()
    gold = doc.get("intent_bucket_gold") or []
    ok = 0
    rows: List[Dict[str, Any]] = []
    for c in gold:
        cid = c.get("id")
        utt = str(c.get("utterance") or "")
        st = _make_state_base(messages=[HumanMessage(content=utt)])
        details = clf.get_intent_details(st)
        primary = str(details.get("primary_intent") or details.get("intent") or "")
        bucket = _primary_bucket(primary)
        exp_any = c.get("expect_bucket_any")
        if isinstance(exp_any, list) and exp_any:
            match = bucket in set(str(x) for x in exp_any)
        else:
            exp = str(c.get("expect_bucket") or "")
            match = bucket == exp
        if match:
            ok += 1
        rows.append(
            {
                "id": cid,
                "utterance": utt,
                "primary_intent": primary,
                "bucket": bucket,
                "expect_bucket": c.get("expect_bucket"),
                "expect_bucket_any": exp_any,
                "match": match,
                "confidence": details.get("confidence"),
                "task_stack": details.get("task_stack"),
            }
        )

    acc = ok / max(len(gold), 1)
    return {
        "num_cases": len(gold),
        "bucket_correct": ok,
        "intent_bucket_accuracy_percent": round(acc * 100.0, 2),
        "per_case": rows,
    }


def run_llm_clarification_block(doc: Dict[str, Any]) -> Dict[str, Any]:
    from src.agent.nodes.router import IntentClassifier

    clf = IntentClassifier()
    flows = doc.get("clarification_flows") or []
    ok_flows = 0
    flow_rows: List[Dict[str, Any]] = []

    for flow in flows:
        fid = flow.get("id")
        turns = flow.get("turns") or []
        msgs: List[Any] = []
        turn_ok: List[bool] = []
        for ti, t in enumerate(turns):
            if "assistant" in t and t.get("assistant"):
                msgs.append(AIMessage(content=str(t.get("assistant"))))
            user = str(t.get("user") or "")
            msgs.append(HumanMessage(content=user))
            st = _make_state_base(messages=list(msgs))
            details = clf.get_intent_details(st)
            primary = str(details.get("primary_intent") or details.get("intent") or "")
            clarify = _clarify_like(details)

            exp_c = bool(t.get("expect_clarify_path"))
            clarify_match = clarify == exp_c

            exp_p = t.get("expect_primary_one_of")
            if isinstance(exp_p, list) and exp_p:
                primary_ok = primary in set(str(x) for x in exp_p)
            else:
                primary_ok = True

            step_ok = clarify_match and primary_ok
            turn_ok.append(step_ok)
            if not step_ok:
                flow_rows.append(
                    {
                        "flow_id": fid,
                        "turn_index": ti,
                        "user": user,
                        "primary_intent": primary,
                        "clarify_like": clarify,
                        "expect_clarify_path": exp_c,
                        "clarify_match": clarify_match,
                        "primary_ok": primary_ok,
                        "task_stack": details.get("task_stack"),
                        "missing_slots": details.get("missing_slots"),
                    }
                )

        if turn_ok and all(turn_ok):
            ok_flows += 1

    conv_rate = ok_flows / max(len(flows), 1)
    return {
        "num_flows": len(flows),
        "converged_flows": ok_flows,
        "multi_turn_clarification_convergence_rate_percent": round(conv_rate * 100.0, 2),
        "failed_steps_detail": flow_rows,
    }


def _composite_e2e_score(
    *,
    intent_acc: Optional[float],
    clarify_rate: Optional[float],
    retrieval_mrr_hybrid: Optional[float],
) -> Optional[float]:
    parts: List[float] = []
    weights: List[float] = []
    if intent_acc is not None:
        parts.append(intent_acc)
        weights.append(0.35)
    if clarify_rate is not None:
        parts.append(clarify_rate)
        weights.append(0.25)
    if retrieval_mrr_hybrid is not None:
        parts.append(retrieval_mrr_hybrid * 100.0)
        weights.append(0.40)
    if not parts:
        return None
    wsum = sum(weights)
    return round(sum(p * w for p, w in zip(parts, weights)) / wsum, 2)


def print_zh_resume_snippets(report: Dict[str, Any]) -> None:
    print("\n========== 简历可直接改写的中文短句（请替换为你的实测数值）==========\n")

    d = report.get("deterministic") or {}
    invu = d.get("inventory_and_units") or {}
    shop = d.get("shopping_list_vs_gold") or {}
    cs = d.get("cross_session_effective_constraint") or {}

    print(
        f"【库存与单位】当前库存食材种类数（本 household 快照）{invu.get('inventory_distinct_ingredient_kinds_in_scope', 0)}；"
        f"单位换算表覆盖 {invu.get('unit_converter_supported_unit_strings', 0)} 种单位写法；"
        f"购物清单与黄金集一致率 {shop.get('accuracy', 0)}%（n={shop.get('num_cases', 0)}）。\n"
        f"【记忆】跨会话有效约束（过敏/医嘱/L3）命中率 {cs.get('hit_rate_percent', 0)}%（n={cs.get('num_cases', 0)}）。"
    )

    llm = report.get("llm") or {}
    if llm.get("intent_bucket"):
        ib = llm["intent_bucket"]
        print(
            f"\n【意图路由】检索/库存/闲聊三分类准确率 {ib.get('intent_bucket_accuracy_percent')}% "
            f"（n={ib.get('num_cases')}，基于黄金话术集）。"
        )
    if llm.get("clarification"):
        cf = llm["clarification"]
        print(
            f"【多轮澄清】模糊意图经追问后收敛成功率 {cf.get('multi_turn_clarification_convergence_rate_percent')}% "
            f"（n={cf.get('num_flows')} 组对话）。"
        )
    if llm.get("l2_summary"):
        l2 = llm["l2_summary"]
        if not l2.get("skipped"):
            print(
                f"\n【L2 摘要】上下文超限后，摘要+保留窗口相对原文长度比 {l2.get('rolling_summary_compression_ratio_percent_of_raw')}% "
                f"（数值越低表示压得越狠；关键词仅在摘要中保留率 {l2.get('keyword_retention_rate_in_summary_only_percent')}% ，"
                f"在摘要或保留窗口中 {l2.get('keyword_retention_rate_anywhere_in_context_percent')}%）。"
            )

    rt = report.get("retrieval") or {}
    rq = rt.get("retrieval_quality") or {}
    if rq.get("num_cases"):
        k = (rq.get("k_values") or [5])[0]
        print(
            f"\n【检索子模块】黄金集 n={rq.get('num_cases')}："
            f"混合 Recall@{k} {rq.get(f'recall_at_{k}_mean_hybrid', 0):.2%}，"
            f"MRR@{k} {rq.get(f'mrr_mean_at_{k}_hybrid', 0):.3f}（与 eval/run_retrieval_metrics 口径一致）。"
        )

    comp = report.get("composite_end_to_end_score_0_100")
    if comp is not None:
        print(f"\n【综合】端到端加权分（意图 0.35 + 澄清 0.25 + 检索 MRR×100 权重 0.40）：{comp} / 100（仅作内部对比，非标准考试分）。")

    print("\n================================================================\n")


async def _async_main(args: argparse.Namespace) -> Dict[str, Any]:
    gold_path = Path(args.gold)
    if not gold_path.is_absolute():
        gold_path = ROOT / gold_path
    doc = _load_json(gold_path)

    report: Dict[str, Any] = {
        "gold_file": str(gold_path),
        "deterministic": run_deterministic_block(doc),
    }

    llm_block: Dict[str, Any] = {}
    if args.with_llm:
        try:
            llm_block["intent_bucket"] = run_llm_intent_block(doc)
            llm_block["clarification"] = run_llm_clarification_block(doc)
            llm_block["l2_summary"] = await run_l2_block(doc)
        except Exception as e:
            llm_block["error"] = str(e)
            import traceback

            llm_block["traceback"] = traceback.format_exc()
    else:
        llm_block["skipped"] = True
        llm_block["hint"] = "追加 --with-llm 以评测意图、澄清与 L2 摘要（将产生 LLM API 调用）。"
    report["llm"] = llm_block

    rt_block: Dict[str, Any] = {}
    if args.with_retrieval:
        try:
            run_benchmark = _import_run_benchmark()

            rgold = Path(args.retrieval_gold)
            if not rgold.is_absolute():
                rgold = ROOT / rgold
            ns = Namespace(
                gold=str(rgold),
                k=args.retrieval_k,
                latency_runs=max(3, args.latency_runs),
                top_k_latency=args.top_k_latency,
                chroma_path=args.chroma_path,
                bm25_path=args.bm25_path,
                json_out=None,
                quiet=True,
            )
            rt_block = run_benchmark(ns)
        except Exception as e:
            rt_block = {"error": str(e)}
    else:
        rt_block["skipped"] = True
        rt_block["hint"] = "追加 --with-retrieval 以跑混合检索 Recall/MRR（需索引与 DASHSCOPE_API_KEY）。"
    report["retrieval"] = rt_block

    intent_acc = None
    clarify_rate = None
    if isinstance(llm_block.get("intent_bucket"), dict):
        intent_acc = llm_block["intent_bucket"].get("intent_bucket_accuracy_percent")
    if isinstance(llm_block.get("clarification"), dict):
        clarify_rate = llm_block["clarification"].get("multi_turn_clarification_convergence_rate_percent")

    retrieval_mrr = None
    rq = rt_block.get("retrieval_quality") if isinstance(rt_block, dict) else None
    if isinstance(rq, dict):
        ks = rq.get("k_values") or [5]
        k0 = int(ks[0]) if ks else 5
        retrieval_mrr = rq.get(f"mrr_mean_at_{k0}_hybrid")

    report["composite_end_to_end_score_0_100"] = _composite_e2e_score(
        intent_acc=intent_acc,
        clarify_rate=clarify_rate,
        retrieval_mrr_hybrid=retrieval_mrr,
    )

    return report


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="简历量化指标（项目2）一站式采集")
    ap.add_argument("--gold", default="eval/data/resume_quant_gold.json", help="本脚本配套黄金集")
    ap.add_argument("--with-llm", action="store_true", help="评测意图/澄清/L2（调用 LLM）")
    ap.add_argument("--with-retrieval", action="store_true", help="跑检索黄金集（调用 Embedding API）")
    ap.add_argument("--retrieval-gold", default="eval/data/retrieval_gold.json")
    ap.add_argument("--retrieval-k", default="5", help="传给 run_retrieval_metrics 的 K 列表")
    ap.add_argument("--latency-runs", type=int, default=8, help="检索延迟重复次数（合并跑时默认略少）")
    ap.add_argument("--top-k-latency", type=int, default=5)
    ap.add_argument("--chroma-path", default=None)
    ap.add_argument("--bm25-path", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    report = asyncio.run(_async_main(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print_zh_resume_snippets(report)

    if args.json_out:
        outp = Path(args.json_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入: {outp.resolve()}")


if __name__ == "__main__":
    main()
