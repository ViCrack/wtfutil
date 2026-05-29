"""
基础工具：仅依赖标准库，供各子模块安全导入，不引用任何 wtfutil 内部模块。
"""

import os
import sys
from pathlib import Path

__all__ = ['get_resource_dir', 'get_resource']


def get_resource_dir(basedir: str | None = None) -> str:
    """向上遍历目录树，找到第一个包含 resource 子目录的路径。"""
    if not basedir:
        basedir = sys._getframe(1).f_code.co_filename
    current_dir = getattr(sys, '_MEIPASS', os.path.dirname(basedir))

    while True:
        resource_folder = os.path.join(current_dir, "resource")
        if os.path.exists(resource_folder) and os.path.isdir(resource_folder):
            break
        if len(current_dir) <= 3:
            break
        current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

    return resource_folder


def get_resource(filename: str) -> str | None:
    """按优先级查找资源文件：当前路径 → resource 子目录 → 用户家目录。"""
    if Path(filename).exists():
        return filename
    resource_path = get_resource_dir(sys._getframe(1).f_code.co_filename) + "/" + filename
    if Path(resource_path).exists():
        return str(Path(resource_path).absolute())
    if Path('~/' + filename).expanduser().exists():
        return str(Path('~/' + filename).expanduser().absolute())
    return None
