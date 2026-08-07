"""util 资源解析和去重队列回归测试。"""

from __future__ import annotations

import queue
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import wtfutil
from wtfutil.util import (
    UniqueQueue,
    cut_list,
    format_datetime,
    get_resource,
    get_resource_dir,
    group_data,
    measure_time,
    parse_datetime,
    unique_items,
)


class TestResourceHelpers(unittest.TestCase):
    def test_public_functions_belong_to_util_module(self) -> None:
        self.assertEqual(get_resource.__module__, "wtfutil.util")
        self.assertEqual(get_resource_dir.__module__, "wtfutil.util")

    def test_resolves_resource_from_explicit_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            resource_directory = project_directory / "resource"
            resource_directory.mkdir()
            resource_file = resource_directory / "settings.json"
            resource_file.write_text("{}", encoding="utf-8")
            anchor_file = project_directory / "src" / "worker.py"

            self.assertEqual(
                Path(get_resource_dir(anchor_file)),
                resource_directory,
            )
            self.assertEqual(
                Path(get_resource("settings.json", basedir=anchor_file)),
                resource_file,
            )

    def test_symlink_anchor_prefers_deployment_resource_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root_directory = Path(temporary_directory)
            source_directory = root_directory / "source"
            deployment_directory = root_directory / "deployment"
            source_directory.mkdir()
            (deployment_directory / "bin").mkdir(parents=True)
            resource_directory = deployment_directory / "resource"
            resource_directory.mkdir()

            source_file = source_directory / "worker.py"
            source_file.write_text("", encoding="utf-8")
            symlink_file = deployment_directory / "bin" / "worker.py"
            try:
                symlink_file.symlink_to(source_file)
            except OSError as exc:
                self.skipTest(f"当前环境不允许创建符号链接：{exc}")

            self.assertEqual(
                Path(get_resource_dir(symlink_file)),
                resource_directory,
            )

    def test_symbols_use_their_owning_submodules(self) -> None:
        self.assertFalse(hasattr(wtfutil, "MemShellParty"))

        from wtfutil.memshellutil import MemShellParty

        self.assertEqual(MemShellParty.__module__, "wtfutil.memshellutil")


class TestUniqueQueue(unittest.TestCase):
    def test_equivalent_nested_dicts_are_deduplicated(self) -> None:
        unique_queue = UniqueQueue()
        unique_queue.put({"name": "job", "tags": ["a", "b"]})
        unique_queue.put({"tags": ["a", "b"], "name": "job"})

        self.assertEqual(unique_queue.qsize(), 1)

    def test_failed_put_does_not_poison_deduplication_state(self) -> None:
        unique_queue = UniqueQueue(maxsize=1)
        unique_queue.put("first")

        with self.assertRaises(queue.Full):
            unique_queue.put("second", block=False)

        self.assertEqual(unique_queue.get_nowait(), "first")
        unique_queue.put("second", block=False)
        self.assertEqual(unique_queue.get_nowait(), "second")


class TestCollectionAndTimeHelpers(unittest.TestCase):
    def test_collection_helpers_keep_order_and_group_records(self) -> None:
        self.assertEqual(unique_items([3, 1, 3, 2, 1]), [3, 1, 2])
        self.assertEqual(cut_list([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
        grouped_records = group_data(
            [
                {"name": "first", "group": "a"},
                {"name": "second", "group": "b"},
                {"name": "first", "group": "a"},
            ],
            "group",
            remove_duplicates=True,
        )
        self.assertEqual(
            grouped_records["a"],
            [{"name": "first", "group": "a"}],
        )

    def test_datetime_helpers_round_trip(self) -> None:
        value = datetime(2026, 8, 7, 12, 34, 56)  # noqa: DTZ001 - API intentionally accepts naive values.
        formatted_value = format_datetime(value)
        self.assertEqual(formatted_value, "2026-08-07 12:34:56")
        self.assertEqual(parse_datetime(formatted_value), value)

    def test_measure_time_preserves_result_and_reports_duration(self) -> None:
        @measure_time
        def add(first_value: int, second_value: int) -> int:
            return first_value + second_value

        with (
            mock.patch("wtfutil.util.time.time", side_effect=[10.0, 10.25]),
            mock.patch("builtins.print") as print_mock,
        ):
            self.assertEqual(add(2, 3), 5)

        print_mock.assert_called_once_with("Function 'add' executed in 0.2500 seconds")


if __name__ == "__main__":
    unittest.main()
