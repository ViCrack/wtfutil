"""configutil：wtfconfig.ini 合并与 mtime 热加载。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wtfutil.configutil as cu


class TestConfigUtil(unittest.TestCase):
    def setUp(self):
        cu.reload_wtfconfig()
        self._tmp = tempfile.TemporaryDirectory()
        self.ini = Path(self._tmp.name) / "wtfconfig.ini"
        self._env_backup = {}

    def tearDown(self):
        for key, old in self._env_backup.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        cu.reload_wtfconfig()
        self._tmp.cleanup()

    def _setenv(self, key: str, value: str | None) -> None:
        if key not in self._env_backup:
            self._env_backup[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def _write_ini(self, text: str) -> None:
        self.ini.write_text(text, encoding="utf-8")

    def _bump_mtime(self) -> None:
        st = self.ini.stat()
        os.utime(self.ini, (st.st_atime, st.st_mtime + 2))

    def test_missing_file_falls_back_to_defaults(self):
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=None):
            cu.reload_wtfconfig()
            merged = cu.merge_section({"A": "1", "B": "2"}, "notify")
            self.assertEqual(merged, {"A": "1", "B": "2"})
            target = {"stale": "x"}
            self.assertTrue(
                cu.ensure_section(target, {"A": "1"}, "notify")
            )
            self.assertEqual(target, {"A": "1"})

    def test_first_load_merges_section(self):
        self._write_ini("[img]\napihz_img_id = from-ini\n")
        defaults = {"APIHZ_IMG_ID": "", "APIHZ_IMG_KEY": ""}
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=str(self.ini)):
            cu.reload_wtfconfig()
            target: dict = {}
            self.assertTrue(
                cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            )
            self.assertEqual(target["APIHZ_IMG_ID"], "from-ini")
            self.assertEqual(target["APIHZ_IMG_KEY"], "")

    def test_unchanged_mtime_keeps_manual_edits(self):
        self._write_ini("[img]\nAPIHZ_IMG_ID = ini\n")
        defaults = {"APIHZ_IMG_ID": "", "APIHZ_IMG_KEY": ""}
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=str(self.ini)):
            cu.reload_wtfconfig()
            target: dict = {}
            self.assertTrue(
                cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            )
            target["APIHZ_IMG_ID"] = "manual"
            self.assertFalse(
                cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            )
            self.assertEqual(target["APIHZ_IMG_ID"], "manual")

    def test_mtime_change_hot_reloads(self):
        self._write_ini("[img]\nAPIHZ_IMG_ID = v1\n")
        defaults = {"APIHZ_IMG_ID": "", "APIHZ_IMG_KEY": ""}
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=str(self.ini)):
            cu.reload_wtfconfig()
            target: dict = {}
            self.assertTrue(
                cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            )
            self.assertEqual(target["APIHZ_IMG_ID"], "v1")

            self._write_ini("[img]\nAPIHZ_IMG_ID = v2\n")
            self._bump_mtime()
            self.assertTrue(
                cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            )
            self.assertEqual(target["APIHZ_IMG_ID"], "v2")

    def test_env_map_overrides(self):
        self._write_ini("[memshell]\nBASE_URL = https://from-ini.example\n")
        defaults = {"BASE_URL": "https://party.mem.mk"}
        self._setenv("MEMSHELL_BASE_URL", "https://from-env.example")
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=str(self.ini)):
            cu.reload_wtfconfig()
            merged = cu.merge_section(
                defaults,
                "memshell",
                uppercase_keys=True,
                env_map={"BASE_URL": "MEMSHELL_BASE_URL"},
            )
            self.assertEqual(merged["BASE_URL"], "https://from-env.example")

    def test_env_same_key_name(self):
        self._write_ini("[notify]\nCONSOLE = false\n")
        defaults = {"CONSOLE": ""}
        self._setenv("CONSOLE", "true")
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=str(self.ini)):
            cu.reload_wtfconfig()
            merged = cu.merge_section(defaults, "notify")
            self.assertEqual(merged["CONSOLE"], "true")

    def test_reload_wtfconfig_forces_reread(self):
        self._write_ini("[img]\nAPIHZ_IMG_ID = a\n")
        defaults = {"APIHZ_IMG_ID": ""}
        with mock.patch.object(cu, "get_wtfconfig_path", return_value=str(self.ini)):
            cu.reload_wtfconfig()
            target: dict = {}
            cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            self._write_ini("[img]\nAPIHZ_IMG_ID = b\n")
            # 不 bump mtime 时 ensure 本应跳过；reload 后强制再合并
            cu.reload_wtfconfig()
            self.assertTrue(
                cu.ensure_section(target, defaults, "img", uppercase_keys=True)
            )
            self.assertEqual(target["APIHZ_IMG_ID"], "b")


if __name__ == "__main__":
    unittest.main()
