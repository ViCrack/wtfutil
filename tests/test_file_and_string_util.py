"""文件和字符串工具的类型与安全边界测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wtfutil import strutil
from wtfutil.fileutil import read_text
from wtfutil.strutil import rand_case, string_to_bash_variable, uuencode


class TestFileUtilities(unittest.TestCase):
    def test_binary_read_returns_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "payload.bin"
            file_path.write_bytes(b"\x00\xff")
            self.assertEqual(read_text(file_path, mode="rb"), b"\x00\xff")

    def test_missing_binary_file_returns_empty_bytes(self) -> None:
        self.assertEqual(
            read_text("missing.bin", mode="rb", not_exists_ok=True),
            b"",
        )


class TestStringUtilities(unittest.TestCase):
    def test_uuencode_accepts_text(self) -> None:
        encoded = uuencode("hello")
        self.assertTrue(encoded.startswith("begin 644 encoder.buf\n"))
        self.assertTrue(encoded.endswith("end\n"))

    def test_unsafe_unpickle_api_is_not_exported(self) -> None:
        self.assertNotIn("base64unpickle", strutil.__all__)
        self.assertFalse(hasattr(strutil, "base64unpickle"))

    def test_rand_case_requires_case_sensitive_character(self) -> None:
        with self.assertRaises(ValueError):
            rand_case("123-=")
        self.assertNotEqual(rand_case("a123"), "a123")

    def test_bash_variable_is_always_non_empty_and_valid(self) -> None:
        self.assertEqual(string_to_bash_variable(""), "_")
        self.assertEqual(string_to_bash_variable("💥1"), "_1")


if __name__ == "__main__":
    unittest.main()
