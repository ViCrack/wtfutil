#!/usr/bin/env python3
from __future__ import annotations

import os
import re

import psutil

_PYTHON_NAME_RE = re.compile(r"^pythonw?(\d+(?:\.\d+)*)?(?:\.exe)?$", re.IGNORECASE)


def _require_non_empty_text(value: str, parameter_name: str) -> str:
    """校验用于进程匹配的文本参数，避免空值匹配全部进程。"""
    if not isinstance(value, str):
        raise TypeError(f"{parameter_name} must be a string")
    if not value.strip():
        raise ValueError(f"{parameter_name} must not be empty")
    return value


def _require_windows() -> None:
    if os.name != "nt":
        raise OSError("process suspend/resume is only supported on Windows")


def _suspend_threads(thread_ids: list[int]) -> bool:
    _require_windows()
    from ._winproc import suspend_threads

    return suspend_threads(thread_ids)


def _resume_threads(thread_ids: list[int]) -> bool:
    _require_windows()
    from ._winproc import resume_threads

    return resume_threads(thread_ids)


def find_process_by_name(process_name: str) -> int | None:
    """
    根据进程名称查找进程 PID

    Args:
        process_name: 进程名称（如 'notepad.exe'）

    Returns:
        进程 PID，如果未找到则返回 None
    """
    process_name_lower = _require_non_empty_text(
        process_name,
        "process_name",
    ).lower()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if (proc.info.get('name') or '').lower() == process_name_lower:
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _get_thread_ids(pid: int) -> list[int]:
    """
    获取进程的所有线程ID

    Args:
        pid: 进程 PID

    Returns:
        线程ID列表
    """
    try:
        process = psutil.Process(pid)
        return [t.id for t in process.threads()]
    except (OSError, psutil.Error):
        return []


def suspend_process_by_pid(pid: int) -> bool:
    """
    根据进程 PID 挂起进程的所有线程

    Args:
        pid: 进程 PID

    Returns:
        如果成功挂起至少一个线程则返回 True，否则返回 False

    Raises:
        OSError: 非 Windows 平台
    """
    _require_windows()
    if pid == os.getpid():
        raise ValueError("cannot suspend the current process")
    try:
        thread_ids = _get_thread_ids(pid)
        return _suspend_threads(thread_ids) if thread_ids else False
    except (OSError, psutil.Error):
        return False


def suspend_process(process_name: str) -> bool:
    """
    挂起进程的所有线程

    Args:
        process_name: 进程名称（如 'notepad.exe'）

    Returns:
        如果成功挂起至少一个线程则返回 True，否则返回 False

    Raises:
        OSError: 非 Windows 平台
    """
    _require_windows()
    pid = find_process_by_name(process_name)
    return suspend_process_by_pid(pid) if pid else False


def resume_process_by_pid(pid: int) -> bool:
    """
    根据进程 PID 恢复进程的所有线程，根据 ResumeThread 返回值循环恢复直到完全恢复

    Args:
        pid: 进程 PID

    Returns:
        如果成功恢复至少一个线程则返回 True，否则返回 False

    Raises:
        OSError: 非 Windows 平台
    """
    _require_windows()
    try:
        thread_ids = _get_thread_ids(pid)
        return _resume_threads(thread_ids) if thread_ids else False
    except (OSError, psutil.Error):
        return False


def resume_process(process_name: str) -> bool:
    """
    恢复进程的所有线程，根据 ResumeThread 返回值循环恢复直到完全恢复

    Args:
        process_name: 进程名称（如 'notepad.exe'）

    Returns:
        如果成功恢复至少一个线程则返回 True，否则返回 False

    Raises:
        OSError: 非 Windows 平台
    """
    _require_windows()
    pid = find_process_by_name(process_name)
    return resume_process_by_pid(pid) if pid else False


def _is_python_process(proc_name: str) -> bool:
    """匹配 python / python3 / python3.13 / pythonw.exe 等跨平台进程名。"""
    return bool(_PYTHON_NAME_RE.match(proc_name or ""))


