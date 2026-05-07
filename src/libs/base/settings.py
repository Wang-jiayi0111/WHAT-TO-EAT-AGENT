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

    def get_scope_id(self, default: str = "default_user") -> str:
        """`household.default_id`（规格 §8 SCOPE_ID）。"""
        hh = self._config.get("household")
        if isinstance(hh, dict):
            did = hh.get("default_id")
            if did is not None and str(did).strip():
                return str(did).strip()
        return default

    def get_user_profiles_db_path(self) -> str:
        """SQLite 用户画像库路径（`paths.db_dir` + `databases.user_profiles`）。"""
        paths = self.get("paths") or {}
        db_dir = paths.get("db_dir") or "data/db"
        dbs = self.get("databases") or {}
        name = dbs.get("user_profiles") or "user_profiles.db"
        root_dir = Path(__file__).resolve().parents[3]
        return str(root_dir / db_dir / name)

    def get_short_term_ttl_days(self, default: int = 7) -> int:
        """`memory.short_term_ttl.default_days`（规格 §3.4；与 `DEFAULT_SHORT_TERM_TTL_DAYS` 对齐）。"""
        mem = self._config.get("memory")
        if not isinstance(mem, dict):
            return default
        st = mem.get("short_term_ttl")
        if not isinstance(st, dict):
            return default
        d = st.get("default_days")
        if d is None:
            return default
        try:
            return max(1, int(d))
        except (TypeError, ValueError):
            return default

    def should_purge_short_term_expired_on_turn(self, default: bool = True) -> bool:
        """每轮入口是否对 SQLite 短期表做物理清理（T-013）。"""
        mem = self._config.get("memory")
        if not isinstance(mem, dict):
            return default
        st = mem.get("short_term_ttl")
        if not isinstance(st, dict):
            return default
        v = st.get("purge_expired_on_turn")
        if v is None:
            return default
        return bool(v)