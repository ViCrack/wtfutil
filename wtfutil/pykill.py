#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
pykill - 根据脚本名或命令行模式终止 Python 进程的命令行工具

用法示例：
    pykill                                # 列出所有 Python 进程
    pykill myscript.py                    # 列出匹配并直接终止
    pykill -c "worker --queue"            # 按命令行子串匹配
    pykill -l                             # 仅列出所有 Python 进程（同无参数）
    pykill myscript.py -l                 # 仅列出匹配进程，不终止
"""

import argparse
import os
import sys

import psutil
import questionary
from rich.console import Console
from rich.table import Table
from rich import box

from .procutil import (
    find_python_process_details_by_script,
    find_python_process_details_by_cmdline,
    list_all_python_process_details,
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
        description="终止 Python 进程。不加参数时列出所有 Python 进程。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  pykill                   列出所有 Python 进程\n"
            "  pykill myscript.py       匹配并直接终止进程\n"
            "  pykill myscript.py -l    仅列出匹配进程\n"
            "  pykill -c worker         按命令行子串匹配\n"
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        metavar="PATTERN",
        help="脚本路径或命令行匹配串（省略则列出所有 Python 进程）",
    )
    parser.add_argument(
        "-c", "--cmdline",
        action="store_true",
        help="按命令行子串匹配，而非脚本路径匹配",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        dest="list_only",
        help="仅列出匹配进程，不执行终止",
    )
    args = parser.parse_args()

    self_pid = os.getpid()

    # 无 target：列出所有 Python 进程，交互式多选后 kill
    if args.target is None:
        details = [d for d in list_all_python_process_details() if d.get("pid") != self_pid]
        if not details:
            console.print("[bold yellow]当前没有运行中的 Python 进程。[/bold yellow]")
            return 0
        table = _build_table(details, title=f"所有 Python 进程（共 {len(details)} 个）")
        console.print(table)

        if args.list_only:
            return 0

        choices = [
            questionary.Choice(
                title=f"[{d['pid']}] {d['script'] or d['name']}  {d['cmdline'][:60]}",
                value=d["pid"],
            )
            for d in details
        ]
        selected_pids = questionary.checkbox(
            "选择要 kill 的进程（空格选中，回车确认，Ctrl+C 取消）：",
            choices=choices,
        ).ask()

        if not selected_pids:
            console.print("[yellow]未选择任何进程，已取消。[/yellow]")
            return 0

        console.print(f"\n[bold]正在终止 {len(selected_pids)} 个进程...[/bold]")
        _kill_pids(selected_pids)
        console.print("[bold green]完成。[/bold green]")
        return 0

    # 有 target：按模式查找
    mode = "命令行匹配" if args.cmdline else "脚本路径匹配"
    if args.cmdline:
        details = [d for d in find_python_process_details_by_cmdline(args.target) if d.get("pid") != self_pid]
    else:
        details = [d for d in find_python_process_details_by_script(args.target) if d.get("pid") != self_pid]

    if not details:
        console.print(
            f"[bold red]未找到匹配的 Python 进程[/bold red]  "
            f"目标: [yellow]{args.target!r}[/yellow]  模式: {mode}"
        )
        return 1

    table = _build_table(
        details,
        title=f"匹配到 {len(details)} 个进程  [{mode}]  {args.target!r}",
    )
    console.print(table)

    if args.list_only:
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
