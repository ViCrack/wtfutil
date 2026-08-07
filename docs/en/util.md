# wtfutil.util

Misc utilities: lifetime-deduplicated queue, timing decorator, datetime helpers, list chunking, grouping, and resource path resolution. `wtfutil.util` is the only public owner of `get_resource` / `get_resource_dir`; private implementation modules are not part of the API contract.

```python
from wtfutil.util import UniqueQueue, get_resource, measure_time
```

> For HTTP, files, and notifications, import from the owning modules: `wtfutil.httputil`, `wtfutil.fileutil`, and `wtfutil.notifyutil`. **`util` does not aggregate other submodules.**

## Symbol index

| Symbol | Description |
|--------|-------------|
| `UniqueQueue` | Queue that ignores equivalent items for its lifetime, including nested containers |
| `measure_time` | Decorator that prints execution time |
| `unique_items(iterable)` | Order-preserving deduplication |
| `current_datetime()` | `datetime.now()` |
| `format_datetime(dt, format=...)` | Format datetime to string |
| `parse_datetime(date_string, format=...)` | Parse datetime string |
| `cut_list(obj, size)` | Chunk list into sublists |
| `group_data(data, group_by, remove_duplicates=False)` | Group rows by column or dict key |
| `get_resource(filename, basedir=None)` | Resolve file: cwd → project `resource/` → `~/filename`; optional explicit search anchor |
| `get_resource_dir(basedir=None)` | Walk up to directory containing `resource/` |

## Examples

```python
from wtfutil.fileutil import read_lines
from wtfutil.util import UniqueQueue, cut_list, get_resource, group_data, measure_time

q = UniqueQueue()
q.put({"url": "https://a.com"})
q.put({"url": "https://a.com"})  # ignored for this queue's lifetime

resource_path = get_resource("blacklist.txt")
if resource_path is None:
    raise FileNotFoundError("blacklist.txt")
lines = read_lines(resource_path, unique=True)
for batch in cut_list(lines, 50):
    process(batch)

group_data([{"status": 0}, {"status": 1}], group_by="status")

@measure_time
def heavy():
    ...
```
