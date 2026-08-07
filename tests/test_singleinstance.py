"""singleinstance 文件锁生命周期测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wtfutil.singleinstance import (
    SingleInstance,
    SingleInstanceException,
    single_instance,
)


class TestSingleInstance(unittest.TestCase):
    def test_lock_file_is_reused_without_deletion_race(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_path = Path(temporary_directory) / "worker.lock"
            first_instance = SingleInstance(lockfile=str(lock_path))
            first_instance.__enter__()
            try:
                with self.assertRaises(SingleInstanceException):
                    with SingleInstance(lockfile=str(lock_path)):
                        self.fail("第二个实例不应获取到锁")
            finally:
                first_instance.__exit__(None, None, None)

            self.assertTrue(lock_path.exists())
            with SingleInstance(lockfile=str(lock_path)):
                pass

    def test_decorator_preserves_function_metadata(self) -> None:
        @single_instance(flavor_id="metadata-test")
        def sample_job() -> str:
            """示例任务。"""
            return "done"

        self.assertEqual(sample_job.__name__, "sample_job")
        self.assertEqual(sample_job.__doc__, "示例任务。")


if __name__ == "__main__":
    unittest.main()
