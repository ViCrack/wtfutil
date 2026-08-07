"""sqlutil 数据库隔离和批量写入回归测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from wtfutil.sqlutil import MYSQL, SQLite, ScriptRunner


class TestSQLite(unittest.TestCase):
    def test_instances_do_not_share_connections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            first_path = Path(temporary_directory) / "first.db"
            second_path = Path(temporary_directory) / "second.db"
            first_database = SQLite(str(first_path))
            second_database = SQLite(str(second_path))
            try:
                for database in (first_database, second_database):
                    database.execute(
                        "CREATE TABLE items (name TEXT PRIMARY KEY, value INTEGER)"
                    )
                first_database.insert("items", {"name": "first", "value": 1})
                second_database.insert("items", {"name": "second", "value": 2})

                self.assertEqual(first_database.count("items"), 1)
                self.assertEqual(second_database.count("items"), 1)
                self.assertIsNotNone(
                    first_database.select_one(
                        "items",
                        where_clause={"name": "first"},
                    )
                )
                self.assertIsNone(
                    first_database.select_one(
                        "items",
                        where_clause={"name": "second"},
                    )
                )
            finally:
                first_database.close()
                second_database.close()

    def test_insert_many_uses_first_record_column_order(self) -> None:
        database = SQLite(":memory:")
        try:
            database.execute("CREATE TABLE items (name TEXT, value INTEGER)")
            database.insert_many(
                "items",
                [
                    {"name": "first", "value": 1},
                    {"value": 2, "name": "second"},
                ],
            )
            rows = database.select("items", order="value")
            self.assertEqual(
                rows,
                [
                    {"name": "first", "value": 1},
                    {"name": "second", "value": 2},
                ],
            )
        finally:
            database.close()

    def test_insert_many_rejects_inconsistent_columns(self) -> None:
        database = SQLite(":memory:")
        try:
            with self.assertRaises(ValueError):
                database.insert_many(
                    "items",
                    [{"name": "first"}, {"value": 2}],
                )
        finally:
            database.close()

    def test_close_releases_worker_thread_connections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "threaded.db"
            database = SQLite(str(database_path))
            connection_holder = []

            def create_connection() -> None:
                connection_holder.append(database._get_connection())

            worker = threading.Thread(target=create_connection)
            worker.start()
            worker.join()
            database.close()

            with self.assertRaises(sqlite3.ProgrammingError):
                connection_holder[0].execute("SELECT 1")

    def test_memory_database_is_shared_between_threads(self) -> None:
        database = SQLite(":memory:")
        worker_rows: list[list[dict]] = []
        try:
            database.execute("CREATE TABLE items (name TEXT PRIMARY KEY)")
            database.insert("items", {"name": "shared"})

            worker = threading.Thread(
                target=lambda: worker_rows.append(database.select("items"))
            )
            worker.start()
            worker.join()

            self.assertEqual(worker_rows, [[{"name": "shared"}]])
        finally:
            database.close()

    def test_close_waits_for_active_operation(self) -> None:
        database = SQLite(":memory:")
        operation_started = threading.Event()
        release_operation = threading.Event()
        close_finished = threading.Event()

        def blocking_select(*args, **kwargs):
            operation_started.set()
            release_operation.wait(timeout=2)
            return []

        database._select = blocking_select
        operation_thread = threading.Thread(target=database.select, args=("items",))
        close_thread = threading.Thread(
            target=lambda: (database.close(), close_finished.set())
        )

        operation_thread.start()
        self.assertTrue(operation_started.wait(timeout=1))
        close_thread.start()
        self.assertFalse(close_finished.wait(timeout=0.05))
        release_operation.set()
        operation_thread.join()
        close_thread.join()
        self.assertTrue(close_finished.is_set())


class TestMySQLSqlGeneration(unittest.TestCase):
    def test_insert_builds_valid_placeholders(self) -> None:
        cursor = mock.Mock()
        cursor.lastrowid = 7
        cursor_context = mock.MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = mock.Mock()
        connection.cursor.return_value = cursor_context

        with mock.patch("wtfutil.sqlutil.pymysql_connect", return_value=connection):
            database = MYSQL(
                host="localhost",
                user="user",
                password="password",
                database="database",
            )
            self.assertEqual(
                database.insert("items", {"name": "first", "value": 1}),
                7,
            )

        executed_sql, executed_values = cursor.execute.call_args.args
        self.assertIn("VALUES (%s, %s)", executed_sql)
        self.assertEqual(executed_values, ("first", 1))

    def test_connection_enables_autocommit_by_default(self) -> None:
        connection = mock.Mock()

        with mock.patch(
            "wtfutil.sqlutil.pymysql_connect",
            return_value=connection,
        ) as connection_factory:
            database = MYSQL(
                host="localhost",
                user="user",
                password="password",
                database="database",
            )
            database._get_connection()

        self.assertIs(connection_factory.call_args.kwargs["autocommit"], True)

    def test_managed_transaction_does_not_commit_each_write(self) -> None:
        cursor = mock.Mock()
        cursor.lastrowid = 7
        cursor_context = mock.MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = mock.Mock()
        connection.cursor.return_value = cursor_context

        with mock.patch("wtfutil.sqlutil.pymysql_connect", return_value=connection):
            database = MYSQL(
                host="localhost",
                user="user",
                password="password",
                database="database",
                autocommit=False,
            )
            database.insert("items", {"name": "first"})

        connection.commit.assert_not_called()

    def test_failed_write_rolls_back_in_autocommit_mode(self) -> None:
        cursor = mock.Mock()
        cursor.execute.side_effect = RuntimeError("write failed")
        cursor_context = mock.MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = mock.Mock()
        connection.cursor.return_value = cursor_context

        with mock.patch("wtfutil.sqlutil.pymysql_connect", return_value=connection):
            database = MYSQL(
                host="localhost",
                user="user",
                password="password",
                database="database",
            )
            with self.assertRaises(RuntimeError):
                database.insert("items", {"name": "first"})

        connection.rollback.assert_called_once_with()

    def test_managed_transaction_commit_and_rollback_delegate_to_connection(self) -> None:
        connection = mock.Mock()

        with mock.patch("wtfutil.sqlutil.pymysql_connect", return_value=connection):
            database = MYSQL(
                host="localhost",
                user="user",
                password="password",
                database="database",
                autocommit=False,
            )
            database.commit()
            database.rollback()

        connection.commit.assert_called_once_with()
        connection.rollback.assert_called_once_with()


class TestScriptRunner(unittest.TestCase):
    def test_autocommit_commits_and_closes_cursor(self) -> None:
        cursor = mock.MagicMock()
        connection = mock.Mock()
        connection.cursor.return_value = cursor

        ScriptRunner(connection, autocommit=True).run_script("SELECT 1;\n")

        cursor.execute.assert_called_once_with("SELECT 1;\n")
        cursor.close.assert_called_once_with()
        connection.commit.assert_called_once_with()

    def test_managed_transaction_rolls_back_on_error(self) -> None:
        cursor = mock.MagicMock()
        cursor.execute.side_effect = RuntimeError("boom")
        connection = mock.Mock()
        connection.cursor.return_value = cursor

        with self.assertRaises(RuntimeError):
            ScriptRunner(connection, autocommit=True).run_script("SELECT 1;\n")

        connection.rollback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
