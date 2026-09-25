"""公开模块边界和打包排除规则测试。"""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import wtfutil
from publish import (
    read_project_version,
    validate_wheel_contents,
    validate_wheel_metadata,
)

PUBLIC_MODULE_NAMES = (
    "configutil",
    "daydaymaputil",
    "fileutil",
    "httputil",
    "imgutil",
    "memshellutil",
    "notifyutil",
    "procutil",
    "singleinstance",
    "sqlutil",
    "strutil",
    "translateutil",
    "util",
)


class TestPublicApiContract(unittest.TestCase):
    def test_package_root_does_not_aggregate_symbols(self) -> None:
        self.assertEqual(wtfutil.__all__, ())

    def test_daydaymap_public_sources_and_cli_boundary(self) -> None:
        from wtfutil import daydaymap, daydaymaputil
        expected = {'DEFAULT_BASE_URL', 'DayDayMapClient', 'DayDayMapError', 'DayDayMapCount',
                    'DayDayMapSearchSummary', 'find_key_file', 'load_keys', 'build_query',
                    'query_from_icon', 'query_from_certificate'}
        self.assertEqual(set(daydaymaputil.__all__), expected)
        self.assertEqual(daydaymap.__all__, ['main'])
        self.assertEqual(daydaymaputil.build_query('x'), '(x) && ip.tag!="蜜罐"')

    def test_every_exported_symbol_exists_and_is_unique(self) -> None:
        for module_name in PUBLIC_MODULE_NAMES:
            with self.subTest(module_name=module_name):
                module = importlib.import_module(f"wtfutil.{module_name}")
                exported_names = tuple(module.__all__)
                self.assertEqual(len(exported_names), len(set(exported_names)))
                for exported_name in exported_names:
                    self.assertTrue(
                        hasattr(module, exported_name),
                        f"wtfutil.{module_name}.{exported_name} 不存在",
                    )


class TestPackagingExclusions(unittest.TestCase):
    def test_packaging_configuration_excludes_tests(self) -> None:
        project_directory = Path(__file__).resolve().parents[1]
        manifest_content = (project_directory / "MANIFEST.in").read_text(encoding="utf-8")
        project_content = (project_directory / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("prune tests", manifest_content)
        self.assertIn("test_*.py", manifest_content)
        self.assertIn("*_test.py", manifest_content)
        self.assertIn('exclude = ["tests*"]', project_content)

    def test_publish_validator_rejects_test_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            valid_wheel = Path(temporary_directory) / "valid.whl"
            invalid_wheel = Path(temporary_directory) / "invalid.whl"
            with ZipFile(valid_wheel, "w") as archive:
                archive.writestr("wtfutil/fileutil.py", "")
            with ZipFile(invalid_wheel, "w") as archive:
                archive.writestr("wtfutil/fileutil.py", "")
                archive.writestr("tests/test_fileutil.py", "")

            validate_wheel_contents(str(valid_wheel))
            with self.assertRaisesRegex(RuntimeError, "tests/test_fileutil.py"):
                validate_wheel_contents(str(invalid_wheel))

    def test_publish_validator_checks_version_and_entry_points(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            wheel_path = Path(temporary_directory) / "wtfutil.whl"
            with ZipFile(wheel_path, "w") as archive:
                archive.writestr(
                    "wtfutil-1.3.2.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: wtfutil\nVersion: 1.3.2\n",
                )
                archive.writestr(
                    "wtfutil-1.3.2.dist-info/entry_points.txt",
                    "[console_scripts]\n"
                    "memshell = wtfutil.memshell:main\n"
                    "daydaymap = wtfutil.daydaymap:main\n"
                    "pykill = wtfutil.pykill:main\n",
                )

            validate_wheel_metadata(str(wheel_path), "1.3.2")
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                validate_wheel_metadata(str(wheel_path), "1.3.3")

    def test_publish_validator_requires_daydaymap_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel_path = Path(directory) / "missing-cli.whl"
            with ZipFile(wheel_path, "w") as archive:
                archive.writestr("wtfutil-1.4.3.dist-info/METADATA",
                                 "Metadata-Version: 2.1\nName: wtfutil\nVersion: 1.4.3\n")
                archive.writestr("wtfutil-1.4.3.dist-info/entry_points.txt",
                                 "[console_scripts]\nmemshell = wtfutil.memshell:main\npykill = wtfutil.pykill:main\n")
            with self.assertRaisesRegex(RuntimeError, "daydaymap"):
                validate_wheel_metadata(str(wheel_path), "1.4.3")

    def test_project_version_is_read_from_project_section(self) -> None:
        self.assertRegex(read_project_version(), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
