#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

import ctypes
from typing import Optional

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


__all__ = [
    'find_process_by_name',
    'suspend_process',
    'suspend_process_by_pid',
    'resume_process',
    'resume_process_by_pid',
]
