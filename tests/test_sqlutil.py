"""sqlutil 数据库隔离和批量写入回归测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from wtfutil.sqlutil import MYSQL, ScriptRunner, SQLite


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

    def test_write_is_committed_before_close_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "committed.db"
            database = SQLite(str(database_path))
            database.execute("CREATE TABLE items (name TEXT PRIMARY KEY)")
            database.insert("items", {"name": "committed"})
            database.close()

            reopened_database = SQLite(str(database_path))
            try:
                self.assertEqual(reopened_database.count("items"), 1)
            finally:
                reopened_database.close()

    def test_insert_many_uses_first_record_column_order(self) -> None:
        database = SQLite(":memory:")
        try:
            database.execute("CREATE TABLE items (name TEXT, value INTEGER)")
            inserted_count = database.insert_many(
                "items",
                [
                    {"name": "first", "value": 1},
                    {"value": 2, "name": "second"},
                ],
            )
            self.assertEqual(inserted_count, 2)
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

    def test_common_crud_and_null_filter(self) -> None:
        database = SQLite(":memory:")
        try:
            database.execute(
                "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, note TEXT)"
            )
            first_id = database.insert("items", {"name": "first", "note": None})
            second_id = database.insert("items", {"name": "second", "note": "value"})

            self.assertTrue(database.record_exists("items", {"id": first_id}))
            self.assertEqual(database.count("items", {"note": None}), 1)
            self.assertEqual(
                database.select_one("items", where_clause={"note": None})["name"],
                "first",
            )
            self.assertEqual(database.update("items", {"note": "updated"}, {"id": first_id}), 1)
            self.assertEqual(database.select_by_id("items", second_id)["name"], "second")
            self.assertEqual(database.delete("items", {"id": second_id}), 1)
            self.assertEqual(database.count("items"), 1)
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

    def test_short_lived_threads_reuse_one_connection(self) -> None:
        database = SQLite(":memory:")
        connection_identifiers: list[int] = []
        try:
            for _ in range(20):
                worker = threading.Thread(
                    target=lambda: connection_identifiers.append(
                        id(database._get_connection())
                    )
                )
                worker.start()
                worker.join()

            self.assertEqual(len(set(connection_identifiers)), 1)
        finally:
            database.close()

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
        connection.commit.assert_called_once_with()

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

        cursor.execute.assert_called_once_with("SELECT 1;")
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

    def test_multiple_statements_on_one_line_are_executed_separately(self) -> None:
        cursors = [mock.MagicMock(), mock.MagicMock()]
        connection = mock.Mock()
        connection.cursor.side_effect = cursors

        ScriptRunner(connection, autocommit=True).run_script("SELECT 1; SELECT 2;")

        self.assertEqual(connection.cursor.call_count, 2)
        self.assertEqual(cursors[0].execute.call_args.args[0].strip(), "SELECT 1;")
        self.assertEqual(cursors[1].execute.call_args.args[0].strip(), "SELECT 2;")
        for cursor in cursors:
            cursor.close.assert_called_once_with()
        connection.commit.assert_called_once_with()

    def test_delimiters_inside_literals_and_comments_do_not_split(self) -> None:
        cursors = [mock.MagicMock(), mock.MagicMock()]
        connection = mock.Mock()
        connection.cursor.side_effect = cursors
        script = (
            "INSERT INTO items(value) VALUES ('a;b');\n"
            "/* comment ; remains attached to the next statement */\n"
            'SELECT "c;d";\n'
        )

        ScriptRunner(connection).run_script(script)

        self.assertEqual(connection.cursor.call_count, 2)
        self.assertIn("'a;b'", cursors[0].execute.call_args.args[0])
        self.assertIn("comment ;", cursors[1].execute.call_args.args[0])
        self.assertIn('"c;d"', cursors[1].execute.call_args.args[0])

    def test_mysql_double_minus_operator_is_not_a_comment(self) -> None:
        cursors = [mock.MagicMock(), mock.MagicMock()]
        connection = mock.Mock()
        connection.cursor.side_effect = cursors

        ScriptRunner(connection).run_script("SELECT 1--1; SELECT 2;")

        self.assertEqual(connection.cursor.call_count, 2)
        self.assertEqual(cursors[0].execute.call_args.args[0], "SELECT 1--1;")
        self.assertEqual(cursors[1].execute.call_args.args[0].strip(), "SELECT 2;")

    def test_mysql_line_comment_requires_following_whitespace(self) -> None:
        cursor = mock.MagicMock()
        connection = mock.Mock()
        connection.cursor.return_value = cursor

        ScriptRunner(connection).run_script("-- comment ; ignored\nSELECT 1;")

        cursor.execute.assert_called_once()
        self.assertIn("-- comment ; ignored", cursor.execute.call_args.args[0])
        self.assertIn("SELECT 1;", cursor.execute.call_args.args[0])

    def test_mysql_executable_version_comment_is_executed(self) -> None:
        cursor = mock.MagicMock()
        connection = mock.Mock()
        connection.cursor.return_value = cursor
        executable_comment = (
            "/*!40101 SET @OLD_CHARACTER_SET_CLIENT="
            "@@CHARACTER_SET_CLIENT */;"
        )

        ScriptRunner(connection).run_script(executable_comment)

        cursor.execute.assert_called_once_with(executable_comment)
        cursor.close.assert_called_once_with()

    def test_custom_delimiter_preserves_internal_semicolons(self) -> None:
        cursor = mock.MagicMock()
        connection = mock.Mock()
        connection.cursor.return_value = cursor
        script = (
            "DELIMITER //\n"
            "CREATE PROCEDURE example()\n"
            "BEGIN\n"
            "    SELECT 'first;value';\n"
            "    SELECT 2;\n"
            "END//\n"
            "DELIMITER ;\n"
        )

        ScriptRunner(connection).run_script(script)

        executed_statement = cursor.execute.call_args.args[0]
        self.assertIn("SELECT 'first;value';", executed_statement)
        self.assertIn("SELECT 2;", executed_statement)
        self.assertTrue(executed_statement.endswith("END;"))
        cursor.close.assert_called_once_with()

    def test_delimiter_must_be_non_empty_token(self) -> None:
        connection = mock.Mock()

        with self.assertRaisesRegex(ValueError, "delimiter"):
            ScriptRunner(connection, delimiter="")
        with self.assertRaisesRegex(ValueError, "DELIMITER"):
            ScriptRunner(connection).run_script("DELIMITER\n")


if __name__ == "__main__":
    unittest.main()
