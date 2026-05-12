"""
T-043：E2E 测评产出物（开发计划 §5.5 链路树、§6 单用例报告与总报告、manifest 索引）。

- 单用例：`docs/evals/cases/<run_id>/<case_id>.md`（§5.5 树 + 期望/实际摘要 + §5.1～5.4 分项与总分）
- 总报告：`docs/evals/runs/<run_id>/e2e_summary.md`、`docs/evals/e2e_summary_<run_id>.md`、`docs/agent_eval_report.md`（NFR-11 固定入口）
- 更新：`docs/evals/runs/<run_id>/manifest.json` 增补 `scenario_category`、`case_report_md`、`scores_json`

由 `python -m eval.score_run` 在写出 `scores.json` 后默认调用；亦可单独
`python -m eval.e2e_reports --run-id <run_id>` 基于已有 `scores.json` + `captures/` 重生成。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_ROOT = Path(__file__).resolve().parents[1]


def _tri(ok: bool, na: bool = False) -> str:
    if na:
        return "—"
    return "✓" if ok else "✗"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_score(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return "—"


def _efficiency_metrics_one(scored: Mapping[str, Any]) -> Dict[str, Any]:
    """单条用例的 §5.4 原始量（与 `scoring.score_efficiency_layer` 一致）。"""
    if scored.get("status") != "ok":
        return {"total_wall_ms": None, "tokens_total_from_messages": None, "mcp_inferred_total": None}
    m = ((scored.get("layers") or {}).get("efficiency") or {}).get("metrics") or {}
    if not isinstance(m, dict):
        return {"total_wall_ms": None, "tokens_total_from_messages": None, "mcp_inferred_total": None}
    return {
        "total_wall_ms": m.get("total_wall_ms"),
        "tokens_total_from_messages": m.get("tokens_total_from_messages"),
        "mcp_inferred_total": m.get("mcp_inferred_total"),
    }


def aggregate_efficiency_across_cases(
    cases: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    从 T-042 `scores.json` 的 `cases[].layers.efficiency.metrics` 聚合全 run §5.4 观测。
    不参与加权总分，仅供总报告人类阅读（开发计划 §5.4 / §6）。
    """
    walls: List[float] = []
    toks: List[int] = []
    mcps: List[int] = []
    n_cases = len(cases)
    for c in cases:
        if c.get("status") != "ok":
            continue
        m = _efficiency_metrics_one(c)
        w = m.get("total_wall_ms")
        if isinstance(w, (int, float)):
            walls.append(float(w))
        t = m.get("tokens_total_from_messages")
        if t is not None:
            try:
                toks.append(int(t))
            except (TypeError, ValueError):
                pass
        mc = m.get("mcp_inferred_total")
        if mc is not None:
            try:
                mcps.append(int(mc))
            except (TypeError, ValueError):
                pass

    n_w = len(walls)
    n_t = len(toks)
    n_m = len(mcps)
    return {
        "run_case_count": n_cases,
        "timing_case_count": n_w,
        "sum_wall_ms": round(sum(walls), 3) if walls else None,
        "mean_wall_ms_per_case": round(sum(walls) / n_w, 3) if n_w else None,
        "token_sample_case_count": n_t,
        "sum_tokens": int(sum(toks)) if toks else None,
        "mean_tokens_per_case_where_present": round(sum(toks) / n_t, 3) if n_t else None,
        "mcp_count_sample_case_count": n_m,
        "sum_mcp_inferred": int(sum(mcps)) if mcps else None,
        "mean_mcp_per_case_where_present": round(sum(mcps) / n_m, 4) if n_m else None,
    }


def _fmt_cell_wall_tokens_mcp(scored: Mapping[str, Any]) -> Tuple[str, str, str]:
    m = _efficiency_metrics_one(scored)
    w = m.get("total_wall_ms")
    wall = f"{float(w):.1f}" if isinstance(w, (int, float)) else "—"
    t = m.get("tokens_total_from_messages")
    tok = str(int(t)) if t is not None else "—"
    mc = m.get("mcp_inferred_total")
    if mc is None:
        mcp = "—"
    elif isinstance(mc, (int, float)):
        mcp = str(int(mc))
    else:
        mcp = str(mc)
    return wall, tok, mcp


