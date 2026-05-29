# wtfutil.fileutil

文件读写、哈希、目录列举、`JarAnalyzer`。

```python
from wtfutil import read_text, read_lines, write_json, JarAnalyzer
```

## 读写与哈希

| 符号 | 参数要点 | 说明 |
|------|----------|------|
| `read_text(filepath, mode='r', encoding='utf-8', not_exists_ok=False, errors=None)` | `mode='rb'` 不按文本编码；`not_exists_ok=True` 且不存在返回 `''` | 读整个文件 |
| `read_json(filepath, encoding='utf-8', not_exists_ok=False)` | 不存在且 `not_exists_ok=True` 返回 `{}` | JSON → dict |
| `read_lines(filepath, encoding='utf-8', not_exists_ok=False, unique=False)` | 跳过空行；`unique=True` 保序去重 | 行列表 |
| `write_text` / `write_lines` / `write_json` | 写文件 | 见下方示例 |
| `file_md5` / `file_sha1` / `file_sha256` | 路径 `str` 或 `Path` | 整文件 hex 摘要 |
| `list_files` / `list_directories` | 单层、全路径 | 非递归 |
| `touch(filepath, mode=0o666, exist_ok=True)` | | 创建或更新时间戳 |

```python
from wtfutil import get_resource, read_lines, read_text, write_json, file_md5

path = get_resource("blacklist.txt")
lines = read_lines(path, unique=True)
domains = read_lines("./state/domains.txt", not_exists_ok=True)
html = read_text("page.html", errors="backslashreplace")

write_json("out.json", {"count": len(lines)})
print(file_md5("app.zip"))
```

## JarAnalyzer

构造时传入 `.jar` 路径；分析 JDK 线索、Spring Boot、`javaw`、Main-Class 等。部分分支依赖本机 **`javap`**。

```python
from wtfutil import JarAnalyzer

j = JarAnalyzer("app.jar")
print(j.jdk_version, j.is_spring_boot, j.recommended_executable, j.main_class)
```

## 与 httputil 联用

从文件读 URL/域名列表后，常用 `get_maindomain` 归一化；配合 `UniqueQueue` 做去重抓取队列（见 [util.md](util.md)）。
