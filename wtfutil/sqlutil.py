# encoding: utf-8
import logging
import sqlite3
import threading
import time
import uuid
import warnings
import weakref
from abc import ABC, abstractmethod
from contextlib import closing
from typing import List, Dict, Union, Optional, Any

from pymysql import connect as pymysql_connect, cursors

# 日志配置
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)


class ScriptRunner:
    def __init__(self, connection, delimiter=";", autocommit=True):
        self.connection = connection
        self.delimiter = delimiter
        self.autocommit = autocommit

    def run_script(self, sql):
        try:
            script = ""
            for line in sql.splitlines():
                strip_line = line.strip()
                if "DELIMITER $$" in strip_line:
                    self.delimiter = "$$"
                    continue
                if "DELIMITER ;" in strip_line:
                    self.delimiter = ";"
                    continue
                if strip_line and not strip_line.startswith("//") and not strip_line.startswith("--"):
                    script += line + "\n"
                    if strip_line.endswith(self.delimiter):
                        if self.delimiter == "$$":
                            script = script[:-1].rstrip("$") + ";"
                        cursor = self.connection.cursor()
                        print(script)
                        cursor.execute(script)
                        script = ""
            if script.strip():
                raise Exception("Line missing end-of-line terminator (" + self.delimiter + ") => " + script)
            if not self.connection.get_autocommit():
                self.connection.commit()
        except Exception:
            if not self.connection.get_autocommit():
                self.connection.rollback()
            raise


