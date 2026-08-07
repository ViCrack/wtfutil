"""供 :mod:`wtfutil.procutil` 使用的 Windows 线程挂起/恢复后端。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_THREAD_SUSPEND_RESUME = 0x0002
_THREAD_OPERATION_FAILED = 0xFFFFFFFF

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_kernel32.OpenThread.argtypes = (
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
)
_kernel32.OpenThread.restype = wintypes.HANDLE

_kernel32.SuspendThread.argtypes = (wintypes.HANDLE,)
_kernel32.SuspendThread.restype = wintypes.DWORD

_kernel32.ResumeThread.argtypes = (wintypes.HANDLE,)
_kernel32.ResumeThread.restype = wintypes.DWORD

_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL


def suspend_threads(thread_ids: list[int]) -> bool:
    """挂起全部可访问线程，并返回是否至少成功挂起一个线程。"""
    any_thread_suspended = False

    for thread_id in thread_ids:
        handle = _kernel32.OpenThread(
            _THREAD_SUSPEND_RESUME,
            False,
            thread_id,
        )
        if not handle:
            continue

        try:
            if _kernel32.SuspendThread(handle) != _THREAD_OPERATION_FAILED:
                any_thread_suspended = True
        finally:
            _kernel32.CloseHandle(handle)

    return any_thread_suspended


def resume_threads(thread_ids: list[int]) -> bool:
    """完全恢复全部可访问线程，并返回是否至少恢复过一个线程。"""
    any_thread_resumed = False

    for thread_id in thread_ids:
        handle = _kernel32.OpenThread(
            _THREAD_SUSPEND_RESUME,
            False,
            thread_id,
        )
        if not handle:
            continue

        try:
            while True:
                previous_count = _kernel32.ResumeThread(handle)
                if previous_count == _THREAD_OPERATION_FAILED:
                    break
                if previous_count == 0:
                    break

                any_thread_resumed = True
                if previous_count <= 1:
                    break
        finally:
            _kernel32.CloseHandle(handle)

    return any_thread_resumed


__all__ = ["resume_threads", "suspend_threads"]
