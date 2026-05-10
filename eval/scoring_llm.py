"""
E2E 打分：调用 LLM 对幻觉、忌口、澄清话术、回复整体质量四维评分。
单一 Prompt：`src/agent/prompts/eval_judge_quality.md`（占位符 {{CONTEXT}}）。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROMPTS_DIR = _PROJECT_ROOT / "src" / "agent" / "prompts"

_EVAL_JUDGE_PROMPT = "eval_judge_quality.md"


def _load_text(rel: str) -> str:
    p = _PROMPTS_DIR / rel
    if not p.is_file():
        raise FileNotFoundError(f"评测 prompt 缺失: {p}")
    return p.read_text(encoding="utf-8")


def _build_eval_context_json(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    recipe_detail: Optional[Dict[str, Any]],
) -> str:
    replies = [str(t.get("assistant_reply") or "") for t in turns]
    user_inputs = []
    for t in turns:
        ui = t.get("input")
        if ui is not None:
            user_inputs.append(str(ui))
    ctx = {
        "expected_summary": {
            "primary_intent": expected.get("primary_intent"),
            "needs_clarification": expected.get("needs_clarification"),
            "scenario_category": expected.get("scenario_category"),
            "output_contains": expected.get("output_contains"),
            "output_excludes": expected.get("output_excludes"),
            "golden_recipe_ids": expected.get("golden_recipe_ids"),
        },
        "user_turn_inputs": user_inputs,
        "assistant_replies": replies,
        "recipe_detail_excerpt": None,
    }
    if isinstance(recipe_detail, dict):
        ing = recipe_detail.get("ingredients")
        title = recipe_detail.get("title")
        ctx["recipe_detail_excerpt"] = {
            "title": title,
            "ingredient_names_sample": [
                str(row.get("name"))
                for row in (ing if isinstance(ing, list) else [])[:40]
                if isinstance(row, dict) and row.get("name")
            ],
            "steps_len": len(recipe_detail.get("steps"))
            if isinstance(recipe_detail.get("steps"), list)
            else 0,
        }
    return json.dumps(ctx, ensure_ascii=False, indent=2)


def build_llm_judge_prompt(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    recipe_detail: Optional[Dict[str, Any]],
) -> str:
    template = _load_text(_EVAL_JUDGE_PROMPT)
    ctx = _build_eval_context_json(expected, turns, recipe_detail)
    return template.replace("{{CONTEXT}}", ctx)


def _extract_json_object(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("响应中无 JSON 对象")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("JSON 根须为对象")
    return obj


def _clamp01(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def invoke_llm_quality_judge(
    expected: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    recipe_detail: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """同步调用配置中的 Chat LLM，返回四维分数。"""
    from langchain_core.messages import HumanMessage

    from src.libs.adapters.llm.llm_factory import LLMFactory
    from src.libs.base.settings import Settings

    prompt = build_llm_judge_prompt(expected, turns, recipe_detail)
    settings = Settings()
    llm = LLMFactory.get_llm(settings)
    try:
        msg = llm.invoke([HumanMessage(content=prompt)])
    except Exception as e:
        logger.warning("LLM 评测调用失败: %s", e)
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "scores": {},
            "raw_response": "",
        }

    text = getattr(msg, "content", None) or str(msg)
    try:
        obj = _extract_json_object(text)
    except Exception as e:
        logger.warning("LLM 评测 JSON 解析失败: %s  raw=%s", e, text[:400])
        return {
            "status": "error",
            "error": f"parse: {e}",
            "scores": {},
            "raw_response": text[:4000],
        }

    scores = {
        "hallucination": _clamp01(obj.get("hallucination_score")),
        "dietary_taboo": _clamp01(obj.get("dietary_taboo_score")),
        "clarification_quality": _clamp01(obj.get("clarification_quality_score")),
        "reply_overall": _clamp01(obj.get("reply_overall_quality_score")),
    }
    out: Dict[str, Any] = {
        "status": "ok",
        "scores": scores,
        "rationales": obj.get("rationales") if isinstance(obj.get("rationales"), dict) else {},
        "raw_response": text[:4000],
    }
    return out
