#!/usr/bin/env python
"""
一键发布脚本：测试 → 清理 → 构建/校验 wheel → 隔离安装 → 上传 PyPI → 本地安装。

用法：
    python publish.py

前置依赖（一次性安装）：
    pip install build twine
"""

import glob
import os
import re
import subprocess
import sys
import time
import venv
from email.parser import BytesParser
from email.policy import default as default_email_policy
from pathlib import Path, PurePosixPath
from shutil import rmtree
from tempfile import TemporaryDirectory
from zipfile import ZipFile

HERE = os.path.abspath(os.path.dirname(__file__))
PROJECT_FILE = Path(HERE) / "pyproject.toml"


def status(msg: str) -> None:
    print(f"\033[1m{msg}\033[0m")


def run(*args: str, **kwargs) -> None:
    result = subprocess.run(list(args), check=False, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)


def read_project_version() -> str:
    """从 pyproject.toml 的 [project] 段读取待发布版本。"""
    project_content = PROJECT_FILE.read_text(encoding="utf-8")
    project_section_match = re.search(
        r"(?ms)^\[project\]\s*$\n(.*?)(?=^\[|\Z)",
        project_content,
    )
    if project_section_match is None:
        raise RuntimeError("pyproject.toml is missing the [project] section")
    version_match = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"\s*$',
        project_section_match.group(1),
    )
    if version_match is None:
        raise RuntimeError("pyproject.toml is missing project.version")
    return version_match.group(1)


def validate_wheel_contents(wheel_path: str) -> None:
    """拒绝包含测试目录或测试脚本的 wheel，避免误上传开发文件。"""
    with ZipFile(wheel_path) as wheel_archive:
        forbidden_members = []
        for archive_member in wheel_archive.namelist():
            normalized_member = archive_member.replace("\\", "/")
            member_path = PurePosixPath(normalized_member)
            member_name = member_path.name.lower()
            contains_test_directory = "tests" in {
                path_part.lower() for path_part in member_path.parts[:-1]
            }
            is_test_script = (
                member_name.startswith("test_") or member_name.endswith("_test.py")
            )
            if contains_test_directory or is_test_script:
                forbidden_members.append(archive_member)

    if forbidden_members:
        formatted_members = "\n".join(
            f"  - {archive_member}" for archive_member in forbidden_members
        )
        raise RuntimeError(
            "Wheel contains test files and cannot be published:\n"
            f"{formatted_members}"
        )


def validate_wheel_metadata(wheel_path: str, expected_version: str) -> None:
    """校验 wheel 名称、版本和控制台入口，避免上传错误产物。"""
    with ZipFile(wheel_path) as wheel_archive:
        metadata_members = [
            archive_member
            for archive_member in wheel_archive.namelist()
            if archive_member.endswith(".dist-info/METADATA")
        ]
        entry_point_members = [
            archive_member
            for archive_member in wheel_archive.namelist()
            if archive_member.endswith(".dist-info/entry_points.txt")
        ]
        if len(metadata_members) != 1:
            raise RuntimeError("Wheel must contain exactly one METADATA file")
        if len(entry_point_members) != 1:
            raise RuntimeError("Wheel must contain exactly one entry_points.txt file")

        metadata = BytesParser(policy=default_email_policy).parsebytes(
            wheel_archive.read(metadata_members[0])
        )
        distribution_name = metadata.get("Name")
        distribution_version = metadata.get("Version")
        entry_points = wheel_archive.read(entry_point_members[0]).decode("utf-8")

    if distribution_name != "wtfutil":
        raise RuntimeError(f"Unexpected wheel distribution name: {distribution_name!r}")
    if distribution_version != expected_version:
        raise RuntimeError(
            "Wheel version does not match pyproject.toml: "
            f"{distribution_version!r} != {expected_version!r}"
        )
    expected_entry_points = {
        "memshell = wtfutil.memshell:main",
        "pykill = wtfutil.pykill:main",
    }
    missing_entry_points = sorted(
        entry_point
        for entry_point in expected_entry_points
        if entry_point not in entry_points
    )
    if missing_entry_points:
        raise RuntimeError(
            "Wheel is missing console entry points: "
            + ", ".join(missing_entry_points)
        )


def run_release_tests() -> None:
    """运行默认无外网联调的全量测试，并把资源警告视为错误。"""
    test_environment = os.environ.copy()
    test_environment["MEMSHELL_RUN_LIVE"] = "0"
    status("Running release tests...")
    run(
        sys.executable,
        "-W",
        "error::ResourceWarning",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-t",
        ".",
        "-p",
        "test_*.py",
        "-v",
        cwd=HERE,
        env=test_environment,
    )


