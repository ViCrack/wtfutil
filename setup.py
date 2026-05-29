#!/usr/bin/env python

""" """

from setuptools import setup, Command
import glob
import io
import os
import subprocess
import sys
from shutil import rmtree

__author__ = "vicrack"
__version__ = "1.2.17"
__contact__ = "18179821+ViCrack@users.noreply.github.com"
__url__ = "https://github.com/vicrack"
__license__ = "GPL-3.0-or-later"
requires = [
    "pymysql",
    "faker",
    "fake_useragent",
    "configobj",
    "requests",
    "urllib3",
    "requests_cache",
    "requests-toolbelt",
    "tldextract",
    "dnspython",
    "ratelimit",
    "rich",
    "pycryptodome",
    "portalocker",
    "psutil",
    "questionary",
    "pywin32; platform_system == 'Windows'",
]

here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = "\n" + f.read()


class PublishCommand(Command):
    """Support setup.py publish."""

    description = "Build and publish the package."
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print("\033[1m{}\033[0m".format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        build_dir = os.path.join(here, "build")
        try:
            self.status("Removing previous builds...")
            rmtree(os.path.join(here, "dist"))
        except FileNotFoundError:
            pass

        # 只构建并上传 wheel；wheel 内须含 wtfutil/*.py，否则 pip 无法 import。
        self.status("Building wheel only (no sdist upload)...")
        try:
            subprocess.check_call(
                [sys.executable, "setup.py", "bdist_wheel"],
                cwd=here,
            )
        except subprocess.CalledProcessError as exc:
            print("Build failed; not uploading or installing.")
            sys.exit(exc.returncode or 1)

        dist_files = sorted(glob.glob(os.path.join(here, "dist", "wtfutil-*.whl")))
        if not dist_files:
            print("No wheel in dist/ (expected wtfutil-*.whl); not uploading or installing.")
            sys.exit(1)

        wheel_path = dist_files[-1]
        names = ", ".join(os.path.basename(f) for f in dist_files)

        try:
            self.status("Uploading to PyPI via Twine: {}".format(names))
            subprocess.check_call(["twine", "upload", *dist_files])
        except subprocess.CalledProcessError as exc:
            print("PyPI upload failed; local install skipped.")
            sys.exit(exc.returncode or 1)

        # 仅在上传成功后再安装，且安装本次发布的 wheel（与 PyPI 产物一致）
        self.status("Upload OK. Installing wheel: {}".format(os.path.basename(wheel_path)))
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", wheel_path],
            )
        except subprocess.CalledProcessError as exc:
            print("PyPI upload succeeded, but local pip install failed.")
            sys.exit(exc.returncode or 1)

        if os.path.isdir(build_dir):
            rmtree(build_dir)
        print("Publish and install completed.")
        sys.exit(0)


setup(
    name="wtfutil",
    version=__version__,
    description="A Python utility.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=__author__,
    author_email=__contact__,
    url=__url__,
    packages=["wtfutil"],
    include_package_data=False,
    zip_safe=False,
    license=__license__,
    install_requires=requires,
    platforms="any",
    classifiers=[
        # See: https://pypi.python.org/pypi?:action=list_classifiers
        "Topic :: Utilities",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Topic :: Software Development :: Libraries",
        "Development Status :: 5 - Production/Stable",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    entry_points={
        "console_scripts": [
            "pykill=wtfutil.pykill:main",
        ],
    },
    cmdclass={
        "publish": PublishCommand,
    },
)

"""
A brief checklist for release:

* tox
* git commit (if applicable)
* Bump setup.py version off of -dev
* git commit -a -m "bump version for x.y.z release"
* python setup.py sdist bdist_wheel upload
* bump docs/conf.py version
* git commit
* git tag -a x.y.z -m "brief summary"
* write CHANGELOG
* git commit
* bump setup.py version onto n+1 dev
* git commit
* git push

"""