class Dict(dict):
    """
    Simple dict but support access as x.y style.
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

    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value


def next_id(t=None):
    """
    Return next id as 50-char string.
    Args:
        t: unix timestamp, default to None and using time.time().
    """
    if t is None:
        t = time.time()
    return '%015d%s000' % (int(t * 1000), uuid.uuid4().hex)


def join_field_value(data, glue=', '):
    sql = comma = ''
    for key in data.keys():
        sql += "{}`{}` = ?".format(comma, key)
        comma = glue
    return sql


def join_field(data, glue=', '):
    sql = comma = ''
    for key in data.keys():
        sql += "{}`{}`".format(comma, key)
        comma = glue
    return sql


def join_value(data, glue=', '):
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
        :return: 最后插入的记录 ID
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

    # 旧方法重定向，保持向后兼容
    def fetch_rows(self, table: str, fields=None, condition=None, order=None, limit=None, fetchone=False):
        warnings.warn("fetch_rows is deprecated, use select instead", DeprecationWarning)
        if fetchone:
            return self.select_one(table, columns=fields, where_clause=condition, order=order, limit=limit)
        return self.select(table, columns=fields, where_clause=condition, order=order, limit=limit)

    def fetchone(self, table: str, fields=None, condition=None, order=None, limit=None):
        warnings.warn("fetchone is deprecated, use select_one instead", DeprecationWarning)
        return self.select_one(table, columns=fields, where_clause=condition, order=order, limit=limit)

    def bulk_insert(self, table: str, data_list: List[Dict[str, Any]]):
        warnings.warn("bulk_insert is deprecated, use insert_many instead", DeprecationWarning)
        return self.insert_many(table, records=data_list)

    def replace(self, table: str, data: Dict[str, Any]):
        warnings.warn("replace is deprecated, use insert_or_replace instead", DeprecationWarning)
        return self.insert_or_replace(table, record=data)

    def exists(self, table: str, condition: Union[Dict[str, Any], str]):
        warnings.warn("exists is deprecated, use record_exists instead", DeprecationWarning)
        return self.record_exists(table, where_clause=condition)

    def fetch_by_id(self, table: str, id_value: Union[int, str], fields=None):
        warnings.warn("fetch_by_id is deprecated, use select_by_id instead", DeprecationWarning)
        return self.select_by_id(table, id_value, columns=fields)


class SQLite(Database):
    """SQLite 数据库连接工具类，支持线程安全的操作

    支持与原生 cursor.execute 相似的调用方式：
    - 位置参数：db.execute("SELECT * FROM users WHERE id = ?", 1)
    - 命名参数：db.execute("SELECT * FROM users WHERE id = :id", id=1)
    """

    _thread_local = threading.local()

    def __init__(self, db_file: str):
        self.db_file = db_file

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._thread_local, "conn"):
            self._thread_local.conn = sqlite3.connect(self.db_file)
            weakref.finalize(self._thread_local, self.close)
        return self._thread_local.conn

    def _build_where_clause(self, where_clause: Union[Dict[str, Any], str, None], params: List[Any]) -> str:
        """构建 WHERE 子句并填充参数"""
        if not where_clause:
            return "1"
        elif isinstance(where_clause, dict):
            where = " AND ".join(f"`{k}` = ?" for k in where_clause.keys())
            params.extend(where_clause.values())
            return where
        return where_clause

    def insert(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict):
            raise TypeError("Record must be a dictionary")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    columns = ", ".join(f"`{k}`" for k in record.keys())
                    placeholders = ", ".join("?" * len(record))
                    sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                    cursor.execute(sql, tuple(record.values()))
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert: {e}")
            raise

    def insert_or_replace(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict):
            raise TypeError("Record must be a dictionary")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    columns = ", ".join(f"`{k}`" for k in record.keys())
                    placeholders = ", ".join("?" * len(record))
                    sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
                    logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                    cursor.execute(sql, tuple(record.values()))
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert_or_replace: {e}")
            raise

    def insert_many(self, table: str, records: List[Dict[str, Any]]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(records, list) or not records:
            raise TypeError("Records must be a non-empty list of dictionaries")
        conn = self._get_connection()
        try:
            with conn:
                with closing(conn.cursor()) as cursor:
                    columns = ", ".join(f"`{k}`" for k in records[0].keys())
                    placeholders = ", ".join("?" * len(records[0]))
                    sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                    values = [tuple(record.values()) for record in records]
                    logger.debug(f"SQL: {sql} -- Params: {values}")
                    cursor.executemany(sql, values)
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert_many: {e}")
            raise

    def update(self, table: str, record: Dict[str, Any], where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict):
            raise TypeError("Record must be a dictionary")
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
        conn = getattr(self._thread_local, "conn", None)
        if conn:
            conn.close()
            del self._thread_local.conn

    def __del__(self):
        self.close()


class MYSQL(Database):
    """MySQL 数据库连接工具类，提供 CRUD 功能

    支持与原生 cursor.execute 相似的调用方式：
    - 位置参数：db.execute("SELECT * FROM users WHERE id = %s", 1)
    - 命名参数：db.execute("SELECT * FROM users WHERE id = %(id)s", id=1)
    """

    def __init__(self, host: str, user: str, password: str, database: str, charset: str = "utf8mb4", port: int = 3306, ssl=None):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.port = int(port)
        self.ssl = ssl
        self.connection = None
        self.closed = False

    def _get_connection(self) -> pymysql_connect:
        if not self.connection or self.closed:
            self.connection = pymysql_connect(
                host=self.host, user=self.user, password=self.password,
                database=self.database, charset=self.charset, port=self.port,
                cursorclass=cursors.DictCursor,
                ssl=self.ssl
            )
            self.closed = False
        return self.connection

    def _build_where_clause(self, where_clause: Union[Dict[str, Any], str, None], params: List[Any]) -> str:
        if not where_clause:
            return "1"
        elif isinstance(where_clause, dict):
            where = " AND ".join(f"`{k}` = %s" for k in where_clause.keys())
            params.extend(where_clause.values())
            return where
        return where_clause

    def insert(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict):
            raise TypeError("Record must be a dictionary")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                columns = ", ".join(f"`{k}`" for k in record.keys())
                placeholders = ", ".join("%s" * len(record))
                sql = f"INSERT IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                cursor.execute(sql, tuple(record.values()))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert: {e}")
            raise

    def insert_or_replace(self, table: str, record: Dict[str, Any]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict):
            raise TypeError("Record must be a dictionary")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                set_clause = ", ".join(f"`{k}` = %s" for k in record.keys())
                sql = f"REPLACE INTO {table} SET {set_clause}"
                logger.debug(f"SQL: {sql} -- Params: {tuple(record.values())}")
                cursor.execute(sql, tuple(record.values()))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert_or_replace: {e}")
            raise

    def insert_many(self, table: str, records: List[Dict[str, Any]]) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(records, list) or not records:
            raise TypeError("Records must be a non-empty list of dictionaries")
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                columns = ", ".join(f"`{k}`" for k in records[0].keys())
                placeholders = ", ".join("%s" * len(records[0]))
                sql = f"INSERT IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                values = [tuple(record.values()) for record in records]
                logger.debug(f"SQL: {sql} -- Params: {values}")
                cursor.executemany(sql, values)
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error in insert_many: {e}")
            raise

    def update(self, table: str, record: Dict[str, Any], where_clause: Union[Dict[str, Any], str, None] = None) -> int:
        if not table:
            raise ValueError("Table name cannot be empty")
        if not isinstance(record, dict):
            raise TypeError("Record must be a dictionary")
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
                conn.commit()
                return cursor.rowcount
        except Exception as e:
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
                conn.commit()
                return cursor.rowcount
        except Exception as e:
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
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
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