def validate_installation(wheel_path: str, expected_version: str) -> None:
    """在临时虚拟环境安装 wheel，并验证模块和 CLI 可加载。"""
    resolved_wheel_path = str(Path(wheel_path).resolve())
    status("Validating wheel in an isolated environment...")
    with TemporaryDirectory(prefix="wtfutil-release-") as temporary_directory:
        environment_directory = Path(temporary_directory) / "venv"
        venv.EnvBuilder(
            with_pip=True,
            system_site_packages=True,
        ).create(environment_directory)
        scripts_directory = environment_directory / (
            "Scripts" if os.name == "nt" else "bin"
        )
        environment_python = scripts_directory / (
            "python.exe" if os.name == "nt" else "python"
        )
        run(
            str(environment_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--force-reinstall",
            resolved_wheel_path,
            cwd=temporary_directory,
        )
        smoke_test = (
            "from importlib import import_module; "
            "from importlib.metadata import version; "
            "modules = ('configutil', 'fileutil', 'httputil', 'imgutil', "
            "'memshellutil', 'notifyutil', 'procutil', 'singleinstance', "
            "'sqlutil', 'strutil', 'translateutil', 'util'); "
            "[import_module(f'wtfutil.{module}') for module in modules]; "
            f"assert version('wtfutil') == {expected_version!r}"
        )
        run(
            str(environment_python),
            "-c",
            smoke_test,
            cwd=temporary_directory,
        )
        run(
            str(environment_python),
            "-m",
            "wtfutil.memshell",
            "--help",
            cwd=temporary_directory,
            stdout=subprocess.DEVNULL,
        )
        run(
            str(environment_python),
            "-m",
            "wtfutil.pykill",
            "--help",
            cwd=temporary_directory,
            stdout=subprocess.DEVNULL,
        )


def install_published_version(version: str, attempts: int = 6) -> None:
    """从 PyPI 安装指定版本，短暂传播延迟时自动重试。"""
    package_requirement = f"wtfutil=={version}"
    for attempt_number in range(1, attempts + 1):
        status(
            f"Installing from PyPI: {package_requirement} "
            f"(attempt {attempt_number}/{attempts})"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--index-url",
                "https://pypi.org/simple",
                "--no-cache-dir",
                "--no-deps",
                "--upgrade",
                "--force-reinstall",
                package_requirement,
            ],
            cwd=HERE,
            check=False,
        )
        if result.returncode == 0:
            return
        if attempt_number < attempts:
            time.sleep(5)
    sys.exit(result.returncode)


def validate_published_installation(expected_version: str) -> None:
    """在项目目录之外验证当前解释器加载的是已安装版本。"""
    with TemporaryDirectory(prefix="wtfutil-installed-") as temporary_directory:
        validation_script = (
            "from importlib.metadata import version; "
            "from pathlib import Path; "
            "from sysconfig import get_paths; "
            "import wtfutil; "
            f"assert version('wtfutil') == {expected_version!r}; "
            "assert Path(wtfutil.__file__).resolve().is_relative_to("
            "Path(get_paths()['purelib']).resolve()); "
            "print(version('wtfutil')); "
            "print(wtfutil.__file__)"
        )
        run(
            sys.executable,
            "-c",
            validation_script,
            cwd=temporary_directory,
        )


def clean_generated_artifacts(*, preserve_dist: bool) -> None:
    """删除测试和构建产生的缓存，按需保留最终 wheel。"""
    project_directory = Path(HERE)
    generated_directories = [
        project_directory / "build",
        project_directory / "wtfutil.egg-info",
        project_directory / ".pytest_cache",
        project_directory / ".ruff_cache",
    ]
    generated_directories.extend(project_directory.rglob("__pycache__"))
    if not preserve_dist:
        generated_directories.append(project_directory / "dist")

    for generated_directory in sorted(
        set(generated_directories),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if generated_directory.is_dir():
            rmtree(generated_directory)


def main() -> None:
    project_version = read_project_version()
    status(f"Preparing wtfutil {project_version}...")

    # 1. 清除历史产物，再执行上传前完整测试。
    clean_generated_artifacts(preserve_dist=False)
    run_release_tests()

    # 2. 只构建 wheel（不生成 sdist 源码包）。
    dist_dir = os.path.join(HERE, "dist")
    status("Building wheel...")
    run(sys.executable, "-m", "build", "--wheel", cwd=HERE)

    wheels = sorted(glob.glob(os.path.join(dist_dir, "wtfutil-*.whl")))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected exactly one wtfutil wheel in dist/, found {len(wheels)}"
        )

    wheel = wheels[0]
    validate_wheel_contents(wheel)
    validate_wheel_metadata(wheel, project_version)
    status(f"Built: {os.path.basename(wheel)}")

    # 3. 上传前检查元数据并在隔离环境完成安装冒烟。
    status("Checking wheel metadata...")
    run(sys.executable, "-m", "twine", "check", wheel, cwd=HERE)
    validate_installation(wheel, project_version)

    # 4. 上传到 PyPI。
    status("Uploading to PyPI...")
    run(
        sys.executable,
        "-m",
        "twine",
        "upload",
        "--non-interactive",
        wheel,
        cwd=HERE,
    )

    # 5. 从 PyPI 安装刚发布的精确版本并验证。
    install_published_version(project_version)
    validate_published_installation(project_version)

    # 6. 保留最终 wheel，清理其余测试与构建缓存。
    clean_generated_artifacts(preserve_dist=True)

    status("Done.")


if __name__ == "__main__":
    main()