def _user_input_line(turns: Sequence[Mapping[str, Any]]) -> str:
    parts: List[str] = []
    for t in turns:
        u = str(t.get("input") or "").strip()
        if u:
            parts.append(u)
    if not parts:
        return "（无用户输入）"
    if len(parts) == 1:
        return parts[0]
    return " | ".join(f"[轮{t.get('turn', '?')}] {x}" for t, x in zip(turns, parts))


def _last_snapshot(turns: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not turns:
        return {}
    s = turns[-1].get("snapshot")
    return dict(s) if isinstance(s, dict) else {}


def _intent_tree_line(expected: Mapping[str, Any], last_snap: Mapping[str, Any]) -> Tuple[str, bool]:
    from eval.scoring import compute_intent_alignment_score

    score, detail = compute_intent_alignment_score(expected, last_snap)
    exp_pi = str(expected.get("primary_intent") or "").strip()
    act_pi = str(last_snap.get("primary_intent") or "").strip()
    exp_ints = detail.get("expected_intents") or []
    act_ints = detail.get("actual_intents") or []

    if not exp_pi and not exp_ints:
        line = f"  ├── 意图识别：实际 `{act_pi or '—'}` —（fixture 未声明 primary_intent / intents）"
        return line, True

    bits: List[str] = []
    if exp_pi:
        ok_p = bool(detail.get("primary_match") == 1.0)
        bits.append(
            f"主意图 期望 `{exp_pi}` · 实际 `{act_pi or '—'}` {_tri(ok_p)}"
        )
    if exp_ints:
        rec = float(detail.get("intents_subset_recall") or 0.0)
        ok_m = rec >= 1.0 - 1e-9
        bits.append(
            f"多意图 期望去重={exp_ints} ⊆ 实际（顺序无关）`{act_ints}` "
            f"召回={rec:.2f} {_tri(ok_m)}"
        )
    ok_all = score >= 1.0 - 1e-9
    line = "  ├── 意图识别：" + "；".join(bits)
    return line, ok_all


def _slots_tree_line(expected: Mapping[str, Any], last_snap: Mapping[str, Any]) -> Tuple[str, bool, bool]:
    ks = expected.get("key_slots") or {}
    slots = dict(last_snap.get("slots") or {})
    if not isinstance(ks, dict) or not ks:
        return "  ├── 槽位提取：—（fixture 未声明 key_slots）", True, True
    hits = 0
    details: List[str] = []
    for k, v in ks.items():
        ev = str(v).strip().lower()
        av_raw = slots.get(k)
        if av_raw is None:
            details.append(f"{k}=?")
            continue
        if isinstance(av_raw, list):
            avs = " ".join(str(x).lower() for x in av_raw)
        else:
            avs = str(av_raw).lower()
        if ev and (ev in avs or avs in ev or any(ev in str(x).lower() for x in (av_raw if isinstance(av_raw, list) else [av_raw]))):
            hits += 1
            details.append(f"{k}≈匹配")
        else:
            details.append(f"{k} 期望含 `{v}` 实际 `{av_raw}`")
    ok = hits >= len(ks)
    line = f"  ├── 槽位提取：{', '.join(details)} {_tri(ok)}"
    return line, ok, False


def _retrieval_tree_line(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    retrieval_layer: Mapping[str, Any],
) -> Tuple[str, bool]:
    from eval.scoring import _candidate_titles_and_ids_from_turn_snapshots, _match_golden_to_rank, stem_from_golden_id

    titles, ids = _candidate_titles_and_ids_from_turn_snapshots(turns)
    n = len(titles)
    goldens = list(expected.get("golden_recipe_ids") or [])
    if not goldens:
        na = n == 0
        msg = f"检索侧候选约 {n} 条标题线索（无 golden_recipe_ids 约束）"
        return f"  ├── 检索调用：{msg} {_tri(True, na=False)}", True
    hits = 0
    best_rank: Optional[int] = None
    for gid in goldens:
        stem = stem_from_golden_id(str(gid))
        hit, rank = _match_golden_to_rank(stem, titles, ids)
        if hit:
            hits += 1
            if rank is not None and (best_rank is None or rank < best_rank):
                best_rank = rank
    sub = (retrieval_layer.get("submetrics") or {}).get("recall_hit_at_k") or {}
    recall_ok = bool(sub.get("status") == "ok" and float(sub.get("score") or 0) >= 1.0)
    ok = hits > 0 or recall_ok
    rank_s = f"，金标最佳名次={best_rank}" if best_rank else ""
    return (
        f"  ├── 检索调用：候选标题线索 {n} 条{rank_s} {_tri(ok)}",
        ok,
    )


def _reply_tree_line(
    turns: Sequence[Mapping[str, Any]],
    scored: Mapping[str, Any],
) -> str:
    reply = ""
    if turns:
        reply = str(turns[-1].get("assistant_reply") or "").strip()
    if scored.get("status") == "error":
        return f"  └── 生成回复：✗（采集/执行错误：`{scored.get('error', '')}`）"
    ov = scored.get("overall_score")
    layers = scored.get("layers") or {}
    gen = layers.get("generation") or {}
    g = gen.get("aggregate_score")
    hard = scored.get("hard_fail_retrieval")
    snippet = reply.replace("\n", " ")[:120] + ("…" if len(reply) > 120 else "")
    if not reply.strip():
        return "  └── 生成回复：✗（空回复）"
    ok = bool(not hard and ov is not None and float(ov) >= 0.35)
    if g is not None and float(g) < 0.25:
        ok = False
    reason = ""
    if hard:
        reason = "；检索硬失败封顶"
    elif ov is not None and float(ov) < 0.35:
        reason = "；总分偏低"
    return f"  └── 生成回复：末轮可见文本片段「{snippet}」{_tri(ok)}{reason}"


def build_section_5_5_chain_tree(
    capture: Mapping[str, Any],
    scored: Mapping[str, Any],
) -> str:
    """开发计划 §5.5 同构树状摘要（✓ / ✗ / —）。"""
    turns = list(capture.get("turns") or [])
    fixture = capture.get("fixture") or {}
    expected = fixture.get("expected") or {}
    last_snap = _last_snapshot(turns)
    layers = scored.get("layers") or {}
    r_layer = layers.get("retrieval") or {}

    head = f'用户输入："{_user_input_line(turns)}"'
    lines = ["```text", head]

    l1, _ = _intent_tree_line(expected, last_snap)
    l2, _, _ = _slots_tree_line(expected, last_snap)
    l3, _ = _retrieval_tree_line(expected, turns, r_layer)
    l4 = "  ├── 过滤排序：—（未实现）"  # 规格 §5.5：独立排序键未在采集中暴露
    l5 = _reply_tree_line(turns, scored)

    for x in (l1, l2, l3, l4, l5):
        lines.append(x)
    lines.append("```")
    return "\n".join(lines)


def _expected_actual_table(
    expected: Mapping[str, Any],
    last_snap: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
) -> List[str]:
    rows = [
        "| 项 | 期望 | 实际 |",
        "|---|------|------|",
        f"| primary_intent | `{expected.get('primary_intent') or '—'}` | `{last_snap.get('primary_intent') or '—'}` |",
    ]
    exp_i = expected.get("intents")
    act_i = last_snap.get("intents")
    if isinstance(exp_i, list) and exp_i:
        rows.append(
            f"| intents（多意图子集召回） | `{exp_i}` | `{act_i if isinstance(act_i, list) else '—'}` |"
        )
    rows.append(
        f"| needs_clarification | `{expected.get('needs_clarification')}` | `{last_snap.get('needs_clarification')}` |",
    )
    gold = expected.get("golden_recipe_ids")
    if gold:
        from eval.scoring import _candidate_titles_and_ids_from_turn_snapshots, stem_from_golden_id

        titles, ids = _candidate_titles_and_ids_from_turn_snapshots(turns)
        hit_ranks: List[str] = []
        for gid in gold:
            stem = stem_from_golden_id(str(gid))
            from eval.scoring import _match_golden_to_rank

            hit, rank = _match_golden_to_rank(stem, titles, ids)
            hit_ranks.append(f"{gid}:{'命中@'+str(rank) if hit else '未命中'}")
        rows.append(f"| golden_recipe_ids | `{gold}` | `{'; '.join(hit_ranks)}` |")
    return rows


def _layer_scores_md(scored: Mapping[str, Any]) -> List[str]:
    if scored.get("status") == "error":
        return ["- **总分**：`0`（执行错误）", ""]
    layers = scored.get("layers") or {}
    out: List[str] = [
        "## §5.1～5.4 分项与用例总分",
        "",
        f"- **overall（§5.6 加权）**：`{scored.get('overall_score')}`"
        + ("（检索硬失败封顶）" if scored.get("hard_fail_retrieval") else ""),
        "",
    ]
    for key, title in (
        ("retrieval", "检索层 §5.1"),
        ("generation", "生成层 §5.2"),
        ("dialogue", "对话层 §5.3"),
        ("efficiency", "效率 §5.4（观测，不计入 overall）"),
    ):
        L = layers.get(key) or {}
        agg = L.get("aggregate_score")
        inc = L.get("included_in_overall")
        if key == "efficiency":
            m = (L.get("metrics") or {})
            out.append(f"- **{title}**：`metrics` wall_ms={m.get('total_wall_ms')} tokens={m.get('tokens_total_from_messages')} mcp≈{m.get('mcp_inferred_total')}")
        else:
            flag = "" if inc is not False else "（未计入总分）"
            out.append(f"- **{title}**：aggregate=`{_fmt_score(agg)}`{flag}")
    out.append("")
    out.append("机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。")
    out.append("")
    return out


def render_per_case_markdown(capture: Mapping[str, Any], scored: Mapping[str, Any]) -> str:
    cid = str(capture.get("case_id") or scored.get("case_id") or "—")
    fixture = capture.get("fixture") or {}
    cat = str(fixture.get("scenario_category") or "—")
    turns = list(capture.get("turns") or [])
    last_snap = _last_snapshot(turns)

    parts: List[str] = [
        f"# E2E 单用例报告：`{cid}`",
        "",
        f"- **场景分类**：`{cat}`",
        f"- **来源**：`{capture.get('source_file') or '—'}`",
        "",
        "## §5.5 业务链路树",
        "",
        build_section_5_5_chain_tree(capture, scored),
        "",
        "## 期望 vs 实际摘要",
        "",
        *_expected_actual_table(fixture.get("expected") or {}, last_snap, turns),
        "",
        *_layer_scores_md(scored),
    ]
    return "\n".join(parts)


def _find_previous_run_dir(run_dir: Path) -> Optional[Path]:
    """按目录名（含时间戳）字典序，取当前 run 的前一带 `scores.json` 的兄弟目录。"""
    parent = run_dir.parent
    if not parent.is_dir():
        return None
    siblings = sorted(
        [p for p in parent.iterdir() if p.is_dir() and (p / "scores.json").is_file()],
        key=lambda p: p.name,
    )
    try:
        idx = next(i for i, p in enumerate(siblings) if p.resolve() == run_dir.resolve())
    except StopIteration:
        return None
    if idx <= 0:
        return None
    return siblings[idx - 1]


def render_run_summary_markdown(
    report: Mapping[str, Any],
    *,
    run_id: str,
    manifest_path: str,
    prev_report: Optional[Mapping[str, Any]] = None,
) -> str:
    """§6 测评总报告（人类主读 Markdown）。"""
    cases = list(report.get("cases") or [])
    eff_agg = aggregate_efficiency_across_cases(cases)

    lines: List[str] = [
        "# E2E 测评总报告（T-043）",
        "",
        f"- **run_id**：`{run_id}`",
        f"- **run 目录**：`{report.get('run_dir', '')}`",
        f"- **manifest**：`{manifest_path}`",
        f"- **用例数**：{report.get('case_count', 0)}",
        f"- **平均分 overall（§5.6）**：**{report.get('mean_overall_score')}**",
        "",
        "## §5.0～5.4 汇总",
        "",
        "| 维度 | 值 |",
        "|------|-----|",
        f"| 检索层集级 MRR 均值（§5.1） | `{report.get('mean_mrr_retrieval')}` |",
    ]
    w = report.get("weights") or {}
    lines.append(
        f"| 加权权重（§5.6，效率不计分） | 检索 {w.get('retrieval')} · 生成 {w.get('generation')} · 对话 {w.get('dialogue')} |"
    )
    def _md_cell(v: Any) -> str:
        return "`—`" if v is None else f"`{v}`"

    lines.extend(
        [
            "",
            "## §5.4 效率观测汇总（**不计入** §5.6 加权 overall）",
            "",
            "聚合自各用例 `scores.json` → `cases[].layers.efficiency.metrics`（与单用例报告 §5.4 行同源）。",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| 有墙钟数据的用例数 / 报告内用例数 | `{eff_agg['timing_case_count']}` / `{eff_agg['run_case_count']}` |",
            f"| 全 run 墙钟合计（ms） | {_md_cell(eff_agg['sum_wall_ms'])} |",
            f"| 每用例墙钟算术均值（ms） | {_md_cell(eff_agg['mean_wall_ms_per_case'])} |",
            f"| 有 token 采样的用例数 | `{eff_agg['token_sample_case_count']}` |",
            f"| token 合计（仅计有采样的消息） | {_md_cell(eff_agg['sum_tokens'])} |",
            f"| token 有采样时的每用例均值 | {_md_cell(eff_agg['mean_tokens_per_case_where_present'])} |",
            f"| 有 MCP 推断计数的用例数 | `{eff_agg['mcp_count_sample_case_count']}` |",
            f"| MCP 推断次数合计（全 run） | {_md_cell(eff_agg['sum_mcp_inferred'])} |",
            f"| MCP 有计数时的每用例均值 | {_md_cell(eff_agg['mean_mcp_per_case_where_present'])} |",
            "",
            "## 通过率与失败索引",
            "",
        ]
    )
    n = len(cases)
    ok_exec = sum(1 for c in cases if c.get("status") == "ok")
    failed_ids: List[str] = []
    for c in cases:
        cid = str(c.get("case_id") or "")
        if c.get("status") == "error":
            failed_ids.append(f"{cid}（执行/采集错误）")
            continue
        if c.get("hard_fail_retrieval"):
            failed_ids.append(f"{cid}（检索硬失败）")
            continue
        ov = c.get("overall_score")
        if ov is not None and float(ov) < 0.35:
            failed_ids.append(f"{cid}（overall<0.35）")

    lines.append(f"- **可打分用例**：{ok_exec}/{n}")
    lines.append(f"- **本报告「失败」索引条数**：{len(failed_ids)}（执行错误 + 检索硬失败 + 总分过低）")
    if failed_ids:
        lines.append("")
        for x in failed_ids:
            lines.append(f"  - `{x}`")
    lines.extend(
        [
            "",
            "## 单用例报告路径",
            "",
            "每条 Markdown：`docs/evals/cases/<run_id>/<case_id>.md`（本 run 已生成）。下表 **wall_ms / tokens / mcp≈** 为 §5.4 观测，**不计入** overall。",
            "",
            "| case_id | overall | wall_ms | tokens | mcp≈ | 单报告 |",
            "|---------|---------|---------|--------|------|--------|",
        ]
    )
    for c in cases:
        cid = str(c.get("case_id") or "—")
        ov = c.get("overall_score")
        ov_s = _fmt_score(ov) if c.get("status") == "ok" else "—"
        wa, to, mc = _fmt_cell_wall_tokens_mcp(c)
        rel = f"docs/evals/cases/{run_id}/{cid}.md"
        lines.append(f"| `{cid}` | {ov_s} | {wa} | {to} | {mc} | `{rel}` |")

    lines.extend(
        [
            "",
            "## 原始采集与机器成绩",
            "",
            f"- captures：`docs/evals/runs/{run_id}/captures/`",
            f"- scores：`docs/evals/runs/{run_id}/scores.json`",
            "",
        ]
    )

    if prev_report:
        lines.extend(
            [
                "## 与上一带分 run 对比（可选）",
                "",
                f"- 上一 run：`{prev_report.get('run_dir', '')}`",
                f"- 上一 mean_overall：`{prev_report.get('mean_overall_score')}` → 本次 `{report.get('mean_overall_score')}`",
                "",
            ]
        )

    lines.append("---\n\n与 `docs/test_report.md` 职责划分见规格 §10.6 / 开发计划 §6。")
    return "\n".join(lines)


def _merge_manifest(
    run_dir: Path,
    run_id: str,
    entries_extra: Dict[str, Dict[str, Any]],
) -> None:
    mpath = run_dir / "manifest.json"
    if not mpath.is_file():
        return
    man = _load_json(mpath)
    if not isinstance(man, dict):
        return
    ent = man.get("entries")
    if not isinstance(ent, list):
        return
    for row in ent:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("case_id") or "")
        ex = entries_extra.get(cid)
        if not ex:
            continue
        row["scenario_category"] = ex.get("scenario_category")
        row["case_report_md"] = ex.get("case_report_md")
        row["scores_json"] = ex.get("scores_json")
    man["t043"] = {
        "case_reports_root": f"docs/evals/cases/{run_id}",
        "scores_json": f"docs/evals/runs/{run_id}/scores.json",
        "e2e_summary_md": f"docs/evals/runs/{run_id}/e2e_summary.md",
    }
    mpath.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def write_all_t043_artifacts(
    run_dir: Path,
    report: Mapping[str, Any],
    *,
    write_main_agent_eval_report: bool = True,
    docs_root: Optional[Path] = None,
) -> Dict[str, str]:
    """
    写入单用例 MD、总报告三处、更新 manifest。

    :param docs_root: 默认 ``<项目根>/docs``；单测可传入临时目录隔离写入。
    返回：各产出物绝对路径或相对项目根的说明路径（字符串）。
    """
    run_dir = run_dir.resolve()
    run_id = run_dir.name
    doc_base = (docs_root or (_ROOT / "docs")).resolve()
    cases_root = doc_base / "evals" / "cases" / run_id
    cases_root.mkdir(parents=True, exist_ok=True)

    cap_dir = run_dir / "captures"
    entries_extra: Dict[str, Dict[str, Any]] = {}
    scores_rel = f"docs/evals/runs/{run_id}/scores.json"

    for scored in report.get("cases") or []:
        cid = str(scored.get("case_id") or "")
        if not cid:
            continue
        cap_path = cap_dir / f"{cid}.json"
        if cap_path.is_file():
            capture = _load_json(cap_path)
        else:
            capture = {"case_id": cid, "turns": [], "fixture": {}}
        body = render_per_case_markdown(capture, scored)
        out_md = cases_root / f"{cid}.md"
        out_md.write_text(body, encoding="utf-8")
        fix = capture.get("fixture") or {}
        entries_extra[cid] = {
            "scenario_category": str(fix.get("scenario_category") or ""),
            "case_report_md": f"docs/evals/cases/{run_id}/{cid}.md",
            "scores_json": scores_rel,
        }

    _merge_manifest(run_dir, run_id, entries_extra)

    prev: Optional[Mapping[str, Any]] = None
    prev_dir = _find_previous_run_dir(run_dir)
    if prev_dir and (prev_dir / "scores.json").is_file():
        try:
            prev = _load_json(prev_dir / "scores.json")
            if not isinstance(prev, dict):
                prev = None
        except (OSError, json.JSONDecodeError):
            prev = None

    summary = render_run_summary_markdown(
        report,
        run_id=run_id,
        manifest_path=f"docs/evals/runs/{run_id}/manifest.json",
        prev_report=prev,
    )
    p_run = run_dir / "e2e_summary.md"
    p_run.write_text(summary, encoding="utf-8")
    p_named = doc_base / "evals" / f"e2e_summary_{run_id}.md"
    p_named.parent.mkdir(parents=True, exist_ok=True)
    p_named.write_text(summary, encoding="utf-8")

    main = doc_base / "agent_eval_report.md"
    if write_main_agent_eval_report:
        main.write_text(summary, encoding="utf-8")

    return {
        "cases_root": str(cases_root),
        "e2e_summary_run": str(p_run),
        "e2e_summary_named": str(p_named),
        "agent_eval_report": str(main) if write_main_agent_eval_report else "",
    }


