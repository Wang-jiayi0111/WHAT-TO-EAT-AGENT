"""
LLM 意图识别端到端验收（IntentClassifier.get_intent_details）。

对照 ``src/agent/prompts/intent_prompt.md`` 的意图目录、§11.5 缺失码与示例话术，
校验：**结构化字段契约** + **主意图/任务栈与需求一致（宽松集合）**。

**默认跳过**（无 API 费用、CI 稳定）。启用真实调用::

    # PowerShell
    $env:WHAT_TO_EAT_RUN_LLM_INTENT = "1"
    python -m pytest tests/integration/test_intent_recognition_llm.py -v --tb=short

可选：每条用例后再问一次评审模型（更慢）::

    $env:WHAT_TO_EAT_INTENT_LLM_JUDGE = "1"

导出原始 JSON 便于人工对照需求::

    $env:WHAT_TO_EAT_INTENT_REPORT = "logs/intent_llm_report.json"
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import pytest
from langchain_core.messages import HumanMessage

from tests.conftest import make_minimal_agent_state

RUN_LLM = os.environ.get("WHAT_TO_EAT_RUN_LLM_INTENT", "").lower() in (
    "1",
    "true",
    "yes",
)
USE_JUDGE = os.environ.get("WHAT_TO_EAT_INTENT_LLM_JUDGE", "").lower() in (
    "1",
    "true",
    "yes",
)
REPORT_PATH = os.environ.get("WHAT_TO_EAT_INTENT_REPORT", "").strip()

pytestmark = [
    pytest.mark.skipif(
        not RUN_LLM,
        reason="Set WHAT_TO_EAT_RUN_LLM_INTENT=1 to run real-LLM intent tests.",
    ),
    pytest.mark.llm_intent,
]


# 与 IntentResult / intent_prompt § Intent Categories 一致
ALLOWED_INTENTS: Set[str] = {
    "profile_sync",
    "recipe_search",
    "inventory_check",
    "inventory_add",
    "dietary_advice",
    "shopping_list",
    "inventory_commit",
    "general_chat",
    "help",
    "out_of_scope",
    "recipe_adopt",
    "user_clarify",
}

@dataclass(frozen=True)
class IntentLlmCase:
    id: str
    utterance: str
    # 主意图允许集合（模型方差）
    expect_primary_one_of: Sequence[str]
    min_confidence: float = 0.0
    # 若给出：intents 必须包含其中每一个（多意图组合验收）
    intents_must_include: Optional[Sequence[str]] = None
    # 若给出：task_stack 中至少出现以下任一子串（内部任务码）
    expect_task_any: Optional[Sequence[str]] = None
    # 若 True：要求 needs_clarification 为 True 或 task_stack 含 TASK_CLARIFY 或 missing 非空
    expect_clarify_or_missing: bool = False


# 话术与 intent_prompt.md Examples / § 目录对齐；宽松集合降低 flaky
INTENT_LLM_CASES: List[IntentLlmCase] = [
    # Example 1
    IntentLlmCase(
        "ex01_inventory_check_meat",
        "冰箱里还有肉吗？",
        ("inventory_check",),
        0.35,
        ("inventory_check",),
        ("TASK_INV_CHECK", "TASK_CLARIFY", "TASK_DIRECT_REPLY"),
    ),
    # Example 3
    IntentLlmCase(
        "ex03_inventory_commit_done",
        "刚才的清蒸鱼做好了。",
        ("inventory_commit", "recipe_search", "general_chat"),
        0.35,
        ("inventory_commit",),
        ("TASK_INV_COMMIT", "TASK_CLARIFY", "TASK_DIRECT_REPLY", "TASK_SEARCH"),
    ),
    # Example 5
    IntentLlmCase(
        "ex05_inventory_add_restock",
        "超市买了鸡蛋一盒、牛奶两瓶，还有一袋大米。",
        ("inventory_add",),
        0.35,
        ("inventory_add",),
        ("TASK_INV_ADD", "TASK_CLARIFY", "TASK_DIRECT_REPLY"),
    ),
    # Example 7 — 缺锚 + 清单
    IntentLlmCase(
        "ex07_vague_search_and_shopping",
        "随便推荐个菜吧，再看看缺啥要买。",
        ("recipe_search", "shopping_list", "general_chat"),
        0.2,
        ("recipe_search", "shopping_list"),
        None,
        expect_clarify_or_missing=True,
    ),
    IntentLlmCase(
        "search_named_dish",
        "我想做红烧肉，帮我找几个做法。",
        ("recipe_search",),
        0.35,
        ("recipe_search",),
        ("TASK_SEARCH", "TASK_CLARIFY"),
    ),
    IntentLlmCase(
        "help_capabilities",
        "你能做什么？",
        ("help", "general_chat"),
        0.25,
        None,
        ("TASK_DIRECT_REPLY",),
    ),
    IntentLlmCase(
        "out_of_scope_code",
        "帮我写一段 Python 快速排序。",
        ("out_of_scope", "general_chat"),
        0.2,
        None,
        ("TASK_DIRECT_REPLY",),
    ),
    IntentLlmCase(
        "dietary_advice_cold",
        "我感冒了，饮食上有什么要注意的？",
        ("dietary_advice", "general_chat"),
        0.2,
        None,
        ("TASK_DIRECT_REPLY",),
    ),
    IntentLlmCase(
        "profile_peanut",
        "帮我记下，我对花生过敏。",
        ("profile_sync", "general_chat"),
        0.25,
        ("profile_sync",),
        ("TASK_PROFILE_SYNC", "TASK_DIRECT_REPLY", "TASK_CLARIFY"),
    ),
    IntentLlmCase(
        "multi_add_search_list",
        "买了点猪肉，想做红烧肉，看看还差什么。",
        (
            "inventory_add",
            "recipe_search",
            "shopping_list",
            "inventory_check",
            "general_chat",
        ),
        0.2,
        ("recipe_search",),
        None,
    ),
    IntentLlmCase(
        "weak_chat",
        "今天天气真不错。",
        ("general_chat", "help"),
        0.1,
        None,
        ("TASK_DIRECT_REPLY",),
    ),
]


def _state(utterance: str) -> Dict[str, Any]:
    s = make_minimal_agent_state()
    s["messages"] = [HumanMessage(content=utterance)]
    s["active_user_id"] = "intent_llm_eval"
    s["conversation_summary"] = ""
    return s


def _all_task_tokens() -> Set[str]:
    from src.agent.nodes.router import IntentClassifier

    out: Set[str] = set()
    for tasks in IntentClassifier.INTENT_TASK_MAPPING.values():
        for t in tasks:
            out.add(t)
    out.add("TASK_CLARIFY")
    return out


def assert_structural_contract(details: Dict[str, Any], case_id: str) -> None:
    assert isinstance(details, dict), f"{case_id}: not a dict"
    primary = details.get("primary_intent") or details.get("intent")
    assert primary in ALLOWED_INTENTS, f"{case_id}: invalid primary {primary!r}"

    intents = list(details.get("intents") or [])
    assert intents, f"{case_id}: empty intents"
    for it in intents:
        assert it in ALLOWED_INTENTS, f"{case_id}: invalid intent {it!r}"

    conf = float(details.get("confidence", -1.0))
    assert 0.0 <= conf <= 1.0, f"{case_id}: confidence out of range {conf}"

    ms = details.get("missing_slots") or []
    assert isinstance(ms, list), f"{case_id}: missing_slots not list"
    for m in ms:
        assert isinstance(m, str), f"{case_id}: missing slot not str {m!r}"

    slots = details.get("slots")
    assert slots is None or isinstance(slots, dict), f"{case_id}: slots not dict"

    tasks = list(details.get("task_stack") or [])
    assert tasks, f"{case_id}: empty task_stack"
    known_tasks = _all_task_tokens()
    for t in tasks:
        assert t in known_tasks, f"{case_id}: unknown task {t!r}"


@pytest.fixture(scope="module")
def classifier():
    from src.agent.nodes.router import IntentClassifier

    return IntentClassifier()


@pytest.fixture(scope="module")
def judge_llm():
    if not USE_JUDGE:
        return None
    from src.libs.adapters.llm.llm_factory import LLMFactory
    from src.libs.base.settings import Settings

    return LLMFactory.get_llm(Settings())


def _llm_judge(judge_llm, utterance: str, details: Dict[str, Any]) -> bool:
    prompt = (
        "You are a QA judge for a meal-planning assistant intent router. "
        "Reply with exactly one word: ACCEPT or REJECT.\n"
        f"User: {utterance}\n"
        f"System: primary={details.get('primary_intent')}, intents={details.get('intents')}, "
        f"task_stack={details.get('task_stack')}, needs_clarification={details.get('needs_clarification')}\n"
        "ACCEPT if the routing is broadly reasonable; otherwise REJECT."
    )
    resp = judge_llm.invoke(prompt)
    text = (getattr(resp, "content", None) or str(resp)).strip().upper()
    if not text:
        return False
    return text.split()[0].startswith("ACCEPT")


@pytest.mark.parametrize("case", INTENT_LLM_CASES, ids=lambda c: c.id)
def test_intent_llm_case_contract_and_expectation(
    classifier, judge_llm, case: IntentLlmCase
):
    details = classifier.get_intent_details(_state(case.utterance))
    assert_structural_contract(details, case.id)

    primary = details.get("primary_intent") or details.get("intent")
    assert primary in case.expect_primary_one_of, (
        f"{case.id}: primary={primary!r} not in {case.expect_primary_one_of!r}; "
        f"details={_json_short(details)}"
    )

    conf = float(details.get("confidence") or 0.0)
    assert conf >= case.min_confidence, (
        f"{case.id}: conf={conf} < {case.min_confidence}; {_json_short(details)}"
    )

    intents = list(details.get("intents") or [])
    if case.intents_must_include:
        for need in case.intents_must_include:
            assert need in intents, (
                f"{case.id}: expected intent {need!r} missing in {intents!r}; "
                f"{_json_short(details)}"
            )

    tasks = list(details.get("task_stack") or [])
    if case.expect_task_any:
        ok = any(tok in " ".join(tasks) for tok in case.expect_task_any)
        assert ok, (
            f"{case.id}: task_stack={tasks!r} has none of {case.expect_task_any!r}; "
            f"{_json_short(details)}"
        )

    if case.expect_clarify_or_missing:
        ms = list(details.get("missing_slots") or [])
        clarify = "TASK_CLARIFY" in tasks
        need_cl = bool(details.get("needs_clarification"))
        assert clarify or need_cl or ms, (
            f"{case.id}: expected clarify/missing path; tasks={tasks!r} "
            f"needs_clarification={need_cl} missing_slots={ms!r}; {_json_short(details)}"
        )

    if USE_JUDGE and judge_llm is not None:
        assert _llm_judge(judge_llm, case.utterance, details), (
            f"{case.id}: LLM judge REJECT; {_json_short(details)}"
        )


def test_intent_llm_write_report_json(classifier, tmp_path):
    """汇总 JSON，便于与 SRS / intent_prompt 人工对照。"""
    rows: List[Dict[str, Any]] = []
    for case in INTENT_LLM_CASES:
        details = classifier.get_intent_details(_state(case.utterance))
        assert_structural_contract(details, case.id)
        rows.append(
            {
                "case_id": case.id,
                "utterance": case.utterance,
                "expect_primary_one_of": list(case.expect_primary_one_of),
                "got": {
                    "primary_intent": details.get("primary_intent"),
                    "intents": details.get("intents"),
                    "confidence": details.get("confidence"),
                    "needs_clarification": details.get("needs_clarification"),
                    "task_stack": details.get("task_stack"),
                    "missing_slots": details.get("missing_slots"),
                    "slots": details.get("slots"),
                    "reasoning": (details.get("reasoning") or "")[:2000],
                },
            }
        )
    out = Path(REPORT_PATH) if REPORT_PATH else tmp_path / "intent_llm_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    assert out.exists()


def _json_short(d: Dict[str, Any], limit: int = 1200) -> str:
    try:
        s = json.dumps(d, ensure_ascii=False, default=str)
    except TypeError:
        s = str(d)
    return s if len(s) <= limit else s[:limit] + "…"
