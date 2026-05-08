"""
启动配置自检（T-027 / IR-04）：单一 YAML 来源、`setting.yaml` 与规格 §8 关键键可读，
并在进程启动时创建必要目录，避免因重复键静默覆盖导致检索参数丢失。

校验结论通过 logging 输出；`errors` 非空时由调用方决定是否退出进程。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from .settings import Settings

logger = logging.getLogger(__name__)


def ensure_runtime_directories(settings: "Settings") -> None:
    """创建数据与日志目录（不存在则 mkdir -p）。"""
    paths = settings.get("paths") or {}
    if isinstance(paths, dict):
        for key in ("data_dir", "db_dir", "log_dir", "recipes_dir"):
            rel = paths.get(key)
            if rel:
                p = settings.resolve_project_path(str(rel))
                p.mkdir(parents=True, exist_ok=True)
                logger.debug("[Config] 目录就绪: %s (%s)", key, p)

    vs = settings.get("vector_store") or {}
    if isinstance(vs, dict):
        persist = vs.get("persist_path")
        if persist:
            settings.resolve_project_path(str(persist)).mkdir(parents=True, exist_ok=True)


def validate_startup_configuration(settings: "Settings") -> Tuple[List[str], List[str]]:
    """
    返回 (errors, warnings)。
    errors：缺必填键或类型明显非法（可能导致运行时逻辑错误）。
    warnings：可容忍偏差（例如 §8 文档键与实现键数值不一致）。
    """
    errors: List[str] = []
    warnings: List[str] = []

    sid = settings.get_scope_id()
    if not str(sid).strip():
        errors.append("household.default_id 不能为空（规格 §8 SCOPE_ID）")

    paths = settings.get("paths")
    if not isinstance(paths, dict):
        errors.append("配置缺少 `paths` 映射")
    else:
        db_dir = paths.get("db_dir")
        if not db_dir:
            warnings.append("paths.db_dir 未设置，将依赖代码内默认 data/db")

    dbs = settings.get("databases")
    if not isinstance(dbs, dict):
        errors.append("配置缺少 `databases` 映射（画像/库存库文件名）")
    else:
        if not dbs.get("inventory"):
            errors.append("databases.inventory 未配置")
        if not dbs.get("user_profiles"):
            errors.append("databases.user_profiles 未配置")

    intent = settings.get("intent")
    if isinstance(intent, dict):
        conf = intent.get("confidence")
        if isinstance(conf, dict):
            th = conf.get("clarify_threshold")
            if th is not None:
                try:
                    v = float(th)
                    if not 0.0 <= v <= 1.0:
                        errors.append("intent.confidence.clarify_threshold 应在 [0,1] 内")
                except (TypeError, ValueError):
                    errors.append("intent.confidence.clarify_threshold 必须为数字")

    inv = settings.get("inventory")
    if inv is not None and not isinstance(inv, dict):
        errors.append("`inventory` 段必须为映射（§6.5 / §8）")

    ret = settings.get("retrieval")
    if not isinstance(ret, dict):
        errors.append("缺少 `retrieval` 配置段（§5.1 置信阈与 FR-24 等）")
    else:
        rc = ret.get("confidence")
        if not isinstance(rc, dict) or rc.get("top2_relative_gap") is None:
            warnings.append(
                "retrieval.confidence.top2_relative_gap 未设置，将使用代码默认值 0.15"
            )
        if not isinstance(ret.get("empty_search"), dict):
            warnings.append("retrieval.empty_search 未配置，软重试次数将用默认值")

    mem = settings.get("memory")
    if isinstance(mem, dict):
        sm = mem.get("summary")
        if not isinstance(sm, dict):
            warnings.append("memory.summary 未配置，L2 窗口将使用代码内置默认")
        st = mem.get("short_term_ttl")
        if not isinstance(st, dict):
            warnings.append("memory.short_term_ttl 未配置，短期 TTL 将使用默认值")

    gap_doc = settings.get_recipe_confidence_gap_ratio()
    gap_impl = settings.get_retrieval_top2_relative_gap()
    if gap_doc is not None and abs(float(gap_doc) - float(gap_impl)) > 1e-6:
        warnings.append(
            "recipe.confidence.gap_ratio 与 retrieval.confidence.top2_relative_gap 不一致（IR-04：建议统一）"
        )

    llm = settings.get("llm") or {}
    if isinstance(llm, dict):
        key = llm.get("api_key")
        if isinstance(key, str) and key.strip().startswith("${") and key.endswith("}"):
            import os

            var = key.strip("${}")
            if not os.environ.get(var):
                warnings.append(
                    f"环境变量 {var} 未设置，LLM 调用可能失败（部署时请注入密钥）"
                )

    return errors, warnings


def run_startup_configuration_check(settings: "Settings") -> bool:
    """
    确保目录、运行校验并写日志。
    返回 True 表示无 error 级问题；False 表示存在 errors（调用方可 sys.exit(1)）。
    """
    ensure_runtime_directories(settings)
    errors, warnings = validate_startup_configuration(settings)
    for w in warnings:
        logger.warning("[启动自检] %s", w)
    for e in errors:
        logger.error("[启动自检] %s", e)
    if not errors:
        logger.info("[启动自检] 配置检查通过（warnings=%d）", len(warnings))
    return not errors
