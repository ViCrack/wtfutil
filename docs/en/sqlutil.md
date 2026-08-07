# wtfutil.sqlutil

`SQLite` / `MySQL` wrappers, `Database` abstraction, `ScriptRunner`, SQL helpers.

```python
from wtfutil.sqlutil import MYSQL, SQLite, next_id
```

## Default transaction behavior

The module commits automatically by default, so normal calls do not require an explicit `commit()`:

- Every public `SQLite` database operation commits on success and rolls back on failure.
- `MYSQL(...)` defaults to `autocommit=True`; successful `insert()`, `insert_or_replace()`, `insert_many()`, `update()`, `delete()`, and `execute()` calls commit automatically and failures roll back automatically.
- `ScriptRunner(...)` defaults to `autocommit=True`; it commits after the complete script succeeds and rolls back when execution fails.

Pass `autocommit=False` only when several MySQL operations must share one caller-managed transaction, then call `commit()` or `rollback()` explicitly.

## Examples

### SQLite: schema and CRUD

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

### Raw SQL

```python
db.query("SELECT * FROM items WHERE status > ?", 0)
db.get("SELECT * FROM items WHERE id = ?", item_id)
```

### MySQL (same API)

```python
# autocommit=True by default; successful writes need no explicit commit().
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "x1", "url": "https://d.com", "status": 0})

# Disable automatic commits when the caller owns transaction boundaries.
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

## Classes

| Symbol | Description |
|--------|-------------|
| `Dict` | `dict` with attribute access |
| `Database` | Abstract CRUD |
| `SQLite` | `SQLite(db_file)` |
| `MYSQL` | `MYSQL(host, user, password, database, ...)` |
| `ScriptRunner` | Multi-statement scripts |

## Common methods

| Methods | Purpose |
|---------|---------|
| `insert`, `insert_or_replace`, `insert_many` | Insert |
| `update`, `delete` | Update / delete |
| `select`, `select_one`, `select_by_id` | Query |
| `count`, `record_exists` | Count / exists |
| `execute`, `query`, `get` | Raw SQL |
| `close` | Close connection |

Each `SQLite` instance owns one connection. Its public operations are serialized, so worker threads can safely share that connection and `close()` waits for an active operation to finish. `SQLite(":memory:")` therefore exposes the same in-memory data to every thread using that instance without retaining one connection per historical worker thread. `insert_many` binds every row according to the first record's column order, returns the number of inserted rows, and raises `ValueError` when column sets differ. Dictionary filters map `None` to SQL `IS NULL`. MySQL write failures roll back before re-raising. The module does not install logging handlers; applications control logging configuration.

`MYSQL(..., autocommit=True)` is the default and prevents read-only calls from retaining implicit transactions. Set it to `False` to manage transaction boundaries yourself with `commit()` and `rollback()`.

`ScriptRunner(..., autocommit=True)` commits the completed script and rolls back on failure; `autocommit=False` leaves transaction ownership to the caller. Multiple statements on one line and token-style `DELIMITER` directives such as `DELIMITER //` are supported. Delimiters inside quoted strings, quoted identifiers, line comments, and block comments do not split a statement. MySQL `--` comments follow the server rule that requires following whitespace, while MySQL/MariaDB executable version comments (`/*!...*/` / `/*M!...*/`) are preserved and executed. Custom terminators are normalized to `;` before execution. Each statement cursor is closed immediately after execution.

## SQL helper functions

| Symbol | Purpose |
|--------|---------|
| `next_id(timestamp=None)` | Build a timestamp-and-UUID identifier |
| `join_field_value(mapping, glue=", ")` | Build backtick-quoted `field = ?` assignments |
| `join_field(mapping, glue=", ")` | Build a backtick-quoted field list |
| `join_value(mapping, glue=", ")` | Build a placeholder list with one `?` per value |

See source docstrings for placeholders and return types.
