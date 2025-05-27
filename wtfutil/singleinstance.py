#!/usr/bin/env python 
# -*- coding: utf-8 -*-

import os
import sys
import tempfile
import portalocker


class SingleInstanceException(Exception):
    """
    当已有运行实例时抛出此异常
    """
    pass


class SingleInstance:
    """
    确保在同一台机器上同一脚本只有一个实例在运行。

    参数：
        flavor_id (str): 可选标识，用于区分同脚本的不同单例实例。
        lockfile (str): 自定义锁文件路径，若不提供则根据脚本路径和 flavor_id 自动生成并放在临时目录。

    用法：
        # 上下文管理
        with SingleInstance(flavor_id="worker"):
            # 主逻辑

        # 装饰器方式
        @single_instance(flavor_id="task")
        def main():
            ...

    注意事项：
        此实现参考 https://github.com/pycontribs/tendo/issues/77 中的讨论，
        避免在 Windows 上因多个线程或子进程同时运行时可能引发的锁竞争问题。
        建议：尽量将锁文件放置于操作系统的临时目录中，并使用唯一路径命名，确保不会与其他程序冲突。
    """

    def __init__(self, flavor_id="", lockfile=""):
        # 生成锁文件路径
        if lockfile:
            self.lockfile_path = os.path.abspath(lockfile)
        else:
            # 取脚本全路径作为基础
            script_path = os.path.splitext(os.path.abspath(sys.argv[0]))[0]
            # 替换非法字符
            basename = (
                script_path
                .replace("/", "-")
                .replace("\\", "-")
                .replace(":", "")
            )
            if flavor_id:
                basename = f"{basename}-{flavor_id}"
            basename = f"{basename}.lock"
            # 放入系统临时目录
            self.lockfile_path = os.path.join(tempfile.gettempdir(), basename)
        self._lock_file = None

    def __enter__(self):
        # 打开并尝试加锁，不阻塞
        try:
            self._lock_file = open(self.lockfile_path, 'w')
            portalocker.lock(self._lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.exceptions.LockException:
            raise SingleInstanceException(
                f"已有实例正在运行，锁文件：{self.lockfile_path}"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 释放锁并删除锁文件
        try:
            if self._lock_file:
                portalocker.unlock(self._lock_file)
                self._lock_file.close()
            os.remove(self.lockfile_path)
        except Exception:
            pass


def single_instance(flavor_id="", lockfile=""):
    """
    装饰器方式，函数执行时自动加锁，执行完毕后释放锁。

    参数：
        flavor_id (str): 区分不同单例的标识。
        lockfile (str): 自定义锁文件路径。
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            with SingleInstance(flavor_id=flavor_id, lockfile=lockfile):
                return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["SingleInstance", "SingleInstanceException", "single_instance"]

if __name__ == "__main__":
    # 示例：直接运行此文件以测试单实例
    try:
        with SingleInstance():
            print("运行中：这是唯一的实例。按 Ctrl+C 退出。")
            import time

            while True:
                time.sleep(1)
    except SingleInstanceException as e:
        print(e)
