# wtfutil.sqlutil

`SQLite` / `MYSQL` 封装、`Database` 抽象、`ScriptRunner`、SQL 拼接辅助。

```python
from wtfutil.sqlutil import MYSQL, SQLite, next_id
```

## 默认事务行为

本模块默认自动提交，常规调用不需要手动执行 `commit()`：

- `SQLite` 的每个公开数据库操作都会在成功后自动提交，发生异常时自动回滚。
- `MYSQL(...)` 默认使用 `autocommit=True`；`insert()`、`insert_or_replace()`、`insert_many()`、`update()`、`delete()` 和 `execute()` 成功后会自动提交，失败时自动回滚。
- `ScriptRunner(...)` 默认使用 `autocommit=True`；整段脚本成功后提交，执行失败时回滚。

只有需要把多个 MySQL 操作放进同一个事务时，才传入 `autocommit=False`，并在最后显式调用 `commit()` 或 `rollback()`。

## 示例

### SQLite：建表与 CRUD

```python
from wtfutil.sqlutil import SQLite, next_id

db = SQLite("data.db")
db.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        url TEXT,
        status INTEGER DEFAULT 0
    )
""")

db.insert("items", {"id": next_id(), "url": "https://a.com", "status": 0})
db.insert_many("items", [
    {"id": next_id(), "url": u, "status": 0}
    for u in ["https://b.com", "https://c.com"]
])

row = db.select_one("items", where_clause={"url": "https://a.com"})
rows = db.select("items", where_clause={"status": 0}, order="id DESC", limit=10)
by_id = db.select_by_id("items", row["id"])

db.update("items", {"status": 1}, where_clause={"url": "https://a.com"})
db.delete("items", where_clause={"status": 0})
print(db.record_exists("items", {"url": "https://a.com"}))
db.close()
```

### 原始 SQL

```python
db.query("SELECT * FROM items WHERE status > ?", 0)
db.get("SELECT * FROM items WHERE id = ?", item_id)
```

### MySQL（API 与 SQLite 相同）

```python
# 默认 autocommit=True，写入成功后无需手动调用 commit()。
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "x1", "url": "https://d.com", "status": 0})

# 需要自行控制事务时关闭自动提交，最后通过公开方法提交或回滚。
transactional_db = MYSQL(
    host="127.0.0.1",
    user="root",
    password="pass",
    database="mydb",
    autocommit=False,
)
transactional_db.insert("items", {"id": "x2", "url": "https://e.com"})
transactional_db.commit()
```

### 辅助函数

```python
from wtfutil.sqlutil import join_field, join_field_value, join_value, next_id

rid = next_id()
# join_* 用于手写 SQL 片段
```

## 类

| 符号 | 说明 |
|------|------|
| `Dict` | 支持 `d.key` 访问的 dict |
| `Database` | 抽象 CRUD |
| `SQLite` | `SQLite(db_file)` |
| `MYSQL` | `MYSQL(host, user, password, database, ...)` |
| `ScriptRunner` | 多语句脚本（含简单 `DELIMITER`） |

## 常用方法

| 方法 | 用途 |
|------|------|
| `insert` / `insert_or_replace` / `insert_many` | 插入 |
| `update` / `delete` | 更新 / 删除 |
| `select` / `select_one` / `select_by_id` | 查询 |
| `count` / `record_exists` | 计数 / 是否存在 |
| `execute` / `query` / `get` | 原始 SQL |
| `close` | 关闭连接 |

占位符与返回类型见 `wtfutil/sqlutil.py` 源码 docstring。

每个 `SQLite` 实例维护一个连接；同一实例的公开操作会串行执行，因此工作线程可以安全共享该连接，`close()` 会等待正在执行的操作完成。`SQLite(":memory:")` 的同一实例在各线程中可访问相同数据，同时不会为已经结束的历史工作线程持续保留连接。

`insert_many()` 按首条记录的列顺序绑定每一行，字段集合不一致时抛出 `ValueError`，成功时返回实际插入行数。字典条件中的 `None` 会生成 SQL `IS NULL`。

`MYSQL(..., autocommit=True)` 是默认值，可避免只读调用长期保留隐式事务；设置为 `False` 后，写操作不再逐次提交或回滚，事务边界由调用方负责。

`ScriptRunner(..., autocommit=True)` 在脚本完成后提交，失败时回滚；`autocommit=False` 时事务完全交给调用方。支持一行内多条语句和 `DELIMITER //` 这类单一 token 分隔符。引号字符串、引号标识符、行注释和块注释中的分隔符不会拆开语句。MySQL 的 `--` 注释按服务端规则要求后接空白；MySQL/MariaDB 可执行版本注释（`/*!...*/` / `/*M!...*/`）会保留并执行。自定义终止符会在执行前归一为 `;`。每条语句的 cursor 都会在执行后立即关闭。

## SQL 辅助函数

| 符号 | 用途 |
|------|------|
| `next_id(timestamp=None)` | 生成由时间戳和 UUID 组成的标识符 |
| `join_field_value(mapping, glue=", ")` | 生成反引号包裹的 `字段 = ?` 赋值列表 |
| `join_field(mapping, glue=", ")` | 生成反引号包裹的字段列表 |
| `join_value(mapping, glue=", ")` | 按值数量生成 `?` 占位符列表 |
