#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

import ctypes
import os
from typing import Optional, List

import psutil
import win32con

# Windows API 函数
kernel32 = ctypes.windll.kernel32


def find_process_by_name(process_name: str) -> Optional[int]:
    """
    根据进程名称查找进程 PID

    Args:
        process_name: 进程名称（如 'notepad.exe'）

    Returns:
        进程 PID，如果未找到则返回 None
    """
    process_name_lower = process_name.lower()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == process_name_lower:
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _get_thread_ids(pid: int) -> list:
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
    except Exception:
        return []


def _suspend_threads(thread_ids: list) -> bool:
    """
    挂起指定的线程列表

    Args:
        thread_ids: 线程ID列表

    Returns:
        如果成功挂起至少一个线程则返回 True，否则返回 False
    """
    for tid in thread_ids:
        try:
            hThread = kernel32.OpenThread(win32con.THREAD_SUSPEND_RESUME, False, tid)
            if hThread:
                kernel32.SuspendThread(hThread)
                kernel32.CloseHandle(hThread)
                return True
        except Exception:
            continue
    return False


def _resume_threads(thread_ids: list) -> bool:
    """
    恢复指定的线程列表，循环恢复直到完全恢复

    Args:
        thread_ids: 线程ID列表

    Returns:
        如果成功恢复至少一个线程则返回 True，否则返回 False
    """
    for tid in thread_ids:
        try:
            hThread = kernel32.OpenThread(win32con.THREAD_SUSPEND_RESUME, False, tid)
            if hThread:
                # 循环恢复，直到 ResumeThread 返回值 <= 1（表示完全恢复）
                while True:
                    prev_count = kernel32.ResumeThread(hThread)
                    if prev_count == 0xFFFFFFFF:  # 错误值
                        break
                    if prev_count <= 1:  # 完全恢复
                        kernel32.CloseHandle(hThread)
                        return True
                kernel32.CloseHandle(hThread)
        except Exception:
            continue
    return False


def suspend_process_by_pid(pid: int) -> bool:
    """
    根据进程 PID 挂起进程的所有线程

    Args:
        pid: 进程 PID

    Returns:
        如果成功挂起至少一个线程则返回 True，否则返回 False
    """
    try:
        thread_ids = _get_thread_ids(pid)
        return _suspend_threads(thread_ids) if thread_ids else False
    except Exception:
        return False


def suspend_process(process_name: str) -> bool:
    """
    挂起进程的所有线程

    Args:
        process_name: 进程名称（如 'notepad.exe'）

    Returns:
        如果成功挂起至少一个线程则返回 True，否则返回 False
    """
    pid = find_process_by_name(process_name)
    return suspend_process_by_pid(pid) if pid else False


def resume_process_by_pid(pid: int) -> bool:
    """
    根据进程 PID 恢复进程的所有线程，根据 ResumeThread 返回值循环恢复直到完全恢复

    Args:
        pid: 进程 PID

    Returns:
        如果成功恢复至少一个线程则返回 True，否则返回 False
    """
    try:
        thread_ids = _get_thread_ids(pid)
        return _resume_threads(thread_ids) if thread_ids else False
    except Exception:
        return False


def resume_process(process_name: str) -> bool:
    """
    恢复进程的所有线程，根据 ResumeThread 返回值循环恢复直到完全恢复

    Args:
        process_name: 进程名称（如 'notepad.exe'）

    Returns:
        如果成功恢复至少一个线程则返回 True，否则返回 False
    """
    pid = find_process_by_name(process_name)
    return resume_process_by_pid(pid) if pid else False


_PYTHON_PROCESS_NAMES = {'python.exe', 'pythonw.exe', 'python', 'pythonw', 'python3.exe', 'python3'}


def _is_python_process(proc_name: str) -> bool:
    return proc_name.lower() in _PYTHON_PROCESS_NAMES


def _get_script_from_cmdline(cmdline: list) -> Optional[str]:
    """
    从命令行参数列表中提取脚本路径（跳过 python 解释器本身及其选项标志）
    """
    # cmdline[0] 是解释器本身，从 [1] 开始查找第一个非 -flag 的参数
    for arg in cmdline[1:]:
        if not arg.startswith('-'):
            return arg
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


def find_python_processes_by_script(script_name: str) -> List[int]:
    """
    根据 Python 脚本名（支持相对/绝对路径）查找所有匹配的 Python 进程 PID 列表。

    匹配优先级：
    1. 绝对路径精确匹配（大小写不敏感）
    2. 仅文件名匹配（回退模糊匹配）

    同时支持 python.exe / pythonw.exe 进程。

    Args:
        script_name: 脚本路径，可以是相对路径或绝对路径

    Returns:
        匹配的进程 PID 列表
    """
    target_abs = os.path.normcase(os.path.abspath(script_name))
    target_basename = os.path.normcase(os.path.basename(script_name))

    exact_matches: List[int] = []
    basename_matches: List[int] = []

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
    return exact_matches if exact_matches else basename_matches


def find_python_process_by_script(script_name: str) -> Optional[int]:
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

    success = False
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.kill()
            success = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return success


def find_python_processes_by_cmdline(pattern: str) -> List[int]:
    """
    对 Python 进程的完整命令行字符串进行模糊匹配，返回所有匹配的 PID 列表。

    匹配方式：将 pattern 与进程命令行拼接字符串进行大小写不敏感的子串搜索。

    Args:
        pattern: 要匹配的命令行子串（如脚本名、参数等）

    Returns:
        匹配的进程 PID 列表
    """
    pattern_lower = pattern.lower()
    results: List[int] = []

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

    success = False
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.kill()
            success = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return success


__all__ = [
    'find_process_by_name',
    'suspend_process',
    'suspend_process_by_pid',
    'resume_process',
    'resume_process_by_pid',
    'find_python_process_by_script',
    'find_python_processes_by_script',
    'kill_python_processes_by_script',
    'find_python_processes_by_cmdline',
    'kill_python_processes_by_cmdline',
]
