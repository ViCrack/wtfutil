#!/usr/bin/env python
"""
一键发布脚本：清理 dist/ → 构建 wheel → 上传 PyPI → 本地安装。

用法：
    python publish.py

前置依赖（一次性安装）：
    pip install build twine
"""

import glob
import os
import subprocess
import sys
from shutil import rmtree

HERE = os.path.abspath(os.path.dirname(__file__))


def status(msg: str) -> None:
    print(f"\033[1m{msg}\033[0m")


def run(*args: str, **kwargs) -> None:
    result = subprocess.run(list(args), **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    # 1. 清理上次产物
    dist_dir = os.path.join(HERE, "dist")
    if os.path.isdir(dist_dir):
        status("Removing previous dist/...")
        rmtree(dist_dir)

    # 2. 只构建 wheel（不生成 sdist 源码包）
    status("Building wheel...")
    run(sys.executable, "-m", "build", "--wheel", cwd=HERE)

    wheels = sorted(glob.glob(os.path.join(dist_dir, "wtfutil-*.whl")))
    if not wheels:
        print("No wheel found in dist/; aborting.")
        sys.exit(1)

    wheel = wheels[-1]
    status(f"Built: {os.path.basename(wheel)}")

    # 3. 上传到 PyPI
    status("Uploading to PyPI...")
    run("twine", "upload", *wheels)

    # 4. 本地安装刚构建的 wheel（与 PyPI 产物一致）
    status(f"Installing locally: {os.path.basename(wheel)}")
    run(sys.executable, "-m", "pip", "install", "--upgrade", wheel)

    status("Done.")


if __name__ == "__main__":
    main()
