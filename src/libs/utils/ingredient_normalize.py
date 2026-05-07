"""
食材名规范化（规格 §7.5 v1）：strip、全角数字字母转半角、可选别名表。

R 与 I 比对前应双方过 normalize_name；补货解析后写入库存键也使用同一函数。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict

import yaml

_FW_DIGIT = str.maketrans("０１２３４５６７８９", "0123456789")


@lru_cache(maxsize=1)
def _load_alias_map() -> Dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    path = root / "config" / "ingredient_aliases.yaml"
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if k is None or v is None:
            continue
        key = str(k).strip()
        val = str(v).strip()
        if key and val:
            out[key] = val
    return out


def normalize_name(s: str) -> str:
    """
    §7.5：strip → 全角数字转半角 → 别名表 canonical（若配置存在）。
    不做简繁转换（除非未来配置开启）。
    """
    if s is None:
        return ""
    t = str(s).strip().translate(_FW_DIGIT)
    if not t:
        return ""
    aliases = _load_alias_map()
    return aliases.get(t, t)
