# wtfutil.sqlutil

`SQLite` / `MySQL` wrappers, `Database` abstraction, `ScriptRunner`, SQL helpers.

```python
from wtfutil import SQLite, MYSQL, next_id
```

## Classes

| Symbol | Description |
|--------|-------------|
| `Dict` | `dict` with attribute access (`d.key`) |
| `Database` | Abstract CRUD / query interface |
| `SQLite` | `SQLite(db_file: str)` |
| `MYSQL` | `MYSQL(host, user, password, database, charset='utf8mb4', port=3306, ssl=None)` |
| `ScriptRunner` | Multi-statement scripts with basic `DELIMITER` support |

## Database method reference

| Methods | Purpose |
|---------|---------|
| `insert`, `insert_or_replace`, `insert_many`, `bulk_insert` | Insert rows |
| `update`, `delete` | Conditional update/delete |
| `select`, `select_one`, `select_by_id`, `fetch_rows`, `fetchone`, `fetch_by_id` | Queries |
| `count`, `exists`, `record_exists` | Count / existence |
| `execute`, `query` | Raw SQL |
| `get`, `replace` | Get or replace by primary key |
| `close` | Close connection |

See source docstrings on `Database`, `SQLite`, and `MYSQL` for placeholders and return types.

## Helper functions

| Symbol | Description |
|--------|-------------|
| `next_id(t=None)` | ~50-char ID (timestamp + UUID) |
| `join_field_value(data)` | `UPDATE SET` fragment |
| `join_field(data)` | Column list |
| `join_value(data)` | Value placeholders |
