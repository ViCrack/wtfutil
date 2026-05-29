# wtfutil.sqlutil

`SQLite` / `MYSQL` 封装、`Database` 抽象、`ScriptRunner`、SQL 拼接辅助。

```python
from wtfutil import SQLite, MYSQL, next_id
```

## 类

| 符号 | 说明 |
|------|------|
| `Dict` | 支持 `d.key` 访问的 dict 子类 |
| `Database` | 抽象基类，通用 CRUD / 查询 |
| `SQLite` | `SQLite(db_file: str)` |
| `MYSQL` | `MYSQL(host, user, password, database, charset='utf8mb4', port=3306, ssl=None)` |
| `ScriptRunner` | `run_script(sql)`：多语句脚本（含简单 `DELIMITER`） |

## Database 方法参考

| 方法 | 用途 |
|------|------|
| `insert` / `insert_or_replace` / `insert_many` / `bulk_insert` | 插入单行、冲突替换、批量插入 |
| `update` / `delete` | 按条件更新、删除 |
| `select` / `select_one` / `select_by_id` / `fetch_rows` / `fetchone` / `fetch_by_id` | 查询多行、单行、按 id |
| `count` / `exists` / `record_exists` | 计数与存在性判断 |
| `execute` / `query` | 执行原始 SQL |
| `get` / `replace` | 按主键获取或替换 |
| `close` | 关闭连接 |

占位符风格与返回类型（`Dict` 行等）见 `wtfutil/sqlutil.py` 中 `Database` / `SQLite` / `MYSQL` 的 docstring。

## 辅助函数

| 符号 | 说明 |
|------|------|
| `next_id(t=None)` | 约 50 字符 ID（时间 + UUID） |
| `join_field_value(data)` | `UPDATE SET` 片段 |
| `join_field(data)` | 列名列表 |
| `join_value(data)` | 值占位符列表 |