def regenerate_from_run_dir(
    run_dir: Path,
    *,
    write_main: bool = True,
    docs_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """从已有 `scores.json` 重跑 T-043 产出（不重新打分）。"""
    run_dir = run_dir.resolve()
    sp = run_dir / "scores.json"
    if not sp.is_file():
        raise FileNotFoundError(f"缺少 scores.json: {sp}")
    report = _load_json(sp)
    if not isinstance(report, dict):
        raise ValueError("scores.json 顶层须为对象")
    paths = write_all_t043_artifacts(
        run_dir,
        report,
        write_main_agent_eval_report=write_main,
        docs_root=docs_root,
    )
    return {"report": report, "paths": paths}


def main() -> int:
    parser = argparse.ArgumentParser(description="T-043：从已有 scores.json 重生成单用例 MD 与总报告")
    parser.add_argument("--run-dir", type=str, default=None)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument(
        "--no-main-report",
        action="store_true",
        help="不写 docs/agent_eval_report.md（仅 runs/ 与 e2e_summary_<run_id>.md）",
    )
    parser.add_argument(
        "--docs-root",
        type=str,
        default=None,
        help="覆盖 docs 根目录（默认项目 docs/），供高级场景使用",
    )
    args = parser.parse_args()
    if not logging.root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from eval.score_run import resolve_run_dir

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    elif args.run_id:
        run_dir = resolve_run_dir(args.run_id)
    else:
        logging.error("请指定 --run-dir 或 --run-id")
        return 2
    dr = Path(args.docs_root).resolve() if args.docs_root else None
    out = regenerate_from_run_dir(
        run_dir, write_main=not args.no_main_report, docs_root=dr
    )
    logging.info("T-043 已写入 %s", out.get("paths"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
