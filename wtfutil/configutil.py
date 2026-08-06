"""
wtfconfig.ini 统一加载与热更新。

优先级：内置 defaults ← ini 段 ← 环境变量（最高）。
热加载：按 ini 路径 + mtime 缓存整文件；ensure_section 仅在首次或 mtime 变化时写回目标 dict。
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from configobj import ConfigObj

from ._base import get_resource

_WTFCONFIG_NAME = "wtfconfig.ini"

# 整文件缓存
_cached_path: str | None = None
_cached_mtime: float | None = None
_cached_cfg: ConfigObj | None = None
_file_loaded: bool = False  # 是否已尝试加载过（含文件不存在）

# ensure_section：记录 (id(target), section) -> 已应用的 (path, mtime)；mtime 用 None 表示无文件
_applied: dict[tuple[int, str], tuple[str | None, float | None]] = {}


def get_wtfconfig_path() -> str | None:
    """解析 wtfconfig.ini：当前目录 → resource/ → ~/"""
    return get_resource(_WTFCONFIG_NAME)


def reload_wtfconfig() -> None:
    """强制丢掉文件缓存与 ensure 应用记录，下次 merge/ensure 重读磁盘。"""
    global _cached_path, _cached_mtime, _cached_cfg, _file_loaded
    _cached_path = None
    _cached_mtime = None
    _cached_cfg = None
    _file_loaded = False
    _applied.clear()


def _stat_mtime(path: str | None) -> float | None:
    if not path:
        return None
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


def load_ini_file(*, force_reload: bool = False) -> ConfigObj | None:
    """带 mtime 缓存的整文件解析；文件不存在返回 None。"""
    global _cached_path, _cached_mtime, _cached_cfg, _file_loaded

    path = get_wtfconfig_path()
    mtime = _stat_mtime(path) if path and Path(path).exists() else None

    if not force_reload and _file_loaded and path == _cached_path and mtime == _cached_mtime:
        return _cached_cfg

    _file_loaded = True
    _cached_path = path
    _cached_mtime = mtime

    if not path or mtime is None:
        _cached_cfg = None
        return None

    _cached_cfg = ConfigObj(path, encoding="UTF-8")
    return _cached_cfg


def _current_signature() -> tuple[str | None, float | None]:
    """当前磁盘上的 (path, mtime)，不强制重读 ConfigObj。"""
    path = get_wtfconfig_path()
    if not path or not Path(path).exists():
        return None, None
    return path, _stat_mtime(path)


def merge_section(
    defaults: Mapping[str, Any],
    section: str,
    *,
    uppercase_keys: bool = False,
    env_keys: Iterable[str] | None = None,
    env_map: Mapping[str, str] | None = None,
    force_reload: bool = False,
) -> dict[str, Any]:
    """
    返回新 dict：copy(defaults) ← [section] ← env。不修改调用方。

    :param uppercase_keys: ini 段内键转为大写后写入
    :param env_keys: 要检查的环境变量名；默认取 defaults 的键
    :param env_map: config 键 → 环境变量名（如 BASE_URL → MEMSHELL_BASE_URL）
    """
    result = copy.deepcopy(dict(defaults))
    cfg = load_ini_file(force_reload=force_reload)

    if cfg is not None and section in cfg:
        for key, value in cfg[section].items():
            out_key = key.upper() if uppercase_keys else key
            result[out_key] = value if not isinstance(value, (list, dict)) else value

    # 环境变量覆盖
    keys_to_check = list(env_keys) if env_keys is not None else list(result.keys())
    env_map = dict(env_map or {})

    for config_key in keys_to_check:
        env_name = env_map.get(config_key, config_key)
        env_val = os.getenv(env_name)
        if env_val is not None and env_val != "":
            result[config_key] = env_val

    # env_map 中仅出现在 map 的键也要检查（defaults 可能已有）
    for config_key, env_name in env_map.items():
        if config_key in keys_to_check:
            continue
        env_val = os.getenv(env_name)
        if env_val is not None and env_val != "":
            result[config_key] = env_val

    return result


def ensure_section(
    target: dict,
    defaults: Mapping[str, Any],
    section: str,
    *,
    uppercase_keys: bool = False,
    env_map: Mapping[str, str] | None = None,
    force_reload: bool = False,
) -> bool:
    """
    若首次或 ini mtime 变化（或 force_reload）：用 merge_section 结果更新 target，返回 True。
    否则不动 target（保留运行时临时改写），返回 False。
    """
    key = (id(target), section)
    sig = _current_signature()

    if force_reload:
        reload_wtfconfig()
        sig = _current_signature()

    if not force_reload and key in _applied and _applied[key] == sig:
        # 签名未变：仍可能需要确认缓存与磁盘一致（path 切换等已含在 sig）
        return False

    merged = merge_section(
        defaults,
        section,
        uppercase_keys=uppercase_keys,
        env_map=env_map,
        force_reload=force_reload,
    )
    target.clear()
    target.update(merged)
    _applied[key] = sig
    return True


__all__ = [
    "get_wtfconfig_path",
    "load_ini_file",
    "merge_section",
    "ensure_section",
    "reload_wtfconfig",
]
