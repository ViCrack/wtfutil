# wtfutil.util

杂项工具：生命周期内去重队列、计时装饰器、日期时间、列表切块、分组、资源路径解析。`get_resource` / `get_resource_dir` 的唯一公开归属是本模块；私有实现文件不属于 API 契约。

```python
from wtfutil.util import UniqueQueue, get_resource, measure_time
```

> HTTP、文件、通知等能力请分别从 `wtfutil.httputil`、`wtfutil.fileutil`、`wtfutil.notifyutil` 导入，**不要**假定 `util` 聚合了其它子模块。

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

`queue.Queue` 子类；同一队列生命周期内，内容等价的对象重复 `put` 会被忽略。dict 键顺序不同、嵌套 list/dict 内容相同时也能去重。

```python
from wtfutil.util import UniqueQueue

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
| `get_resource(filename, basedir=None)` | 解析资源文件：当前路径 → 项目 `resource/` → `~/filename`；可显式指定搜索锚点 |

**`get_resource` 示例**：配置文件、黑名单等与脚本相对位置无关时，把文件放在 `resource/` 或用户家目录即可被找到（常与 [fileutil.read_lines](fileutil.md) 联用）。

```python
from wtfutil.fileutil import read_lines
from wtfutil.util import cut_list, get_resource, group_data, measure_time

path = get_resource("blacklist.txt")
if path is None:
    raise FileNotFoundError("blacklist.txt")
lines = read_lines(path, unique=True)

for batch in cut_list(lines, 50):
    process(batch)

rows = [{"status": 0, "url": "a"}, {"status": 1, "url": "b"}]
group_data(rows, group_by="status")

@measure_time
def job():
    ...
```
