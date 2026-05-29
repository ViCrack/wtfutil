# wtfutil.util

杂项工具：去重队列、计时装饰器、日期时间、列表切块、分组、资源路径解析。`get_resource` / `get_resource_dir` 实现在 `wtfutil._base`，经本模块与包顶层 re-export。

```python
from wtfutil import util
# 或
from wtfutil import UniqueQueue, measure_time, get_resource
```

> HTTP、文件、通知等能力请使用 `from wtfutil import requests_session, read_text, send` 或 `from wtfutil import httputil, fileutil, ...`，**不要**假定 `util` 聚合了其它子模块。

## 符号索引

| 符号 | 说明 |
|------|------|
| `UniqueQueue` | 去重队列 |
| `measure_time` | 计时装饰器 |
| `unique_items` | 保序去重 |
| `current_datetime` / `format_datetime` / `parse_datetime` | 日期时间 |
| `cut_list` / `group_data` | 列表切块与分组 |
| `get_resource_dir` / `get_resource` | 资源路径解析 |

## UniqueQueue

`queue.Queue` 子类；同一对象（或等价 dict）重复 `put` 会忽略。

```python
from wtfutil import UniqueQueue

q = UniqueQueue()
q.put({"url": "https://a.com"})
q.put({"url": "https://a.com"})  # dict 内容相同 → 忽略
```

## measure_time

装饰器：打印被装饰函数的执行耗时（秒）。

## 函数

| 符号 | 说明 |
|------|------|
| `unique_items(iterable)` | 保序去重 |
| `current_datetime()` | `datetime.now()` |
| `format_datetime(dt, format=...)` | 格式化时间 |
| `parse_datetime(date_string, format=...)` | 解析时间字符串 |
| `cut_list(obj, size)` | 列表按固定长度切片成二维列表 |
| `group_data(data, group_by, remove_duplicates=False)` | 按列索引或 dict 键分组；可选组内去重 |
| `get_resource_dir(basedir=None)` | 向上查找含 `resource` 目录的路径 |
| `get_resource(filename)` | 解析资源文件：当前路径 → `resource/` → `~/filename` |

**`get_resource` 示例**：配置文件、黑名单等与脚本相对位置无关时，把文件放在 `resource/` 或用户家目录即可被找到（常与 [fileutil.read_lines](fileutil.md) 联用）。

```python
from wtfutil import get_resource, read_lines, cut_list, group_data, measure_time

path = get_resource("blacklist.txt")
lines = read_lines(path, unique=True)

for batch in cut_list(lines, 50):
    process(batch)

rows = [{"status": 0, "url": "a"}, {"status": 1, "url": "b"}]
group_data(rows, group_by="status")

@measure_time
def job():
    ...
```
