"""pykill CLI 的无副作用参数和退出码测试。"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from wtfutil import pykill


def _process_detail(pid: int = 12345) -> dict:
    return {
        "pid": pid,
        "name": "python.exe",
        "script": "worker.py",
        "script_abs": "C:/jobs/worker.py",
        "cwd": "C:/jobs",
        "cmdline": "python worker.py",
    }


class TestPyKillCli(unittest.TestCase):
    def test_list_mode_excludes_current_process_and_does_not_kill(self) -> None:
        details = [_process_detail(os.getpid()), _process_detail(12345)]
        with (
            mock.patch.object(pykill.sys, "argv", ["pykill", "--list"]),
            mock.patch.object(pykill, "list_all_python_process_details", return_value=details),
            mock.patch.object(pykill, "_kill_pids") as kill_mock,
            mock.patch.object(pykill.console, "print") as print_mock,
        ):
            exit_code = pykill.main()

        self.assertEqual(exit_code, 0)
        kill_mock.assert_not_called()
        rendered_table = print_mock.call_args_list[0].args[0]
        self.assertEqual(rendered_table.row_count, 1)

    def test_missing_script_match_returns_nonzero(self) -> None:
        with (
            mock.patch.object(pykill.sys, "argv", ["pykill", "missing.py"]),
            mock.patch.object(pykill, "find_python_process_details_by_script", return_value=[]),
            mock.patch.object(pykill.console, "print"),
        ):
            self.assertEqual(pykill.main(), 1)

    def test_cmdline_mode_uses_matching_api_and_kills_result(self) -> None:
        details = [_process_detail(12345)]
        with (
            mock.patch.object(pykill.sys, "argv", ["pykill", "--cmdline", "queue=high"]),
            mock.patch.object(
                pykill,
                "find_python_process_details_by_cmdline",
                return_value=details,
            ) as finder,
            mock.patch.object(pykill, "_kill_pids", return_value=True) as kill_mock,
            mock.patch.object(pykill.console, "print"),
        ):
            self.assertEqual(pykill.main(), 0)

        finder.assert_called_once_with("queue=high")
        kill_mock.assert_called_once_with([12345])


if __name__ == "__main__":
    unittest.main()
