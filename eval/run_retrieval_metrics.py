#!/usr/bin/env python3
"""
离线检索量化指标：全量与 **分场景（scenario）** Recall@K / MRR@K 均值、混合 vs 纯向量对比、索引规模、延迟、增量入库。

用法（在项目根目录）:
  set PYTHONPATH=.   # Linux/macOS: export PYTHONPATH=.
  python eval/run_retrieval_metrics.py
  python eval/run_retrieval_metrics.py --gold eval/data/retrieval_gold.json --latency-runs 30 --json-out eval/out/retrieval_metrics.json
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from collections import defaultdict
import sqlite3
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.memory.effective_constraint import filter_recipes_by_hard_exclusions  # noqa: E402
from src.libs.adapters.embed.embed_factory import EmbedFactory  # noqa: E402
from src.libs.base.bm25_indexer import BM25Indexer  # noqa: E402
from src.libs.base.chroma_store import ChromaStore  # noqa: E402
from src.libs.base.settings import Settings  # noqa: E402
from src.mcp.tool import SearchRecipesService  # noqa: E402
from src.rag.rag_core import (  # noqa: E402
    HybridSearchEngine,
    KeywordSearchEngine,
    SearchResult,
    SemanticSearchEngine,
)

# 报告与简历中的场景展示顺序（黄金集 scenario 字段）
_SCENARIO_ORDER = (
    "exact",
    "semantic_fuzzy",
    "keyword_exact",
    "filter_constraint",
    "mixed",
    "unspecified",
)

_SCENARIO_LABEL_ZH = {
    "exact": "精确查询",
    "semantic_fuzzy": "语义模糊",
    "keyword_exact": "关键词精确",
    "filter_constraint": "过滤约束",
    "mixed": "混合多目标",
    "unspecified": "未标注场景",
}


def _aggregate_rows_by_scenario(rows: List[Dict[str, Any]], k_list: List[int]) -> Dict[str, Any]:
    """按 scenario 分组，对每条已写入 per_query 的 recall/mrr 做算术均值。"""
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        sk = row.get("scenario")
        if not sk or not str(sk).strip():
            sk = "unspecified"
        buckets[str(sk).strip()].append(row)

    out: Dict[str, Any] = {}
    for sk in sorted(buckets.keys(), key=lambda x: (_SCENARIO_ORDER.index(x) if x in _SCENARIO_ORDER else 99, x)):
        sub = buckets[sk]
        n = len(sub)
        block: Dict[str, Any] = {"num_cases": n}
        if n == 0:
            out[sk] = block
            continue
        for k in k_list:
            rv = [float(r[f"recall_at_{k}_vector"]) for r in sub]
            rh = [float(r[f"recall_at_{k}_hybrid"]) for r in sub]
            mv = [float(r[f"mrr_at_{k}_vector"]) for r in sub]
            mh = [float(r[f"mrr_at_{k}_hybrid"]) for r in sub]
            block[f"recall_at_{k}_mean_vector"] = round(statistics.mean(rv), 4)
            block[f"recall_at_{k}_mean_hybrid"] = round(statistics.mean(rh), 4)
            block[f"mrr_mean_at_{k}_vector"] = round(statistics.mean(mv), 4)
            block[f"mrr_mean_at_{k}_hybrid"] = round(statistics.mean(mh), 4)
            v_hit = sum(1 for x in mv if x > 0) / n
            h_hit = sum(1 for x in mh if x > 0) / n
            block[f"hit_at_{k}_rate_vector"] = round(v_hit, 4)
            block[f"hit_at_{k}_rate_hybrid"] = round(h_hit, 4)
            block[f"hit_at_{k}_hybrid_minus_vector_pp"] = round((h_hit - v_hit) * 100.0, 2)
        out[sk] = block
    return out


def _bench_log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg, flush=True)


def _norm_path(p: str) -> str:
    return str(p).replace("\\", "/").lower().strip()


def _path_matches_gold_candidate(nc: str, ng: str) -> bool:
    """
    判断规范化后的候选路径 nc 是否视为命中 gold 路径 ng。
    禁止仅用子串 ng in nc（否则「凉拌木耳」会误命中 gold「木耳」）。
    规则：全串相等；或 nc 以「/」+ ng 为后缀；或与 ng 的 path 分量后缀完全一致。
    """
    if not ng:
        return False
    if nc == ng:
        return True
    if nc.endswith(ng) and (len(nc) == len(ng) or nc[len(nc) - len(ng) - 1] == "/"):
        return True
    nc_parts = [p for p in nc.split("/") if p]
    ng_parts = [p for p in ng.split("/") if p]
    if not ng_parts or len(ng_parts) > len(nc_parts):
        return False
    return nc_parts[-len(ng_parts) :] == ng_parts


def _resolve_gold_path(root: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p.resolve()
    return (root / p).resolve()


def result_matches_gold(meta: Optional[Dict[str, Any]], gold_paths: Sequence[str], root: Path) -> bool:
    if not meta:
        return False
    candidates: List[str] = []
    for k in ("file_path", "source_document_id"):
        v = meta.get(k)
        if v:
            candidates.append(str(v))
    if not candidates:
        return False
    gold_resolved = [_resolve_gold_path(root, g) for g in gold_paths]
    for c in candidates:
        try:
            cp = Path(c).resolve()
        except OSError:
            cp = None
        nc = _norm_path(c)
        for gr in gold_resolved:
            try:
                if cp is not None and cp == gr.resolve():
                    return True
            except OSError:
                pass
            ng = _norm_path(str(gr))
            if ng and _path_matches_gold_candidate(nc, ng):
                return True
    return False


def recall_mrr_for_results(
    results: List[SearchResult],
    gold_paths: Sequence[str],
    root: Path,
    k: int,
) -> Tuple[float, float]:
    """
    多标签召回：命中数 / |gold|；MRR 取「第一个命中任意 gold 的 rank」。
    """
    top = results[:k]
    matched_gold = set()
    for g in gold_paths:
        gr = _resolve_gold_path(root, g)
        ng = _norm_path(str(gr))
        for r in top:
            if result_matches_gold(r.metadata, [g], root):
                matched_gold.add(ng)
                break
    recall = len(matched_gold) / max(len(gold_paths), 1)

    mrr = 0.0
    for i, r in enumerate(top):
        if result_matches_gold(r.metadata, gold_paths, root):
            mrr = 1.0 / float(i + 1)
            break
    return recall, mrr


def _silent_hybrid_search(engine: HybridSearchEngine, query: str, top_k: int) -> List[SearchResult]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return engine.search(query, top_k)


def _case_has_hard_exclusions(case: Dict[str, Any]) -> bool:
    ec = case.get("effective_constraint")
    if not isinstance(ec, dict):
        return False
    hx = ec.get("hard_exclusions")
    if not isinstance(hx, list):
        return False
    return any(str(x).strip() for x in hx)


def apply_hard_exclusions_to_search_results(
    results: List[SearchResult],
    effective_constraint: Optional[Dict[str, Any]],
) -> List[SearchResult]:
    """
    与 MCP `search_recipes` 一致：对检索候选按 §5.4 hard_exclusions 过滤后再参与指标计算。
    """
    if not effective_constraint or not isinstance(effective_constraint, dict):
        return results
    hx = effective_constraint.get("hard_exclusions") or []
    if not isinstance(hx, list) or not any(str(x).strip() for x in hx):
        return results
    recipes: List[Dict[str, Any]] = []
    for r in results:
        md = r.metadata or {}
        recipes.append(
            {
                "id": r.id,
                "title": SearchRecipesService.extract_title(r.content or "", md),
                "content": r.content or "",
                "source": md.get("source_document_id") or "",
            }
        )
    kept = filter_recipes_by_hard_exclusions(recipes, hx)
    kept_ids = {x["id"] for x in kept}
    return [r for r in results if r.id in kept_ids]


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def chroma_scale(collection) -> Dict[str, Any]:
    n = collection.count()
    doc_paths: set = set()
    try:
        raw = collection.get(include=["metadatas"], limit=max(n, 1))
        metas = raw.get("metadatas") or []
        for m in metas:
            if not m:
                continue
            fp = m.get("file_path") or m.get("source_document_id")
            if fp:
                doc_paths.add(str(fp))
    except Exception as e:
        return {"chunk_count": n, "unique_file_paths": None, "meta_scan_error": str(e)}
    return {"chunk_count": n, "unique_file_paths": len(doc_paths)}


def bm25_scale(db_path: Path) -> Dict[str, Any]:
    if not db_path.exists():
        return {"fts_rows": 0, "db_file_bytes": 0}
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    fts_rows = 0
    try:
        cur.execute("SELECT COUNT(*) FROM recipe_fts")
        fts_rows = int(cur.fetchone()[0])
    except sqlite3.Error:
        pass
    conn.close()
    return {"fts_rows": fts_rows, "db_file_bytes": db_path.stat().st_size}


def cleanup_eval_bm25_row(db_path: Path, recipe_id: str) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("DELETE FROM recipe_fts WHERE recipe_id = ?", (recipe_id,))
    cur.execute("DELETE FROM bm25_stats WHERE recipe_id = ?", (recipe_id,))
    try:
        cur.execute("UPDATE global_params SET total_docs = (SELECT COUNT(*) FROM recipe_fts) WHERE id = 1")
    except sqlite3.Error:
        pass
    conn.commit()
    conn.close()


def run_benchmark(args: argparse.Namespace) -> Dict[str, Any]:
    quiet = bool(getattr(args, "quiet", False))
    root = ROOT
    settings = Settings(str(root / "config" / "setting.yaml"))
    gold_path = Path(args.gold)
    if not gold_path.is_absolute():
        gold_path = root / gold_path
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_doc = json.load(f)
    cases: List[Dict[str, Any]] = gold_doc.get("cases") or []
    default_queries = ["蛋炒饭 家常做法", "麻婆豆腐 豆瓣酱 花椒"]
    latency_queries = [str(c.get("query") or "") for c in cases if c.get("query")] or default_queries

    chroma_dir = Path(args.chroma_path) if args.chroma_path else root / "data" / "db"
    bm25_path = Path(args.bm25_path) if args.bm25_path else root / "data" / "db" / "bm25_index.db"

    if not chroma_dir.exists():
        raise SystemExit(f"Chroma 持久化目录不存在: {chroma_dir}（请先完成菜谱索引摄取）")
    if not bm25_path.exists():
        raise SystemExit(f"BM25 库不存在: {bm25_path}（请先完成索引）")

    embed_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not embed_key.strip():
        raise SystemExit("未设置环境变量 DASHSCOPE_API_KEY，无法调用向量检索（与线上一致）。")

    _bench_log("[bench] 检查通过，开始加载 Embedding / Chroma / BM25（首次可能较慢）…", quiet)
    embedding_fn = EmbedFactory.get_embed(settings)
    vector_store = ChromaStore(
        db_path=str(chroma_dir),
        embedding_function=embedding_fn,
        collection_name="recipes",
    )
    bm25_indexer = BM25Indexer(db_path=str(bm25_path))

    semantic_engine = SemanticSearchEngine(vector_store=vector_store, embed_model=embedding_fn)
    keyword_engine = KeywordSearchEngine(bm25_indexer)
    hybrid_engine = HybridSearchEngine(
        semantic_engine=semantic_engine,
        keyword_engine=keyword_engine,
    )
    _bench_log("[bench] 检索引擎就绪。", quiet)

    k_list = [int(x) for x in args.k.split(",") if x.strip()]
    if not k_list:
        raise SystemExit("无效的 --k，至少提供一个整数，如 5 或 5,10")
    max_k = max(k_list)
    # 过滤会裁掉部分候选，池子略大以便过滤后仍有足够深度算 Recall@K / MRR@K
    any_filter = any(_case_has_hard_exclusions(c) for c in cases)
    pool_k = max(max_k, 28 if any_filter else 15)

    for probe_q in ("豆腐", "花椒 豆瓣酱"):
        nhits = len(bm25_indexer.search(probe_q, 5))
        _bench_log(
            f"[bench] BM25 探针 {probe_q!r} 命中 {nhits} 条；全 0 时混合检索无稀疏信号，指标会与纯向量一致。",
            quiet,
        )

    per_case: List[Dict[str, Any]] = []
    vec_recalls: Dict[int, List[float]] = {k: [] for k in k_list}
    hyb_recalls: Dict[int, List[float]] = {k: [] for k in k_list}
    vec_mrrs: Dict[int, List[float]] = {k: [] for k in k_list}
    hyb_mrrs: Dict[int, List[float]] = {k: [] for k in k_list}
    vec_hits: Dict[int, List[int]] = {k: [] for k in k_list}
    hyb_hits: Dict[int, List[int]] = {k: [] for k in k_list}

    valid_cases = [
        c
        for c in cases
        if (c.get("query") or "")
        and (c.get("relevant_paths") or c.get("relevant_source_document_ids") or [])
    ]
    n_valid = len(valid_cases)
    _bench_log(
        f"[bench] 检索质量：共 {n_valid} 条有效黄金样本；每条会做「纯向量 + 混合」检索（均会请求向量化 API），"
        f"默认约 {n_valid * 2} 次 query 级调用，请耐心等待。",
        quiet,
    )

    for idx, case in enumerate(valid_cases, start=1):
        q = str(case.get("query") or "")
        rel = case.get("relevant_paths") or case.get("relevant_source_document_ids") or []
        ec = case.get("effective_constraint") if isinstance(case.get("effective_constraint"), dict) else None
        scenario = case.get("scenario")
        _bench_log(f"[bench]  ({idx}/{n_valid}) 评测 query …", quiet)

        vec_raw = semantic_engine.search(q, pool_k)
        hyb_raw = _silent_hybrid_search(hybrid_engine, q, pool_k)
        vec_results = apply_hard_exclusions_to_search_results(vec_raw, ec)
        hyb_results = apply_hard_exclusions_to_search_results(hyb_raw, ec)

        row: Dict[str, Any] = {"query": q, "relevant_paths": rel}
        if scenario:
            row["scenario"] = scenario
        if ec:
            row["effective_constraint"] = ec
        for k in k_list:
            vr, vm = recall_mrr_for_results(vec_results, rel, root, k)
            hr, hm = recall_mrr_for_results(hyb_results, rel, root, k)
            vec_recalls[k].append(vr)
            hyb_recalls[k].append(hr)
            vec_mrrs[k].append(vm)
            hyb_mrrs[k].append(hm)
            v_hit = 1 if vm > 0 else 0
            h_hit = 1 if hm > 0 else 0
            vec_hits[k].append(v_hit)
            hyb_hits[k].append(h_hit)
            row[f"recall_at_{k}_vector"] = round(vr, 4)
            row[f"recall_at_{k}_hybrid"] = round(hr, 4)
            row[f"mrr_at_{k}_vector"] = round(vm, 4)
            row[f"mrr_at_{k}_hybrid"] = round(hm, 4)
        per_case.append(row)

    n_cases = max(len(per_case), 1)

    aggregate: Dict[str, Any] = {"num_cases": len(per_case), "k_values": k_list}
    for k in k_list:
        v_mean_r = statistics.mean(vec_recalls[k]) if vec_recalls[k] else 0.0
        h_mean_r = statistics.mean(hyb_recalls[k]) if hyb_recalls[k] else 0.0
        v_mean_mrr = statistics.mean(vec_mrrs[k]) if vec_mrrs[k] else 0.0
        h_mean_mrr = statistics.mean(hyb_mrrs[k]) if hyb_mrrs[k] else 0.0
        v_hit_rate = sum(vec_hits[k]) / n_cases
        h_hit_rate = sum(hyb_hits[k]) / n_cases
        delta_pp = (h_hit_rate - v_hit_rate) * 100.0
        aggregate[f"recall_at_{k}_mean_vector"] = round(v_mean_r, 4)
        aggregate[f"recall_at_{k}_mean_hybrid"] = round(h_mean_r, 4)
        aggregate[f"mrr_mean_at_{k}_vector"] = round(v_mean_mrr, 4)
        aggregate[f"mrr_mean_at_{k}_hybrid"] = round(h_mean_mrr, 4)
        aggregate[f"hit_at_{k}_rate_vector"] = round(v_hit_rate, 4)
        aggregate[f"hit_at_{k}_rate_hybrid"] = round(h_hit_rate, 4)
        aggregate[f"hit_at_{k}_hybrid_minus_vector_pp"] = round(delta_pp, 2)

    aggregate["by_scenario"] = _aggregate_rows_by_scenario(per_case, k_list)

    _bench_log(
        f"[bench] 延迟测试：warmup {min(3, len(latency_queries))} 次 + "
        f"{args.latency_runs} 次混合检索（每次一次向量化请求）…",
        quiet,
    )
    # 延迟：混合检索 wall time（与 RAGEngine.retrieve 调用链一致）
    warmup = min(3, len(latency_queries))
    for i in range(warmup):
        cq = latency_queries[i % len(latency_queries)]
        _silent_hybrid_search(hybrid_engine, cq, args.top_k_latency)

    lat_ms: List[float] = []
    for run_i in range(args.latency_runs):
        cq = latency_queries[run_i % len(latency_queries)]
        t0 = time.perf_counter()
        _silent_hybrid_search(hybrid_engine, cq, args.top_k_latency)
        lat_ms.append((time.perf_counter() - t0) * 1000.0)

    aggregate["latency_ms"] = {
        "top_k": args.top_k_latency,
        "runs": args.latency_runs,
        "mean": round(statistics.mean(lat_ms), 2),
        "stdev": round(statistics.stdev(lat_ms), 2) if len(lat_ms) > 1 else 0.0,
        "p50": round(statistics.median(lat_ms), 2),
        "p95": round(sorted(lat_ms)[min(len(lat_ms) - 1, max(0, int(0.95 * (len(lat_ms) - 1))))], 2)
        if lat_ms
        else 0.0,
    }

    _bench_log("[bench] 单条增量入库（写入后立即清理）…", quiet)
    # 增量入库：单 chunk，随后清理 Chroma + BM25 测试行
    eval_rid = f"__eval_bench_{uuid.uuid4().hex}__"
    eval_vid = f"vs_eval_{uuid.uuid4().hex}"
    bench_fp = str(root / "eval" / "bench_temp.md")
    inc_meta = {
        "source_document_id": bench_fp,
        "file_path": bench_fp,
        "section_type": "eval",
        "eval_temp": True,
    }
    inc_content = (
        "【评测临时文档】低盐蒸蛋羹：鸡蛋打散加温水1:1.5，过筛后小火蒸8分钟，滴香油。"
    ) * 2
    t_inc0 = time.perf_counter()
    vector_store.add_texts(
        texts=[inc_content],
        metadatas=[{**inc_meta, "original_chunk_id": f"eval-{eval_rid}"}],
        ids=[eval_vid],
    )
    bm25_indexer.index_content(
        recipe_id=eval_rid,
        content=inc_content,
        file_hash="eval",
        metadata=inc_meta,
    )
    incremental_s = time.perf_counter() - t_inc0
    try:
        vector_store.collection.delete(ids=[eval_vid])
    except Exception:
        pass
    cleanup_eval_bm25_row(bm25_path, eval_rid)

    _bench_log(
        "[bench] 统计索引规模（Chroma 会扫描全部 metadata，分块很多时可能需数十秒）…",
        quiet,
    )
    scale_chroma = chroma_scale(vector_store.collection)
    scale_bm25 = bm25_scale(bm25_path)
    chroma_bytes = dir_size_bytes(chroma_dir)

    out: Dict[str, Any] = {
        "gold_file": str(gold_path),
        "paths": {"chroma_dir": str(chroma_dir), "bm25_db": str(bm25_path)},
        "retrieval_quality": aggregate,
        "per_query": per_case,
        "index_scale": {
            "chroma": scale_chroma,
            "bm25_fts_rows": scale_bm25["fts_rows"],
            "bm25_db_file_mb": round(scale_bm25["db_file_bytes"] / (1024 * 1024), 3),
            "chroma_persist_dir_total_mb": round(chroma_bytes / (1024 * 1024), 3),
        },
        "incremental_index_one_chunk_seconds": round(incremental_s, 4),
    }
    _bench_log("[bench] 全部阶段完成，输出 JSON 与简历摘要。", quiet)
    return out


def print_resume_snippets(report: Dict[str, Any]) -> None:
    iq = report["retrieval_quality"]
    ks = iq.get("k_values") or [5]
    k = ks[0]
    sc = report["index_scale"]
    chunks = sc["chroma"].get("chunk_count", 0)
    ufiles = sc["chroma"].get("unique_file_paths")
    lat = iq["latency_ms"]

    print("\n========== 简历可用短句（请按实测替换 XX）==========\n")
    print(
        f"检索质量：在自建黄金集（n={iq['num_cases']}）上，"
        f"Top-{k} 平均召回率（多标签）混合检索 {iq.get(f'recall_at_{k}_mean_hybrid', 0):.2%}\n"
        f"纯向量 {iq.get(f'recall_at_{k}_mean_vector', 0):.2%}\n"
        f"平均 MRR 混合 {iq.get(f'mrr_mean_at_{k}_hybrid', 0):.3f} vs 向量 {iq.get(f'mrr_mean_at_{k}_vector', 0):.3f}\n"
        f"Top-{k}「至少命中一相关文档」命中率混合 {iq.get(f'hit_at_{k}_rate_hybrid', 0):.2%}\n"
        f"向量 {iq.get(f'hit_at_{k}_rate_vector', 0):.2%}\n"
        f"混合相对向量提升 {iq.get(f'hit_at_{k}_hybrid_minus_vector_pp', 0):+.1f} 个百分点。"
    )
    by_s = iq.get("by_scenario")
    if isinstance(by_s, dict) and by_s:
        print(f"\n---------- 分场景 Top-{k}（简历可引用）----------\n")
        for sk in sorted(by_s.keys(), key=lambda x: (_SCENARIO_ORDER.index(x) if x in _SCENARIO_ORDER else 99, x)):
            blk = by_s[sk]
            if not isinstance(blk, dict) or not blk.get("num_cases"):
                continue
            label = _SCENARIO_LABEL_ZH.get(sk, sk)
            n = blk["num_cases"]
            rh = blk.get(f"recall_at_{k}_mean_hybrid", 0)
            rv = blk.get(f"recall_at_{k}_mean_vector", 0)
            mh = blk.get(f"mrr_mean_at_{k}_hybrid", 0)
            mv = blk.get(f"mrr_mean_at_{k}_vector", 0)
            print(
                f"· {label}（{sk}，n={n}）：混合 Recall@{k} {rh:.2%}，向量 {rv:.2%}；"
                f"混合 MRR@{k} {mh:.3f}，向量 {mv:.3f}。"
            )
        print()
        if len(ks) > 1:
            print(
                f"（配置了多个 K：{ks}，其它 K 的分场景字段见 JSON `retrieval_quality.by_scenario`。）\n"
            )
    doc_line = f"索引覆盖约 {ufiles} 篇菜谱文档、{chunks} 个向量分块" if ufiles is not None else f"向量分块数 {chunks}"
    print(f"\n系统规模：{doc_line}\nBM25 行数 {sc['bm25_fts_rows']}\n"
          f"向量库目录约 {sc['chroma_persist_dir_total_mb']} MB，BM25 库文件约 {sc['bm25_db_file_mb']} MB\n")
    print(f"\n性能：混合检索端到端延迟均值约 {lat['mean']} ms（p95 {lat['p95']} ms\ntop_k={lat['top_k']}，n={lat['runs']}）；"
          f"单条新文档（向量+BM25）入库约 {report['incremental_index_one_chunk_seconds']:.3f} s\n")
    print("\n====================================================\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="检索量化指标评测（简历数据）")
    ap.add_argument("--gold", default="eval/data/retrieval_gold.json", help="黄金集 JSON 路径")
    ap.add_argument("--k", default="5", help="Recall/MRR 的 K 列表，逗号分隔（默认 5）")
    ap.add_argument("--latency-runs", type=int, default=40, help="延迟测量重复次数")
    ap.add_argument("--top-k-latency", type=int, default=5, help="测延迟时的 top_k")
    ap.add_argument("--chroma-path", default=None, help="Chroma 持久化目录（默认 data/db，与 MCP 一致）")
    ap.add_argument("--bm25-path", default=None, help="bm25_index.db 路径（默认 data/db/bm25_index.db）")
    ap.add_argument("--json-out", default=None, help="将完整报告写入 JSON 文件")
    ap.add_argument("--quiet", action="store_true", help="不输出分阶段进度（仍输出最终 JSON 与简历短句）")
    args = ap.parse_args()

    report = run_benchmark(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print_resume_snippets(report)

    if args.json_out:
        outp = Path(args.json_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"已写入: {outp.resolve()}")


if __name__ == "__main__":
    main()