def _get_script_from_cmdline(cmdline: list) -> str | None:
    """
    从命令行参数中提取脚本路径；``-m`` 和 ``-c`` 启动方式不视为脚本。
    """
    arguments = cmdline[1:]
    argument_index = 0
    options_with_separate_values = {"-W", "-X", "--check-hash-based-pycs"}

    while argument_index < len(arguments):
        argument = arguments[argument_index]
        if argument in {"-m", "-c"} or argument.startswith(("-m", "-c")):
            return None
        if argument == "--":
            next_index = argument_index + 1
            return arguments[next_index] if next_index < len(arguments) else None
        if argument.startswith("-"):
            if argument in options_with_separate_values:
                argument_index += 2
            else:
                argument_index += 1
            continue
        return argument
    return None


def _resolve_script_abs(script_arg: str, proc_cwd: str) -> str:
    """
    将脚本路径解析为绝对路径：
    - 若已是绝对路径，直接规范化
    - 若是相对路径，基于进程 cwd 解析
    """
    try:
        if os.path.isabs(script_arg):
            return os.path.normcase(os.path.normpath(script_arg))
        if proc_cwd:
            return os.path.normcase(os.path.normpath(os.path.join(proc_cwd, script_arg)))
    except (ValueError, TypeError):
        pass
    return os.path.normcase(script_arg)


def find_python_processes_by_script(script_name: str) -> list[int]:
    """
    根据 Python 脚本名（支持相对/绝对路径）查找所有匹配的 Python 进程 PID 列表。

    匹配优先级：
    1. 绝对路径精确匹配（遵循当前操作系统的路径大小写规则）
    2. 仅文件名匹配（未找到精确路径时回退）

    同时支持 python.exe / pythonw.exe 进程。

    Args:
        script_name: 脚本路径，可以是相对路径或绝对路径

    Returns:
        匹配的进程 PID 列表
    """
    script_name = _require_non_empty_text(script_name, "script_name")
    target_abs = os.path.normcase(os.path.abspath(script_name))
    target_basename = os.path.normcase(os.path.basename(script_name))
    allows_basename_fallback = not (
        os.path.isabs(script_name)
        or os.path.dirname(script_name)
        or "/" in script_name
        or "\\" in script_name
    )

    exact_matches: list[int] = []
    basename_matches: list[int] = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            info = proc.info
            if not _is_python_process(info.get('name') or ''):
                continue

            cmdline = info.get('cmdline') or []
            script_arg = _get_script_from_cmdline(cmdline)
            if not script_arg:
                continue

            proc_cwd = info.get('cwd') or ''
            script_abs = _resolve_script_abs(script_arg, proc_cwd)

            if script_abs == target_abs:
                exact_matches.append(info['pid'])
            elif os.path.normcase(os.path.basename(script_arg)) == target_basename:
                basename_matches.append(info['pid'])

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 优先返回绝对路径精确匹配，无精确匹配时返回文件名模糊匹配
    if exact_matches:
        return exact_matches
    return basename_matches if allows_basename_fallback else []


def find_python_process_by_script(script_name: str) -> int | None:
    """
    根据 Python 脚本名查找第一个匹配的进程 PID。

    Args:
        script_name: 脚本路径，可以是相对路径或绝对路径

    Returns:
        第一个匹配的进程 PID，未找到返回 None
    """
    pids = find_python_processes_by_script(script_name)
    return pids[0] if pids else None


def kill_python_processes_by_script(script_name: str) -> bool:
    """
    根据 Python 脚本名终止所有匹配的 Python 进程。

    Args:
        script_name: 脚本路径，可以是相对路径或绝对路径

    Returns:
        若成功终止至少一个进程则返回 True，否则返回 False
    """
    pids = find_python_processes_by_script(script_name)
    if not pids:
        return False

    current_pid = os.getpid()
    success = False
    for pid in pids:
        if pid == current_pid:
            continue
        try:
            proc = psutil.Process(pid)
            proc.kill()
            success = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return success


def find_python_processes_by_cmdline(pattern: str) -> list[int]:
    """
    对 Python 进程的完整命令行字符串进行模糊匹配，返回所有匹配的 PID 列表。

    匹配方式：将 pattern 与进程命令行拼接字符串进行大小写不敏感的子串搜索。

    Args:
        pattern: 要匹配的命令行子串（如脚本名、参数等）

    Returns:
        匹配的进程 PID 列表
    """
    pattern_lower = _require_non_empty_text(pattern, "pattern").lower()
    results: list[int] = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            info = proc.info
            if not _is_python_process(info.get('name') or ''):
                continue

            cmdline = info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline).lower()
            if pattern_lower in cmdline_str:
                results.append(info['pid'])

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return results


