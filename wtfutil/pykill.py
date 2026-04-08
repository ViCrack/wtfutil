#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
pykill - 根据脚本名或命令行模式终止 Python 进程的命令行工具

用法示例：
    pykill myscript.py                    # 按脚本路径终止（支持相对/绝对路径）
    pykill C:\\path\\to\\myscript.py       # 绝对路径精确匹配
    pykill -c "worker --queue"            # 模糊匹配命令行子串
    pykill -f myscript.py                 # 仅查找进程，不终止
    pykill -n myscript.py                 # 模拟运行，显示将要终止的进程
"""

import argparse
import sys

import psutil
from rich.console import Console
from rich.table import Table
from rich import box

from .procutil import (
    find_python_process_details_by_script,
    find_python_process_details_by_cmdline,
)

console = Console()


def _build_table(details: list, title: str) -> Table:
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_lines=True,
        highlight=True,
        title_style="bold cyan",
    )
    table.add_column("PID", style="bold yellow", justify="right", no_wrap=True)
    table.add_column("进程名", style="green", no_wrap=True)
    table.add_column("脚本", style="cyan")
    table.add_column("绝对路径", style="blue")
    table.add_column("工作目录 (cwd)", style="magenta")
    table.add_column("完整命令行", style="white", overflow="fold")

    for d in details:
        table.add_row(
            str(d.get("pid", "")),
            d.get("name", ""),
            d.get("script", ""),
            d.get("script_abs", ""),
            d.get("cwd", ""),
            d.get("cmdline", ""),
        )
    return table


def _kill_pids(pids: list) -> bool:
    success = False
    for pid in pids:
        try:
            psutil.Process(pid).kill()
            console.print(f"  [green]✓[/green] PID {pid} 已终止")
            success = True
        except psutil.NoSuchProcess:
            console.print(f"  [yellow]⚠[/yellow] PID {pid} 进程不存在（已退出）")
        except psutil.AccessDenied:
            console.print(f"  [red]✗[/red] PID {pid} 权限不足，无法终止")
    return success


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
        help="使用命令行子串模糊匹配，而非脚本路径匹配",
    )
    parser.add_argument(
        "-f", "--find",
        action="store_true",
        default=False,
        help="仅查找并显示匹配进程，不执行终止",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="模拟运行：显示将要终止的进程，但不实际终止",
    )

    args = parser.parse_args()
    mode = "cmdline 模糊匹配" if args.cmdline else "脚本路径匹配"

    if args.cmdline:
        details = find_python_process_details_by_cmdline(args.target)
    else:
        details = find_python_process_details_by_script(args.target)

    if not details:
        console.print(
            f"[bold red]未找到匹配的 Python 进程[/bold red]  "
            f"目标: [yellow]{args.target!r}[/yellow]  模式: {mode}"
        )
        return 1

    table = _build_table(
        details,
        title=f"匹配到 {len(details)} 个进程  [{mode}]  目标: {args.target!r}",
    )
    console.print(table)

    if args.find:
        return 0

    if args.dry_run:
        console.print("[bold yellow]模拟运行，未实际终止任何进程。[/bold yellow]")
        return 0

    console.print(f"\n[bold]正在终止 {len(details)} 个进程...[/bold]")
    pids = [d["pid"] for d in details]
    success = _kill_pids(pids)

    if success:
        console.print("[bold green]完成。[/bold green]")
        return 0
    else:
        console.print("[bold red]所有进程终止失败（权限不足或已退出）。[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
