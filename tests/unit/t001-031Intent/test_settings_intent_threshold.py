"""T-005：intent.confidence.clarify_threshold（规格 §8）。"""

from src.libs.base.settings import Settings


def test_default_clarify_threshold_when_key_missing(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("llm:\n  model: x\n", encoding="utf-8")
    s = Settings(str(p))
    assert s.get_intent_clarify_threshold() == 0.55


def test_clarify_threshold_from_config(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(
        "intent:\n  confidence:\n    clarify_threshold: 0.42\n",
        encoding="utf-8",
    )
    s = Settings(str(p))
    assert s.get_intent_clarify_threshold() == 0.42
