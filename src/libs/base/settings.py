import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

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
        低于该值的综合置信度 → `needs_clarification`，且不映射写库类任务（FR-03；§12.6）。
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

    def get_inventory_db_path(self) -> str:
        """SQLite 库存库路径（规格 §6.2、§8；与画像库同 `paths.db_dir` 根）。"""
        paths = self.get("paths") or {}
        db_dir = paths.get("db_dir") or "data/db"
        dbs = self.get("databases") or {}
        name = dbs.get("inventory") or "inventory.db"
        root_dir = Path(__file__).resolve().parents[3]
        return str(root_dir / db_dir / name)

    def get_inventory_restock_confirm_required(self, default: bool = True) -> bool:
        """`inventory.restock.confirm_required`（规格 §6.5.3）。"""
        inv = self._config.get("inventory")
        if not isinstance(inv, dict):
            return default
        rs = inv.get("restock")
        if not isinstance(rs, dict):
            return default
        v = rs.get("confirm_required")
        if v is None:
            return default
        return bool(v)

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

    def get_retrieval_top2_relative_gap(self, default: float = 0.15) -> float:
        """规格 §5.1：`(s1-s2)/(s2+ε) > gap` 时高置信锁定 top1。"""
        ret = self._config.get("retrieval")
        if not isinstance(ret, dict):
            return default
        conf = ret.get("confidence")
        if not isinstance(conf, dict):
            return default
        v = conf.get("top2_relative_gap")
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def get_ambiguity_max_candidates(self, default: int = 6) -> int:
        """FR-22 / §5.1：歧义澄清展示的候选上限。"""
        ret = self._config.get("retrieval")
        if not isinstance(ret, dict):
            return default
        amb = ret.get("ambiguity")
        if not isinstance(amb, dict):
            return default
        v = amb.get("max_candidates")
        if v is None:
            return default
        try:
            return max(2, min(20, int(v)))
        except (TypeError, ValueError):
            return default

    def get_recipe_search_soft_retry_max(self, default: int = 1) -> int:
        """FR-24：`retrieval.empty_search.soft_retry_max`，首轮空结果后的放宽软约束重试次数。"""
        ret = self._config.get("retrieval")
        if not isinstance(ret, dict):
            return default
        es = ret.get("empty_search")
        if not isinstance(es, dict):
            return default
        v = es.get("soft_retry_max")
        if v is None:
            return default
        try:
            return max(0, min(5, int(v)))
        except (TypeError, ValueError):
            return default

    def get_memory_summary_window_size(self, default: int = 4) -> int:
        """`memory.summary.window_size`（规格 §8；L2 热窗口）。"""
        mem = self._config.get("memory")
        if not isinstance(mem, dict):
            return default
        sm = mem.get("summary")
        if not isinstance(sm, dict):
            return default
        v = sm.get("window_size")
        if v is None:
            return default
        try:
            return max(1, min(64, int(v)))
        except (TypeError, ValueError):
            return default

    def get_memory_summary_compress_trigger(self, default: int = 8) -> int:
        """`memory.summary.compress_trigger`（规格 §8；消息条数超过则触发压缩）。"""
        mem = self._config.get("memory")
        if not isinstance(mem, dict):
            return default
        sm = mem.get("summary")
        if not isinstance(sm, dict):
            return default
        v = sm.get("compress_trigger")
        if v is None:
            return default
        try:
            return max(2, min(256, int(v)))
        except (TypeError, ValueError):
            return default

    def get_recipe_parser_version(self, default: str = "llm_structured_v1") -> str:
        """`recipe.parser_version`（规格 §8）。"""
        rp = self._config.get("recipe")
        if not isinstance(rp, dict):
            return default
        v = rp.get("parser_version")
        if v is None or not str(v).strip():
            return default
        return str(v).strip()

    def get_recipe_confidence_gap_ratio(self, default: Optional[float] = None) -> Optional[float]:
        """
        `recipe.confidence.gap_ratio`（规格 §8 文档键名）。
        实现上与 `retrieval.confidence.top2_relative_gap` 应对齐；默认 None 表示未单独配置。
        """
        rp = self._config.get("recipe")
        if not isinstance(rp, dict):
            return default
        conf = rp.get("confidence")
        if not isinstance(conf, dict):
            return default
        v = conf.get("gap_ratio")
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def project_root(self) -> Path:
        """仓库根目录（解析 paths.* 相对路径）。"""
        return Path(__file__).resolve().parents[3]

    def resolve_project_path(self, relative: str) -> Path:
        """将配置中的相对路径解析为绝对路径。"""
        rel = (relative or "").strip()
        if not rel:
            return self.project_root()
        p = Path(rel.replace("\\", "/"))
        if p.is_absolute():
            return p
        return (self.project_root() / p).resolve()

    def observability_enabled(self, default: bool = True) -> bool:
        """`observability.enabled` 总开关。"""
        obs = self._config.get("observability")
        if not isinstance(obs, dict):
            return default
        v = obs.get("enabled")
        if v is None:
            return default
        return bool(v)

    def observability_structured_agent_log(self, default: bool = True) -> bool:
        """NFR-06：节点结构化日志。"""
        if not self.observability_enabled():
            return False
        obs = self._config.get("observability")
        if not isinstance(obs, dict):
            return default
        v = obs.get("structured_agent_log")
        if v is None:
            return default
        return bool(v)

    def observability_memory_metrics_log(self, default: bool = True) -> bool:
        """NFR-07：记忆指标日志。"""
        if not self.observability_enabled():
            return False
        obs = self._config.get("observability")
        if not isinstance(obs, dict):
            return default
        v = obs.get("memory_metrics_log")
        if v is None:
            return default
        return bool(v)
