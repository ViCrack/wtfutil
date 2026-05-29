# wtfutil.sqlutil

`SQLite` / `MySQL` wrappers, `Database` abstraction, `ScriptRunner`, SQL helpers.

```python
from wtfutil import SQLite, MYSQL, next_id
```

## Examples

### SQLite: schema and CRUD

```python
from wtfutil import SQLite, next_id

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
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "x1", "url": "https://d.com", "status": 0})
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

See source docstrings for placeholders and return types.
