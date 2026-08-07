# wtfutil.fileutil

File read/write, hashing, directory listing, `JarAnalyzer`.

```python
from wtfutil.fileutil import JarAnalyzer, read_lines, read_text, write_json
```

## Read / write / hash

| Symbol | Notes |
|--------|-------|
| `read_text(path, mode='r', encoding='utf-8', not_exists_ok=False, errors=None)` | Read-only modes return `str` or `bytes`; write/append/create/update modes raise `ValueError` before opening the file; missing binary reads return `b''` when allowed |
| `read_json(path, encoding='utf-8', not_exists_ok=False)` | `{}` if missing and `not_exists_ok=True` |
| `read_lines(path, encoding='utf-8', not_exists_ok=False, unique=False)` | Skips blank lines; `unique=True` dedupes |
| `write_text` / `write_lines` / `write_json` | See source docstrings |
| `file_md5` / `file_sha1` / `file_sha256(path)` | Streaming whole-file hex digest (bounded memory) |
| `list_files` / `list_directories(directory)` | Non-recursive full paths |
| `touch(path, mode=0o666, exist_ok=True)` | Create or update mtime |

```python
from wtfutil.fileutil import file_md5, read_lines, read_text, write_json
from wtfutil.util import get_resource

lines = read_lines(get_resource("urls.txt"), unique=True)
html = read_text("page.html", errors="backslashreplace")
write_json("out.json", {"count": len(lines)})
print(file_md5("app.zip"))
```

## JarAnalyzer

```python
from wtfutil.fileutil import JarAnalyzer

j = JarAnalyzer("app.jar")
print(j.jdk_version, j.is_spring_boot, j.recommended_executable, j.main_class)
```

GUI analysis uses local `javap` when available and falls back to JAR byte inspection if the command is missing, fails, or exceeds 30 seconds. Manifest continuation lines and Java 22 or newer class-major versions are supported.
