# wtfutil.sqlutil

`SQLite` / `MYSQL` 封装、`Database` 抽象、`ScriptRunner`、SQL 拼接辅助。

```python
from wtfutil.sqlutil import MYSQL, SQLite, next_id
```

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
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "x1", "url": "https://d.com", "status": 0})

# 需要自行控制事务时关闭自动提交，最后直接使用底层连接提交或回滚。
transactional_db = MYSQL(
    host="127.0.0.1",
    user="root",
    password="pass",
    database="mydb",
    autocommit=False,
)
transactional_db.insert("items", {"id": "x2", "url": "https://e.com"})
transactional_db._get_connection().commit()
```

### 辅助函数

```python
from wtfutil.sqlutil import join_field, join_value, next_id

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

每个 `SQLite` 实例维护自己的线程局部连接；同一实例的公开操作会串行执行，`close()` 会等待正在执行的操作完成，再关闭所有工作线程连接。`SQLite(":memory:")` 使用实例独立的共享内存 URI，因此同一实例的不同线程能访问相同数据。

`MYSQL(..., autocommit=True)` 是默认值，可避免只读调用长期保留隐式事务；设置为 `False` 后，写操作不再逐次提交或回滚，事务边界由调用方负责。

`ScriptRunner(..., autocommit=True)` 在脚本完成后提交，失败时回滚；`autocommit=False` 时事务完全交给调用方。每条语句的 cursor 都会在执行后立即关闭。
