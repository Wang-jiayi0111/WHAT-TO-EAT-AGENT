"""
T-027 配置单源与启动自检（IR-04 / §8）
====================================

**任务**：T-027  
**规格**：IR-04；规格 §8  
**开发记录**：`docs/dev_log.md` [DEV-033]

验收结论写入 **`docs/test_report.md`** [TR-041]。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from src.libs.base.settings import Settings
from src.libs.base.config_startup_check import (
    ensure_runtime_directories,
    run_startup_configuration_check,
    validate_startup_configuration,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_settings() -> Settings:
    return Settings(str(_repo_root() / "config" / "setting.yaml"))


def test_t027_settings_memory_summary_and_recipe_getters() -> None:
    """§8：`memory.summary` 与 `recipe.*` 可从默认 YAML 读出。"""
    s = _default_settings()
    assert s.get_memory_summary_window_size() >= 1
    assert s.get_memory_summary_compress_trigger() >= s.get_memory_summary_window_size()
    assert s.get_recipe_parser_version()
    gap = s.get_recipe_confidence_gap_ratio()
    ret_gap = s.get_retrieval_top2_relative_gap()
    assert gap is not None and abs(float(gap) - float(ret_gap)) < 1e-6


def test_t027_resolve_project_path_relative() -> None:
    """相对路径相对仓库根解析。"""
    s = _default_settings()
    p = s.resolve_project_path("./data/db")
    assert p.is_absolute()
    assert p.name == "db"


def test_t027_setting_yaml_retrieval_has_confidence_and_empty_search() -> None:
    """IR-04：避免重复 `retrieval:` 静默覆盖后丢失子键；合并后应同时含 confidence 与 empty_search。"""
    path = _repo_root() / "config" / "setting.yaml"
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    ret = data.get("retrieval") or {}
    assert isinstance(ret.get("confidence"), dict)
    assert ret["confidence"].get("top2_relative_gap") is not None
    assert isinstance(ret.get("empty_search"), dict)


def test_t027_validate_default_config_no_errors() -> None:
    """仓库默认 `setting.yaml` 应通过 error 级校验（可有 warning，如未注入 API Key）。"""
    s = _default_settings()
    errors, _warnings = validate_startup_configuration(s)
    assert not errors


def test_t027_run_startup_check_succeeds() -> None:
    """`run_startup_configuration_check` 对默认配置返回 True。"""
    assert run_startup_configuration_check(_default_settings()) is True


def test_t027_validate_errors_missing_databases() -> None:
    """缺 `databases` → errors。"""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    try:
        minimal = {
            "household": {"default_id": "u"},
            "paths": {"db_dir": "./data/db"},
            "retrieval": {"confidence": {"top2_relative_gap": 0.1}, "empty_search": {}},
        }
        Path(path).write_text(yaml.dump(minimal, allow_unicode=True), encoding="utf-8")
        s = Settings(path)
        errors, _ = validate_startup_configuration(s)
        assert any("databases" in e for e in errors)
    finally:
        os.unlink(path)


def test_t027_validate_error_clarify_threshold_range() -> None:
    """clarify_threshold 超出 [0,1] → error。"""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    try:
        cfg = {
            "household": {"default_id": "u"},
            "paths": {"db_dir": "./data/db"},
            "databases": {"user_profiles": "a.db", "inventory": "b.db"},
            "retrieval": {"confidence": {"top2_relative_gap": 0.1}, "empty_search": {}},
            "intent": {"confidence": {"clarify_threshold": 2.0}},
        }
        Path(path).write_text(yaml.dump(cfg, allow_unicode=True), encoding="utf-8")
        s = Settings(path)
        errors, _ = validate_startup_configuration(s)
        assert any("clarify_threshold" in e for e in errors)
    finally:
        os.unlink(path)


def test_t027_validate_warning_gap_ratio_mismatch() -> None:
    """`recipe.confidence.gap_ratio` 与 `retrieval.confidence.top2_relative_gap` 不一致 → warning。"""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    try:
        cfg = {
            "household": {"default_id": "u"},
            "paths": {"db_dir": "./data/db"},
            "databases": {"user_profiles": "a.db", "inventory": "b.db"},
            "retrieval": {"confidence": {"top2_relative_gap": 0.15}, "empty_search": {}},
            "recipe": {"parser_version": "x", "confidence": {"gap_ratio": 0.99}},
        }
        Path(path).write_text(yaml.dump(cfg, allow_unicode=True), encoding="utf-8")
        s = Settings(path)
        _errors, warnings = validate_startup_configuration(s)
        assert any("gap_ratio" in w and "top2_relative_gap" in w for w in warnings)
    finally:
        os.unlink(path)


def test_t027_ensure_runtime_directories_creates_paths(tmp_path: Path) -> None:
    """`ensure_runtime_directories` 创建 `paths.*` 与向量库目录（绝对路径，避免依赖 project_root）。"""
    cfg_path = tmp_path / "setting.yaml"
    abs_data = str(tmp_path / "abs_data")
    cfg = {
        "household": {"default_id": "u"},
        "paths": {
            "data_dir": abs_data,
            "db_dir": abs_data + "/db",
            "log_dir": abs_data + "/logs",
            "recipes_dir": abs_data + "/recipes",
        },
        "databases": {"user_profiles": "a.db", "inventory": "b.db"},
        "vector_store": {"persist_path": abs_data + "/chroma"},
        "retrieval": {"confidence": {"top2_relative_gap": 0.1}, "empty_search": {}},
    }
    cfg_path.write_text(yaml.dump(cfg, allow_unicode=True), encoding="utf-8")
    s = Settings(str(cfg_path))
    ensure_runtime_directories(s)
    assert Path(abs_data).is_dir()
    assert (Path(abs_data) / "db").is_dir()
    assert (Path(abs_data) / "chroma").is_dir()
