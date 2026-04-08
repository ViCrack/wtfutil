#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
pykill - 根据脚本名或命令行模式终止 Python 进程的命令行工具

用法示例：
    pykill myscript.py                    # 按脚本路径终止（支持相对/绝对路径）
    pykill C:\\path\\to\\myscript.py       # 绝对路径精确匹配
    pykill -c "worker --queue"            # 模糊匹配命令行子串
    pykill -f myscript.py                 # 仅查找 PID，不终止
    pykill -n myscript.py                 # 模拟运行，显示将要终止的进程
"""

import argparse
import sys

from .procutil import (
    find_python_processes_by_script,
    find_python_processes_by_cmdline,
    kill_python_processes_by_script,
    kill_python_processes_by_cmdline,
)


def _print_processes(pids: list, target: str, mode: str) -> None:
    if not pids:
        print(f"[pykill] 未找到匹配的 Python 进程: {target!r} (模式={mode})")
    else:
        print(f"[pykill] 找到 {len(pids)} 个匹配进程 (模式={mode}):")
        for pid in pids:
            print(f"  PID {pid}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pykill",
        description="根据脚本名或命令行模式终止 Python 进程（支持 python/pythonw）",
    )
    parser.add_argument(
        "target",
        help="脚本路径（默认）或命令行匹配模式（配合 -c 使用）",
    )
    parser.add_argument(
        "-c", "--cmdline",
        action="store_true",
        default=False,
        help="使用命令行子串模糊匹配模式，而非脚本路径匹配",
    )
    parser.add_argument(
        "-f", "--find",
        action="store_true",
        default=False,
        help="仅查找并显示匹配的进程 PID，不执行终止操作",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="模拟运行：显示将要终止的进程，但不实际终止",
    )

    args = parser.parse_args()

    mode = "cmdline" if args.cmdline else "script"

    if args.cmdline:
        pids = find_python_processes_by_cmdline(args.target)
    else:
        pids = find_python_processes_by_script(args.target)

    if args.find or args.dry_run:
        _print_processes(pids, args.target, mode)
        if args.dry_run and pids:
            print("[pykill] 模拟运行，未实际终止任何进程。")
        return 0 if pids else 1

    if not pids:
        print(f"[pykill] 未找到匹配的 Python 进程: {args.target!r} (模式={mode})")
        return 1

    print(f"[pykill] 正在终止 {len(pids)} 个进程 (模式={mode}):")
    for pid in pids:
        print(f"  PID {pid}")

    if args.cmdline:
        success = kill_python_processes_by_cmdline(args.target)
    else:
        success = kill_python_processes_by_script(args.target)

    if success:
        print("[pykill] 完成。")
        return 0
    else:
        print("[pykill] 终止失败（进程可能已退出或权限不足）。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
