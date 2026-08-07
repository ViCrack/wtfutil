"""fileutil 常见读写、摘要和 JAR 分析测试。"""

from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from wtfutil.fileutil import (
    JarAnalyzer,
    file_md5,
    file_sha1,
    file_sha256,
    list_directories,
    list_files,
    read_json,
    read_lines,
    read_text,
    touch,
    write_json,
    write_lines,
    write_text,
)


class TestFileReadWrite(unittest.TestCase):
    def test_hashes_match_standard_library(self) -> None:
        content = b"wtfutil\x00payload"
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "payload.bin"
            file_path.write_bytes(content)

            self.assertEqual(file_md5(file_path), hashlib.md5(content).hexdigest())
            self.assertEqual(file_sha1(file_path), hashlib.sha1(content).hexdigest())
            self.assertEqual(file_sha256(file_path), hashlib.sha256(content).hexdigest())

    def test_text_lines_and_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root_directory = Path(temporary_directory)
            text_path = root_directory / "message.txt"
            lines_path = root_directory / "lines.txt"
            json_path = root_directory / "data.json"

            write_text(text_path, "中文\ntext")
            write_lines(lines_path, ["first", "second", "first"], unique=True)
            write_json(json_path, {"message": "中文", "value": 3})

            self.assertEqual(read_text(text_path), "中文\ntext")
            self.assertEqual(read_lines(lines_path), ["first", "second"])
            self.assertEqual(read_json(json_path), {"message": "中文", "value": 3})

    def test_read_text_rejects_write_modes_before_opening_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "important.txt"
            file_path.write_text("keep", encoding="utf-8")

            for invalid_mode in ("w", "a", "x", "r+"):
                with self.subTest(invalid_mode=invalid_mode):
                    with self.assertRaises(ValueError):
                        read_text(file_path, mode=invalid_mode)
                    self.assertEqual(file_path.read_text(encoding="utf-8"), "keep")

    def test_list_helpers_only_include_direct_children(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root_directory = Path(temporary_directory)
            direct_file = root_directory / "direct.txt"
            nested_directory = root_directory / "nested"
            nested_directory.mkdir()
            direct_file.write_text("data", encoding="utf-8")
            (nested_directory / "nested.txt").write_text("data", encoding="utf-8")

            self.assertEqual(set(list_files(root_directory)), {str(direct_file)})
            self.assertEqual(set(list_directories(root_directory)), {str(nested_directory)})

    def test_touch_create_and_existing_file_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "created.txt"
            touch(file_path)
            self.assertTrue(file_path.is_file())
            with self.assertRaises(FileExistsError):
                touch(file_path, exist_ok=False)


class TestJarAnalyzer(unittest.TestCase):
    @staticmethod
    def _write_jar(path: Path, *, manifest: str, class_major: int) -> None:
        class_header = b"\xca\xfe\xba\xbe" + struct.pack(">HH", 0, class_major)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("META-INF/MANIFEST.MF", manifest)
            archive.writestr("example/Main.class", class_header)

    def test_java_22_and_folded_main_class_are_recognized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            jar_path = Path(temporary_directory) / "sample.JAR"
            self._write_jar(
                jar_path,
                manifest="Manifest-Version: 1.0\r\nMain-Class: example.\r\n Main\r\n",
                class_major=66,
            )

            with mock.patch("wtfutil.fileutil.subprocess.run", side_effect=FileNotFoundError):
                analyzer = JarAnalyzer(str(jar_path))

            self.assertEqual(analyzer.main_class, "example.Main")
            self.assertEqual(analyzer.jdk_version, 22)

    def test_javap_dot_notation_detects_gui_application(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            jar_path = Path(temporary_directory) / "gui.jar"
            self._write_jar(
                jar_path,
                manifest="Manifest-Version: 1.0\nMain-Class: example.Main\n",
                class_major=61,
            )
            javap_result = SimpleNamespace(
                stdout="public class example.Main extends javax.swing.JFrame {}"
            )

            with mock.patch("wtfutil.fileutil.subprocess.run", return_value=javap_result):
                analyzer = JarAnalyzer(str(jar_path))

            self.assertEqual(analyzer.recommended_executable, "javaw")


if __name__ == "__main__":
    unittest.main()
