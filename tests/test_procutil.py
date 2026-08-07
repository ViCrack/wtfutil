"""procutil 危险边界和命令行解析回归测试。"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from wtfutil import procutil


class TestProcessMatchingSafety(unittest.TestCase):
    def test_find_process_by_name_is_case_insensitive(self) -> None:
        process = mock.Mock()
        process.info = {"pid": 12345, "name": "Python.EXE"}
        with mock.patch.object(procutil.psutil, "process_iter", return_value=[process]):
            self.assertEqual(procutil.find_process_by_name("python.exe"), 12345)

    def test_pypy_process_names_are_recognized(self) -> None:
        for process_name in ("pypy", "pypy3", "pypy3.exe"):
            with self.subTest(process_name=process_name):
                self.assertTrue(procutil._is_python_process(process_name))

    def test_empty_patterns_are_rejected(self) -> None:
        for invalid_value in ("", "   "):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    procutil.find_python_processes_by_cmdline(invalid_value)
                with self.assertRaises(ValueError):
                    procutil.find_python_processes_by_script(invalid_value)

    def test_kill_by_cmdline_skips_current_process(self) -> None:
        current_pid = os.getpid()
        process_mock = mock.Mock()

        with (
            mock.patch.object(
                procutil,
                "find_python_processes_by_cmdline",
                return_value=[current_pid, 12345],
            ),
            mock.patch.object(
                procutil.psutil,
                "Process",
                return_value=process_mock,
            ) as process_factory,
        ):
            self.assertTrue(procutil.kill_python_processes_by_cmdline("worker"))

        process_factory.assert_called_once_with(12345)
        process_mock.kill.assert_called_once_with()

    def test_suspend_current_process_is_rejected(self) -> None:
        with mock.patch.object(procutil.os, "name", "nt"), self.assertRaises(ValueError):
            procutil.suspend_process_by_pid(os.getpid())

    def test_absolute_script_path_does_not_match_other_directory(self) -> None:
        expected_script = os.path.abspath(
            os.path.join("expected", "worker.py")
        )
        other_directory = os.path.abspath("other")
        process = mock.Mock()
        process.info = {
            "pid": 12345,
            "name": "python.exe",
            "cmdline": ["python", "worker.py"],
            "cwd": other_directory,
        }

        with mock.patch.object(
            procutil.psutil,
            "process_iter",
            return_value=[process],
        ):
            self.assertEqual(
                procutil.find_python_processes_by_script(expected_script),
                [],
            )

    def test_absolute_script_path_matches_exact_process_and_details(self) -> None:
        expected_script = os.path.abspath(
            os.path.join("expected", "worker.py")
        )
        process = mock.Mock()
        process.info = {
            "pid": 12345,
            "name": "python.exe",
            "cmdline": ["python", expected_script],
            "cwd": os.path.dirname(expected_script),
        }

        with mock.patch.object(
            procutil.psutil,
            "process_iter",
            return_value=[process],
        ):
            self.assertEqual(
                procutil.find_python_processes_by_script(expected_script),
                [12345],
            )
        with mock.patch.object(
            procutil.psutil,
            "process_iter",
            return_value=[process],
        ):
            details = procutil.find_python_process_details_by_script(
                expected_script
            )

        self.assertEqual(details[0]["pid"], 12345)
        self.assertEqual(
            details[0]["script_abs"],
            os.path.normcase(expected_script),
        )

    def test_relative_script_path_uses_process_working_directory(self) -> None:
        process_directory = os.path.abspath("worker-directory")
        process = mock.Mock()
        process.info = {
            "pid": 12345,
            "name": "python.exe",
            "cmdline": ["python", "worker.py"],
            "cwd": process_directory,
        }

        with mock.patch.object(
            procutil.psutil,
            "process_iter",
            return_value=[process],
        ):
            self.assertEqual(
                procutil.find_python_processes_by_script(
                    os.path.join("worker-directory", "worker.py")
                ),
                [12345],
            )


class TestPythonCommandLineParsing(unittest.TestCase):
    def test_extracts_script_after_interpreter_options(self) -> None:
        self.assertEqual(
            procutil._get_script_from_cmdline(
                ["python", "-X", "utf8", "worker.py", "--queue", "high"]
            ),
            "worker.py",
        )

    def test_module_and_code_modes_are_not_scripts(self) -> None:
        self.assertIsNone(
            procutil._get_script_from_cmdline(["python", "-m", "http.server"])
        )
        self.assertIsNone(
            procutil._get_script_from_cmdline(["python", "-c", "print(1)"])
        )

    def test_attached_module_and_code_options_are_not_scripts(self) -> None:
        self.assertIsNone(
            procutil._get_script_from_cmdline(
                ["python", "-mhttp.server", "worker.py"]
            )
        )
        self.assertIsNone(
            procutil._get_script_from_cmdline(
                ["python", "-cprint(1)", "worker.py"]
            )
        )


if __name__ == "__main__":
    unittest.main()
