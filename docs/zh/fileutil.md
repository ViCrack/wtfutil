# wtfutil.fileutil

文件读写、哈希、目录列举、`JarAnalyzer`。

```python
from wtfutil.fileutil import JarAnalyzer, read_lines, read_text, write_json
```

## 读写与哈希

| 符号 | 参数要点 | 说明 |
|------|----------|------|
| `read_text(filepath, mode='r', encoding='utf-8', not_exists_ok=False, errors=None)` | 文本模式返回 `str`；任意二进制模式返回 `bytes`；允许缺失时二进制返回 `b''` | 读整个文件 |
| `read_json(filepath, encoding='utf-8', not_exists_ok=False)` | 不存在且 `not_exists_ok=True` 返回 `{}` | JSON → dict |
| `read_lines(filepath, encoding='utf-8', not_exists_ok=False, unique=False)` | 跳过空行；`unique=True` 保序去重 | 行列表 |
| `write_text` / `write_lines` / `write_json` | 写文件 | 见下方示例 |
| `file_md5` / `file_sha1` / `file_sha256` | 路径 `str` 或 `Path` | 分块读取并计算整文件 hex 摘要 |
| `list_files` / `list_directories` | 单层、全路径 | 非递归 |
| `touch(filepath, mode=0o666, exist_ok=True)` | | 创建或更新时间戳 |

```python
from wtfutil.fileutil import file_md5, read_lines, read_text, write_json
from wtfutil.util import get_resource

path = get_resource("blacklist.txt")
lines = read_lines(path, unique=True)
domains = read_lines("./state/domains.txt", not_exists_ok=True)
html = read_text("page.html", errors="backslashreplace")

write_json("out.json", {"count": len(lines)})
print(file_md5("app.zip"))
```

## JarAnalyzer

构造时传入 `.jar` 路径；分析 JDK 线索、Spring Boot、`javaw`、Main-Class 等。GUI 分析优先使用本机 **`javap`**；命令不存在、失败或超过 30 秒时回退到 JAR 字节检查。

```python
from wtfutil.fileutil import JarAnalyzer

j = JarAnalyzer("app.jar")
print(j.jdk_version, j.is_spring_boot, j.recommended_executable, j.main_class)
```

## 与 httputil 联用

从文件读 URL/域名列表后，常用 `get_maindomain` 归一化；配合 `UniqueQueue` 做去重抓取队列（见 [util.md](util.md)）。
