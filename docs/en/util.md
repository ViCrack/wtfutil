# wtfutil.util

Misc utilities: deduplicated queue, timing decorator, datetime helpers, list chunking, grouping, resource path resolution. `get_resource` / `get_resource_dir` are implemented in `wtfutil._base` and re-exported here and at package top level.

```python
from wtfutil import UniqueQueue, measure_time, get_resource
```

> For HTTP, files, notifications, etc., use `from wtfutil import requests_session, read_text, send` or import submodules (`httputil`, `fileutil`, …). **`util` does not re-export other submodules.**

## Symbol index

| Symbol | Description |
|--------|-------------|
| `UniqueQueue` | Queue that ignores duplicate items |
| `measure_time` | Decorator that prints execution time |
| `unique_items(iterable)` | Order-preserving deduplication |
| `current_datetime()` | `datetime.now()` |
| `format_datetime(dt, format=...)` | Format datetime to string |
| `parse_datetime(date_string, format=...)` | Parse datetime string |
| `cut_list(obj, size)` | Chunk list into sublists |
| `group_data(data, group_by, remove_duplicates=False)` | Group rows by column or dict key |
| `get_resource(filename)` | Resolve file: cwd → `resource/` → `~/filename` |
| `get_resource_dir(basedir=None)` | Walk up to directory containing `resource/` |

## Examples

```python
from wtfutil import UniqueQueue, measure_time, get_resource, read_lines

q = UniqueQueue()
q.put({"url": "https://a.com"})
q.put({"url": "https://a.com"})  # ignored

@measure_time
def heavy():
    ...

lines = read_lines(get_resource("blacklist.txt"), unique=True)
```
