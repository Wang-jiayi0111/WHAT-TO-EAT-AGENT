import os
import yaml
from pathlib import Path
from typing import Any, Dict

class Settings:
    def __init__(self, config_path: str = None):
        if config_path is None:
            root_dir = Path(__file__).parents[3] 
            config_path = root_dir / "config" / "setting.yaml"
        
        self._config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                content = os.path.expandvars(content)
                self._config = yaml.safe_load(content) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with an optional default."""
        return self._config.get(key, default)

    def get_intent_clarify_threshold(self, default: float = 0.55) -> float:
        """
        `intent.confidence.clarify_threshold`（规格 §8）。
        低于该值的综合置信度 → `needs_clarification`，且不映射写库类任务（FR-03；§11.6）。
        """
        intent = self._config.get("intent")
        if not isinstance(intent, dict):
            return default
        conf = intent.get("confidence")
        if not isinstance(conf, dict):
            return default
        v = conf.get("clarify_threshold")
        if v is None:
            return default
        return float(v)