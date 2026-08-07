"""资源路径解析的私有基础层，仅依赖 Python 标准库。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_resource_directory_from_anchor(anchor_path: Path) -> Path | None:
    """沿单个锚点的父目录查找现有 ``resource`` 目录。"""
    current_directory = anchor_path if anchor_path.is_dir() else anchor_path.parent

    while True:
        resource_directory = current_directory / "resource"
        if resource_directory.is_dir():
            return resource_directory

        parent_directory = current_directory.parent
        if parent_directory == current_directory:
            return None
        current_directory = parent_directory


def find_resource_directory(anchor_path: str | Path) -> Path:
    """从锚点路径向上查找 ``resource`` 目录。

    找不到现有目录时返回文件系统根目录下的候选路径，以保持旧版
    ``get_resource_dir`` 的返回约定。调用方在读取文件前仍应检查其存在性。
    """
    frozen_base_path = getattr(sys, "_MEIPASS", None)
    if frozen_base_path:
        frozen_anchor = Path(frozen_base_path).resolve()
        return (
            _find_resource_directory_from_anchor(frozen_anchor)
            or Path(frozen_anchor.anchor) / "resource"
        )

    expanded_anchor = Path(anchor_path).expanduser()
    lexical_anchor = Path(os.path.abspath(expanded_anchor))
    resolved_anchor = expanded_anchor.resolve()
    for candidate_anchor in dict.fromkeys((lexical_anchor, resolved_anchor)):
        resource_directory = _find_resource_directory_from_anchor(candidate_anchor)
        if resource_directory is not None:
            return resource_directory

    return Path(lexical_anchor.anchor) / "resource"


def resolve_resource_path(
    filename: str | Path,
    *,
    anchor_path: str | Path,
) -> str | None:
    """按当前路径、项目资源目录、用户家目录的顺序解析资源文件。"""
    requested_path = Path(filename)
    if requested_path.exists():
        return str(filename)

    resource_path = find_resource_directory(anchor_path) / requested_path
    if resource_path.exists():
        return str(resource_path.absolute())

    home_path = Path.home() / requested_path
    if home_path.exists():
        return str(home_path.absolute())
    return None
