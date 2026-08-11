# encoding: utf-8
import logging
import sqlite3
import threading
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import closing
from functools import wraps
from typing import Any, Dict, List, Optional, Union

from pymysql import connect as pymysql_connect
from pymysql import cursors

logger = logging.getLogger(__name__)


def _prepare_record_batch(
    records: List[Dict[str, Any]],
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """校验批量记录字段一致，并按首条记录的列顺序构建参数。"""
    if not isinstance(records, list) or not records:
        raise TypeError("Records must be a non-empty list of dictionaries")
    if not isinstance(records[0], dict) or not records[0]:
        raise TypeError("Each record must be a non-empty dictionary")

    column_names = list(records[0].keys())
    expected_columns = set(column_names)
    values: list[tuple[Any, ...]] = []

    for record_index, record in enumerate(records):
        if not isinstance(record, dict) or not record:
            raise TypeError(
                f"Record at index {record_index} must be a non-empty dictionary"
            )
        if set(record.keys()) != expected_columns:
            raise ValueError(
                f"Record at index {record_index} has inconsistent columns"
            )
        values.append(tuple(record[column_name] for column_name in column_names))

    return column_names, values


def _serialize_sqlite_operation(function):
    """串行化同一 SQLite 实例的操作，使 ``close`` 不会中途关闭连接。"""
    @wraps(function)
    def wrapper(database, *args, **kwargs):
        with database._operation_lock:
            return function(database, *args, **kwargs)

    return wrapper


class ScriptRunner:
    def __init__(self, connection: Any, delimiter: str = ";", autocommit: bool = True) -> None:
        if not delimiter or any(character.isspace() for character in delimiter):
            raise ValueError("delimiter must be a non-empty token without whitespace")
        self.connection = connection
        self.delimiter = delimiter
        self.autocommit = autocommit

    @staticmethod
    def _starts_mysql_line_comment(statement: str, character_index: int) -> bool:
        """Return whether ``--`` begins a MySQL line comment at this position."""
        if not statement.startswith("--", character_index):
            return False
        following_character_index = character_index + 2
        if following_character_index >= len(statement):
            return True
        return ord(statement[following_character_index]) <= 32

    @staticmethod
    def _starts_executable_block_comment(
        statement: str,
        character_index: int,
    ) -> bool:
        """Recognize MySQL and MariaDB executable version comments."""
        return statement.startswith("/*!", character_index) or statement.startswith(
            "/*M!",
            character_index,
        )

    @staticmethod
    def _has_executable_content(statement: str) -> bool:
        """Return whether a statement contains content other than comments."""
        character_index = 0
        parser_state = "normal"
        while character_index < len(statement):
            current_character = statement[character_index]
            next_character = (
                statement[character_index + 1]
                if character_index + 1 < len(statement)
                else ""
            )

            if parser_state == "normal":
                if current_character.isspace():
                    character_index += 1
                    continue
                if ScriptRunner._starts_mysql_line_comment(
                    statement,
                    character_index,
                ):
                    parser_state = "line_comment"
                    character_index += 2
                    continue
                if current_character == "#":
                    parser_state = "line_comment"
                    character_index += 1
                    continue
                if current_character == "/" and next_character == "*":
                    if ScriptRunner._starts_executable_block_comment(
                        statement,
                        character_index,
                    ):
                        return True
                    parser_state = "block_comment"
                    character_index += 2
                    continue
                return True

            if parser_state == "line_comment":
                if current_character in "\r\n":
                    parser_state = "normal"
                character_index += 1
                continue

            if current_character == "*" and next_character == "/":
                parser_state = "normal"
                character_index += 2
            else:
                character_index += 1

        return False

    def _iter_statements(self, sql: str):
        """Yield terminated SQL statements without splitting literals or comments."""
        current_delimiter = self.delimiter
        statement_buffer: list[str] = []
        parser_state = "normal"

        for line in sql.splitlines(keepends=True):
            buffered_statement = "".join(statement_buffer)
            stripped_line = line.strip()
            delimiter_parts = stripped_line.split(maxsplit=1)
            is_delimiter_directive = (
                parser_state == "normal"
                and not self._has_executable_content(buffered_statement)
                and delimiter_parts
                and delimiter_parts[0].upper() == "DELIMITER"
            )
            if is_delimiter_directive:
                if len(delimiter_parts) != 2:
                    raise ValueError("DELIMITER must not be empty")
                new_delimiter = delimiter_parts[1].strip()
                if not new_delimiter or any(
                    character.isspace() for character in new_delimiter
                ):
                    raise ValueError(
                        "DELIMITER must be a non-empty token without whitespace"
                    )
                current_delimiter = new_delimiter
                self.delimiter = new_delimiter
                statement_buffer.clear()
                continue

            character_index = 0
            while character_index < len(line):
                current_character = line[character_index]
                next_character = (
                    line[character_index + 1]
                    if character_index + 1 < len(line)
                    else ""
                )

                if parser_state == "normal":
                    if line.startswith(current_delimiter, character_index):
                        statement = "".join(statement_buffer).rstrip()
                        statement_buffer.clear()
                        character_index += len(current_delimiter)
                        if self._has_executable_content(statement):
                            yield statement + ";"
                        continue
                    if current_character == "'":
                        parser_state = "single_quote"
                    elif current_character == '"':
                        parser_state = "double_quote"
                    elif current_character == "`":
                        parser_state = "backtick_quote"
                    elif self._starts_mysql_line_comment(line, character_index):
                        parser_state = "line_comment"
                        statement_buffer.extend((current_character, next_character))
                        character_index += 2
                        continue
                    elif current_character == "#":
                        parser_state = "line_comment"
                    elif current_character == "/" and next_character == "*":
                        parser_state = "block_comment"
                        statement_buffer.extend((current_character, next_character))
                        character_index += 2
                        continue
                    statement_buffer.append(current_character)
                    character_index += 1
                    continue

                if parser_state in {
                    "single_quote",
                    "double_quote",
                    "backtick_quote",
                }:
                    quote_character = {
                        "single_quote": "'",
                        "double_quote": '"',
                        "backtick_quote": "`",
                    }[parser_state]
                    statement_buffer.append(current_character)
                    if current_character == "\\" and next_character:
                        statement_buffer.append(next_character)
                        character_index += 2
                        continue
                    if current_character == quote_character:
                        if next_character == quote_character:
                            statement_buffer.append(next_character)
                            character_index += 2
                            continue
                        parser_state = "normal"
                    character_index += 1
                    continue

                if parser_state == "line_comment":
                    statement_buffer.append(current_character)
                    if current_character in "\r\n":
                        parser_state = "normal"
                    character_index += 1
                    continue

                statement_buffer.append(current_character)
                if current_character == "*" and next_character == "/":
                    statement_buffer.append(next_character)
                    parser_state = "normal"
                    character_index += 2
                else:
                    character_index += 1

        trailing_statement = "".join(statement_buffer)
        if self._has_executable_content(trailing_statement):
            raise ValueError(
                "Line missing end-of-line terminator ("
                + current_delimiter
                + ") => "
                + trailing_statement
            )

    def run_script(self, sql: str) -> None:
        """按当前分隔符拆分并执行 SQL 脚本。"""
        def execute_statement(statement: str) -> None:
            with closing(self.connection.cursor()) as cursor:
                logger.debug("SQL script statement: %s", statement)
                cursor.execute(statement)

        try:
            for statement in self._iter_statements(sql):
                execute_statement(statement)
            if self.autocommit:
                self.connection.commit()
        except Exception:
            if self.autocommit:
                self.connection.rollback()
            raise


class Dict(dict):
    """
    支持通过 ``value.key`` 形式访问键值的字典。
    >>> d1 = Dict()
    >>> d1['x'] = 100
    >>> d1.x
    100
    >>> d1.y = 200
    >>> d1['y']
    200
    >>> d2 = Dict(a=1, b=2, c='3')
    >>> d2.c
    '3'
    >>> d2['empty']
    Traceback (most recent call last):
        ...
    KeyError: 'empty'
    >>> d2.empty
    Traceback (most recent call last):
        ...
    AttributeError: 'Dict' object has no attribute 'empty'
    >>> d3 = Dict(('a', 'b', 'c'), (1, 2, 3))
    >>> d3.a
    1
    >>> d3.b
    2
    >>> d3.c
    3

    """

    def __init__(self, names: tuple[str, ...] = (), values: tuple[Any, ...] = (), **kw: Any) -> None:
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def next_id(t: float | None = None) -> str:
    """
    生成由毫秒时间戳和 UUID 组成的 50 位 ID。

    Args:
        t: Unix 时间戳；默认使用 ``time.time()``。
    """
    if t is None:
        t = time.time()
    return '%015d%s000' % (int(t * 1000), uuid.uuid4().hex)


def join_field_value(data: Dict[str, Any], glue: str = ', ') -> str:
    sql = comma = ''
    for key in data.keys():
        sql += "{}`{}` = ?".format(comma, key)
        comma = glue
    return sql


def join_field(data: Dict[str, Any], glue: str = ', ') -> str:
    sql = comma = ''
    for key in data.keys():
        sql += "{}`{}`".format(comma, key)
        comma = glue
    return sql


def join_value(data: Dict[str, Any], glue: str = ', ') -> str:
    sql = comma = ''
    for key in data.values():
        sql += "{}?".format(comma, key)
        comma = glue
    return sql


class Database(ABC):
    """数据库操作的抽象基类，定义通用的 CRUD 接口"""

    @abstractmethod
    def _get_connection(self):
        """获取数据库连接"""
        pass

    @abstractmethod
    def close(self):
        """关闭数据库连接"""
        pass

    def insert(self, table: str, record: Dict[str, Any]) -> int:
        """插入单条记录，忽略重复记录

        :param table: 表名
        :param record: 要插入的记录，字典形式
        :return: 插入的记录 ID
        """
        raise NotImplementedError

    def insert_or_replace(self, table: str, record: Dict[str, Any]) -> int:
        """插入或替换单条记录

        :param table: 表名
        :param record: 要插入或替换的记录，字典形式
        :return: 插入或替换的记录 ID
        """
        raise NotImplementedError

    def insert_many(self, table: str, records: List[Dict[str, Any]]) -> int:
        """批量插入记录，忽略重复记录

        :param table: 表名
        :param records: 要插入的记录列表，每个记录为字典
        :return: 实际插入的记录数
        """
        raise NotImplementedError

    def update(self, table: str, record: Dict[str, Any], where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        """更新记录，返回受影响的行数

        :param table: 表名
        :param record: 要更新的字段和值，字典形式
        :param where_clause: 更新条件，可以是字典或 SQL 字符串
        :return: 受影响的行数
        """
        raise NotImplementedError

    def delete(self, table: str, where_clause: Union[Dict[str, Any], str, None] = None, limit: Optional[int] = None) -> int:
        """删除记录，返回受影响的行数

        :param table: 表名
        :param where_clause: 删除条件，可以是字典或 SQL 字符串
        :param limit: 删除的记录数限制
        :return: 受影响的行数
        """
        raise NotImplementedError

    def count(self, table: str, where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        """统计符合条件的记录数

        :param table: 表名
        :param where_clause: 统计条件，可以是字典或 SQL 字符串
        :return: 记录数
        """
        raise NotImplementedError

    def select(self, table: str, columns: Union[List[str], str, None] = None, where_clause: Union[Dict[str, Any], str, None] = None,
               order: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """查询多条记录

        :param table: 表名
        :param columns: 要查询的列，列表或字符串，默认为所有列
        :param where_clause: 查询条件，可以是字典或 SQL 字符串
        :param order: 排序方式，例如 'id DESC'
        :param limit: 查询的记录数限制
        :return: 记录列表，每个记录为字典
        """
        raise NotImplementedError

    def select_one(self, table: str, columns: Union[List[str], str, None] = None, where_clause: Union[Dict[str, Any], str, None] = None,
                   order: Optional[str] = None, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """查询单条记录

        :param table: 表名
        :param columns: 要查询的列，列表或字符串，默认为所有列
        :param where_clause: 查询条件，可以是字典或 SQL 字符串
        :param order: 排序方式，例如 'id DESC'
        :param limit: 查询的记录数限制
        :return: 记录字典或 None
        """
        raise NotImplementedError

    def execute(self, sql: str, *params, **kwargs) -> int:
        """执行自定义 SQL，返回 lastrowid

        支持以下调用方式：
        - db.execute("INSERT INTO users (id, name) VALUES (?, ?)", 1, "Alice")
        - db.execute("INSERT INTO users (id, name) VALUES (:id, :name)", id=1, name="Alice")

        :param sql: SQL 语句
        :param params: 位置参数，例如 1, "Alice"
        :param kwargs: 命名参数，例如 id=1, name="Alice"
        :return: 最后插入的记录 ID
        """
        raise NotImplementedError

    def query(self, sql: str, *params, **kwargs) -> List[Dict[str, Any]]:
        """执行自定义查询，返回多条记录

        支持以下调用方式：
        - db.query("SELECT * FROM users WHERE id > ?", 1)
        - db.query("SELECT * FROM users WHERE id = :id", id=1)

        :param sql: SQL 语句
        :param params: 位置参数，例如 1
        :param kwargs: 命名参数，例如 id=1
        :return: 记录列表，每个记录为字典
        """
        raise NotImplementedError

    def get(self, sql: str, *params, **kwargs) -> Optional[Dict[str, Any]]:
        """执行自定义查询，返回单条记录

        支持以下调用方式：
        - db.get("SELECT * FROM users WHERE id = ?", 1)
        - db.get("SELECT * FROM users WHERE id = :id", id=1)

        :param sql: SQL 语句
        :param params: 位置参数，例如 1
        :param kwargs: 命名参数，例如 id=1
        :return: 记录字典或 None
        """
        raise NotImplementedError

    def record_exists(self, table: str, where_clause: Union[Dict[str, Any], str]) -> bool:
        """检查记录是否存在

        :param table: 表名
        :param where_clause: 查询条件，可以是字典或 SQL 字符串
        :return: True 如果记录存在，否则 False
        """
        return self.count(table, where_clause) > 0

    def select_by_id(self, table: str, id_value: Union[int, str], columns: Union[List[str], str, None] = None) -> Optional[Dict[str, Any]]:
        """根据 ID 查询记录

        :param table: 表名
        :param id_value: ID 值
        :param columns: 要查询的列，列表或字符串，默认为所有列
        :return: 记录字典或 None
        """
        where_clause = {"id": id_value}
        return self.select_one(table, columns, where_clause)


class SQLite(Database):
    """SQLite 数据库连接工具类，支持线程安全的操作

    每个公开数据库操作默认在成功后自动提交，发生异常时自动回滚。

    支持与原生 cursor.execute 相似的调用方式：
    - 位置参数：db.execute("SELECT * FROM users WHERE id = ?", 1)
    - 命名参数：db.execute("SELECT * FROM users WHERE id = :id", id=1)
    """

    def __init__(self, db_file: str):
        self.db_file = db_file
        self._connection_target = db_file
        self._connection_uses_uri = False
        if db_file == ":memory:":
            self._connection_target = (
                f"file:wtfutil-{uuid.uuid4().hex}?mode=memory&cache=shared"
            )
            self._connection_uses_uri = True
        self._operation_lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(
                self._connection_target,
                check_same_thread=False,
                uri=self._connection_uses_uri,
            )
        return self._connection

    def _build_where_clause(self, where_clause: Union[Dict[str, Any], str, None], params: List[Any]) -> str:
        """构建 WHERE 子句并填充参数"""
        if not where_clause:
            return "1"
        elif isinstance(where_clause, dict):
            expressions = []
            for column_name, column_value in where_clause.items():
                if column_value is None:
                    expressions.append(f"`{column_name}` IS NULL")
                else:
                    expressions.append(f"`{column_name}` = ?")
                    params.append(column_value)
            return " AND ".join(expressions)
        return where_clause

    @_serialize_sqlite_operation
    def insert(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict) or not record:
            raise TypeError("Record must be a non-empty dictionary")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    columns = ", ".join(f"`{k}`" for k in record.keys())
                    placeholders = ", ".join(["?"] * len(record))
                    sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                    cursor.execute(sql, tuple(record.values()))
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert: {e}")
            raise

    @_serialize_sqlite_operation
    def insert_or_replace(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict) or not record:
            raise TypeError("Record must be a non-empty dictionary")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    columns = ", ".join(f"`{k}`" for k in record.keys())
                    placeholders = ", ".join(["?"] * len(record))
                    sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                    cursor.execute(sql, tuple(record.values()))
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert_or_replace: {e}")
            raise

    @_serialize_sqlite_operation
    def insert_many(self, table: str, records: List[Dict[str, Any]]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        column_names, values = _prepare_record_batch(records)
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    columns = ", ".join(f"`{column_name}`" for column_name in column_names)
                    placeholders = ", ".join(["?"] * len(column_names))
                    sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                    logger.debug(f"SQL: {sql} -- Params: {values}")
                    cursor.executemany(sql, values)
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Error in insert_many: {e}")
            raise

    @_serialize_sqlite_operation
    def update(self, table: str, record: Dict[str, Any], where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict) or not record:
            raise TypeError("Record must be a non-empty dictionary")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    params = []
                    set_clause = ", ".join(f"`{k}` = ?" for k in record.keys())
                    params.extend(record.values())
                    where = self._build_where_clause(where_clause, params)
                    sql = f"UPDATE OR IGNORE {table} SET {set_clause} WHERE {where}"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                    cursor.execute(sql, tuple(params))
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Error in update: {e}")
            raise

    @_serialize_sqlite_operation
    def delete(self, table: str, where_clause: Union[Dict[str, Any], str, None] = None, limit: Optional[int] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    params = []
                    where = self._build_where_clause(where_clause, params)
                    limits = f"LIMIT {limit}" if limit else ""
                    sql = f"DELETE FROM {table} WHERE {where} {limits}"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                    cursor.execute(sql, tuple(params))
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Error in delete: {e}")
            raise

    @_serialize_sqlite_operation
    def count(self, table: str, where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    params = []
                    where = self._build_where_clause(where_clause, params)
                    sql = f"SELECT COUNT(*) as cnt FROM {table} WHERE {where}"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                    cursor.execute(sql, tuple(params))
                    return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error in count: {e}")
            raise

    @_serialize_sqlite_operation
    def select(self, table: str, columns: Union[List[str], str, None] = None, where_clause: Union[Dict[str, Any], str, None] = None,
               order: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._select(table, columns, where_clause, order, limit, fetchone=False)

    @_serialize_sqlite_operation
    def select_one(self, table: str, columns: Union[List[str], str, None] = None, where_clause: Union[Dict[str, Any], str, None] = None,
                   order: Optional[str] = None, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self._select(table, columns, where_clause, order, limit, fetchone=True)

    def _select(self, table: str, columns: Union[List[str], str, None], where_clause: Union[Dict[str, Any], str, None],
                order: Optional[str], limit: Optional[int], fetchone: bool) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        if not table:
            raise ValueError("Table name cannot be empty")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    params = []
                    columns_str = "*" if not columns else ", ".join(f"`{c}`" for c in columns) if isinstance(columns, list) else columns
                    where = self._build_where_clause(where_clause, params)
                    orderby = f"ORDER BY {order}" if order else ""
                    limits = f"LIMIT {limit}" if limit else ""
                    sql = f"SELECT {columns_str} FROM {table} WHERE {where} {orderby} {limits}"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                    cursor.execute(sql, tuple(params))
                    names = [x[0] for x in cursor.description]
                    if fetchone:
                        row = cursor.fetchone()
                        return dict(zip(names, row)) if row else None
                    else:
                        rows = cursor.fetchall()
                        return [dict(zip(names, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error in select: {e}")
            raise

    @_serialize_sqlite_operation
    def execute(self, sql: str, *params, **kwargs) -> int:
        """执行自定义 SQL，返回 lastrowid

        支持以下调用方式：
        - db.execute("INSERT INTO users (id, name) VALUES (?, ?)", 1, "Alice")
        - db.execute("INSERT INTO users (id, name) VALUES (:id, :name)", id=1, name="Alice")
        """
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    if params and kwargs:
                        raise ValueError("Cannot use both positional and keyword arguments")
                    args = params or kwargs
                    logger.debug(f"SQL: {sql} -- Params: {args if args else 'None'}")
                    cursor.execute(sql, args)
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in execute: {e}")
            raise

    @_serialize_sqlite_operation
    def query(self, sql: str, *params, **kwargs) -> List[Dict[str, Any]]:
        """执行自定义查询，返回多条记录

        支持以下调用方式：
        - db.query("SELECT * FROM users WHERE id > ?", 1)
        - db.query("SELECT * FROM users WHERE id = :id", id=1)
        """
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    if params and kwargs:
                        raise ValueError("Cannot use both positional and keyword arguments")
                    args = params or kwargs
                    logger.debug(f"SQL: {sql} -- Params: {args if args else 'None'}")
                    cursor.execute(sql, args)
                    names = [x[0] for x in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(names, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error in query: {e}")
            raise

    @_serialize_sqlite_operation
    def get(self, sql: str, *params, **kwargs) -> Optional[Dict[str, Any]]:
        """执行自定义查询，返回单条记录

        支持以下调用方式：
        - db.get("SELECT * FROM users WHERE id = ?", 1)
        - db.get("SELECT * FROM users WHERE id = :id", id=1)
        """
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    if params and kwargs:
                        raise ValueError("Cannot use both positional and keyword arguments")
                    args = params or kwargs
                    logger.debug(f"SQL: {sql} -- Params: {args if args else 'None'}")
                    cursor.execute(sql, args)
                    names = [x[0] for x in cursor.description]
                    row = cursor.fetchone()
                    return dict(zip(names, row)) if row else None
        except Exception as e:
            logger.error(f"Error in get: {e}")
            raise

    def close(self):
        with self._operation_lock:
            connection = self._connection
            self._connection = None
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    logger.debug("关闭 SQLite 连接失败", exc_info=True)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class MYSQL(Database):
    """MySQL 数据库连接工具类，提供 CRUD 功能

    ``autocommit=True`` 是默认值；写操作成功后自动提交，失败时自动回滚。
    设置为 ``False`` 时，由调用方通过 :meth:`commit` 和 :meth:`rollback`
    管理事务边界。

    支持与原生 cursor.execute 相似的调用方式：
    - 位置参数：db.execute("SELECT * FROM users WHERE id = %s", 1)
    - 命名参数：db.execute("SELECT * FROM users WHERE id = %(id)s", id=1)
    """

    def __init__(self, host: str, user: str, password: str, database: str, charset: str = "utf8mb4", port: int = 3306, ssl=None, autocommit: bool = True):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.port = int(port)
        self.ssl = ssl
        self.autocommit = autocommit
        self.connection = None
        self.closed = False

    def _get_connection(self) -> pymysql_connect:
        if not self.connection or self.closed:
            self.connection = pymysql_connect(
                host=self.host, user=self.user, password=self.password,
                database=self.database, charset=self.charset, port=self.port,
                cursorclass=cursors.DictCursor,
                ssl=self.ssl,
                autocommit=self.autocommit,
            )
            self.closed = False
        return self.connection

    def _build_where_clause(self, where_clause: Union[Dict[str, Any], str, None], params: List[Any]) -> str:
        if not where_clause:
            return "1"
        elif isinstance(where_clause, dict):
            expressions = []
            for column_name, column_value in where_clause.items():
                if column_value is None:
                    expressions.append(f"`{column_name}` IS NULL")
                else:
                    expressions.append(f"`{column_name}` = %s")
                    params.append(column_value)
            return " AND ".join(expressions)
        return where_clause

    def insert(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict) or not record:
            raise TypeError("Record must be a non-empty dictionary")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                columns = ", ".join(f"`{k}`" for k in record.keys())
                placeholders = ", ".join(["%s"] * len(record))
                sql = f"INSERT IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                cursor.execute(sql, tuple(record.values()))
                if self.autocommit:
                    conn.commit()
                return cursor.lastrowid
        except Exception as e:
            if self.autocommit:
                conn.rollback()
            logger.error(f"Error in insert: {e}")
            raise

    def insert_or_replace(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict) or not record:
            raise TypeError("Record must be a non-empty dictionary")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                set_clause = ", ".join(f"`{k}` = %s" for k in record.keys())
                sql = f"REPLACE INTO {table} SET {set_clause}"
                logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                cursor.execute(sql, tuple(record.values()))
                if self.autocommit:
                    conn.commit()
                return cursor.lastrowid
        except Exception as e:
            if self.autocommit:
                conn.rollback()
            logger.error(f"Error in insert_or_replace: {e}")
            raise

    def insert_many(self, table: str, records: List[Dict[str, Any]]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        column_names, values = _prepare_record_batch(records)
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                columns = ", ".join(f"`{column_name}`" for column_name in column_names)
                placeholders = ", ".join(["%s"] * len(column_names))
                sql = f"INSERT IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                logger.debug(f"SQL: {sql} -- Params: {values}")
                cursor.executemany(sql, values)
                if self.autocommit:
                    conn.commit()
                return cursor.rowcount
        except Exception as e:
            if self.autocommit:
                conn.rollback()
            logger.error(f"Error in insert_many: {e}")
            raise

    def update(self, table: str, record: Dict[str, Any], where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict) or not record:
            raise TypeError("Record must be a non-empty dictionary")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                params = []
                set_clause = ", ".join(f"`{k}` = %s" for k in record.keys())
                params.extend(record.values())
                where = self._build_where_clause(where_clause, params)
                sql = f"UPDATE IGNORE {table} SET {set_clause} WHERE {where}"
                logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                cursor.execute(sql, tuple(params))
                if self.autocommit:
                    conn.commit()
                return cursor.rowcount
        except Exception as e:
            if self.autocommit:
                conn.rollback()
            logger.error(f"Error in update: {e}")
            raise

    def delete(self, table: str, where_clause: Union[Dict[str, Any], str, None] = None, limit: Optional[int] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                params = []
                where = self._build_where_clause(where_clause, params)
                limits = f"LIMIT {limit}" if limit else ""
                sql = f"DELETE FROM {table} WHERE {where} {limits}"
                logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                cursor.execute(sql, tuple(params))
                if self.autocommit:
                    conn.commit()
                return cursor.rowcount
        except Exception as e:
            if self.autocommit:
                conn.rollback()
            logger.error(f"Error in delete: {e}")
            raise

    def count(self, table: str, where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                params = []
                where = self._build_where_clause(where_clause, params)
                sql = f"SELECT COUNT(*) as cnt FROM {table} WHERE {where}"
                logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                cursor.execute(sql, tuple(params))
                return cursor.fetchone()["cnt"]
        except Exception as e:
            logger.error(f"Error in count: {e}")
            raise

    def select(self, table: str, columns: Union[List[str], str, None] = None, where_clause: Union[Dict[str, Any], str, None] = None,
               order: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._select(table, columns, where_clause, order, limit, fetchone=False)

    def select_one(self, table: str, columns: Union[List[str], str, None] = None, where_clause: Union[Dict[str, Any], str, None] = None,
                   order: Optional[str] = None, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self._select(table, columns, where_clause, order, limit, fetchone=True)

    def _select(self, table: str, columns: Union[List[str], str, None], where_clause: Union[Dict[str, Any], str, None],
                order: Optional[str], limit: Optional[int], fetchone: bool) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        if not table:
            raise ValueError("Table name cannot be empty")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                params = []
                columns_str = "*" if not columns else ", ".join(f"`{c}`" for c in columns) if isinstance(columns, list) else columns
                where = self._build_where_clause(where_clause, params)
                orderby = f"ORDER BY {order}" if order else ""
                limits = f"LIMIT {limit}" if limit else ""
                sql = f"SELECT {columns_str} FROM {table} WHERE {where} {orderby} {limits}"
                logger.debug(f"SQL: {sql} -- Params: {tuple(params)}")
                cursor.execute(sql, tuple(params))
                if fetchone:
                    return cursor.fetchone()
                else:
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error in select: {e}")
            raise

    def execute(self, sql: str, *params, **kwargs) -> int:
        """执行自定义 SQL，返回 lastrowid

        支持以下调用方式：
        - db.execute("INSERT INTO users (id, name) VALUES (%s, %s)", 1, "Alice")
        - db.execute("INSERT INTO users (id, name) VALUES (%(id)s, %(name)s)", id=1, name="Alice")
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                if params and kwargs:
                    raise ValueError("Cannot use both positional and keyword arguments")
                args = params or kwargs
                logger.debug(f"SQL: {sql} -- Params: {args if args else 'None'}")
                cursor.execute(sql, args)
                if self.autocommit:
                    conn.commit()
                return cursor.lastrowid
        except Exception as e:
            if self.autocommit:
                conn.rollback()
            logger.error(f"Error in execute: {e}")
            raise

    def query(self, sql: str, *params, **kwargs) -> List[Dict[str, Any]]:
        """执行自定义查询，返回多条记录

        支持以下调用方式：
        - db.query("SELECT * FROM users WHERE id > %s", 1)
        - db.query("SELECT * FROM users WHERE id = %(id)s", id=1)
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                if params and kwargs:
                    raise ValueError("Cannot use both positional and keyword arguments")
                args = params or kwargs
                logger.debug(f"SQL: {sql} -- Params: {args if args else 'None'}")
                cursor.execute(sql, args)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error in query: {e}")
            raise

    def get(self, sql: str, *params, **kwargs) -> Optional[Dict[str, Any]]:
        """执行自定义查询，返回单条记录

        支持以下调用方式：
        - db.get("SELECT * FROM users WHERE id = %s", 1)
        - db.get("SELECT * FROM users WHERE id = %(id)s", id=1)
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                if params and kwargs:
                    raise ValueError("Cannot use both positional and keyword arguments")
                args = params or kwargs
                logger.debug(f"SQL: {sql} -- Params: {args if args else 'None'}")
                cursor.execute(sql, args)
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error in get: {e}")
            raise

    def commit(self) -> None:
        """提交由 ``autocommit=False`` 调用方管理的事务。"""
        self._get_connection().commit()

    def rollback(self) -> None:
        """回滚由 ``autocommit=False`` 调用方管理的事务。"""
        self._get_connection().rollback()

    def close(self):
        if self.connection and not self.closed:
            self.connection.close()
            self.closed = True

    def __del__(self):
        self.close()


__all__ = [
    # --- 类 ---
    'Dict',
    'Database',
    'SQLite',
    'MYSQL',
    'ScriptRunner',

    # --- 函数 ---
    'next_id',
    'join_field_value',
    'join_field',
    'join_value',
]

if __name__ == '__main__':
    db = MYSQL(host="", user="", password="", database="test", port=4000,
               ssl={'ssl': {'ssl_verify_peer': False}})
    rows = db.query("""
                SELECT
                  domain
                FROM
                  hostdata
                WHERE
                  (domain LIKE '%%.com' OR domain LIKE '%%.cn')
                  AND `rank` = 0
                  AND company = ''
                  AND LENGTH(domain) > 10
                ORDER BY
                  RAND()
                  LIMIT %s
            """, 1)

    print(rows)