def _build_proc_detail(info: dict) -> dict:
    """从 psutil 进程信息构建展示用的详情字典"""
    cmdline = info.get('cmdline') or []
    script_arg = _get_script_from_cmdline(cmdline)
    proc_cwd = info.get('cwd') or ''
    script_abs = _resolve_script_abs(script_arg, proc_cwd) if script_arg else ''
    return {
        'pid': info.get('pid'),
        'name': info.get('name') or '',
        'script': script_arg or '',
        'script_abs': script_abs,
        'cwd': proc_cwd,
        'cmdline': ' '.join(cmdline),
    }


def find_python_process_details_by_script(script_name: str) -> list[dict]:
    """
    根据 Python 脚本名查找所有匹配进程，返回详情字典列表。

    每个字典包含：pid, name, script, script_abs, cwd, cmdline

    Args:
        script_name: 脚本路径，可以是相对路径或绝对路径

    Returns:
        匹配的进程详情列表
    """
    script_name = _require_non_empty_text(script_name, "script_name")
    target_abs = os.path.normcase(os.path.abspath(script_name))
    target_basename = os.path.normcase(os.path.basename(script_name))
    allows_basename_fallback = not (
        os.path.isabs(script_name)
        or os.path.dirname(script_name)
        or "/" in script_name
        or "\\" in script_name
    )

    exact_matches: list[dict] = []
    basename_matches: list[dict] = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            info = proc.info
            if not _is_python_process(info.get('name') or ''):
                continue

            cmdline = info.get('cmdline') or []
            script_arg = _get_script_from_cmdline(cmdline)
            if not script_arg:
                continue

            proc_cwd = info.get('cwd') or ''
            script_abs = _resolve_script_abs(script_arg, proc_cwd)

            if script_abs == target_abs:
                exact_matches.append(_build_proc_detail(info))
            elif os.path.normcase(os.path.basename(script_arg)) == target_basename:
                basename_matches.append(_build_proc_detail(info))

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if exact_matches:
        return exact_matches
    return basename_matches if allows_basename_fallback else []


def find_python_process_details_by_cmdline(pattern: str) -> list[dict]:
    """
    对 Python 进程命令行进行模糊匹配，返回详情字典列表。

    每个字典包含：pid, name, script, script_abs, cwd, cmdline

    Args:
        pattern: 要匹配的命令行子串

    Returns:
        匹配的进程详情列表
    """
    pattern_lower = _require_non_empty_text(pattern, "pattern").lower()
    results: list[dict] = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            info = proc.info
            if not _is_python_process(info.get('name') or ''):
                continue

            cmdline = info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline).lower()
            if pattern_lower in cmdline_str:
                results.append(_build_proc_detail(info))

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return results


def kill_python_processes_by_cmdline(pattern: str) -> bool:
    """
    对 Python 进程命令行进行模糊匹配，终止所有匹配的进程。

    Args:
        pattern: 要匹配的命令行子串

    Returns:
        若成功终止至少一个进程则返回 True，否则返回 False
    """
    pids = find_python_processes_by_cmdline(pattern)
    if not pids:
        return False

    current_pid = os.getpid()
    success = False
    for pid in pids:
        if pid == current_pid:
            continue
        try:
            proc = psutil.Process(pid)
            proc.kill()
            success = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return success


def list_all_python_process_details() -> list[dict]:
    """
    枚举系统中所有 Python 进程，返回详情字典列表。

    每个字典包含：pid, name, script, script_abs, cwd, cmdline

    Returns:
        所有 Python 进程的详情列表
    """
    results: list[dict] = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            info = proc.info
            if not _is_python_process(info.get('name') or ''):
                continue
            results.append(_build_proc_detail(info))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


__all__ = [
    'find_process_by_name',
    'find_python_process_by_script',
    'find_python_process_details_by_cmdline',
    'find_python_process_details_by_script',
    'find_python_processes_by_cmdline',
    'find_python_processes_by_script',
    'kill_python_processes_by_cmdline',
    'kill_python_processes_by_script',
    'list_all_python_process_details',
    'resume_process',
    'resume_process_by_pid',
    'suspend_process',
    'suspend_process_by_pid',
]
