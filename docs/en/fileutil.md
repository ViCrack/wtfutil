# wtfutil.fileutil

File read/write, hashing, directory listing, `JarAnalyzer`.

```python
from wtfutil import read_text, read_lines, write_json, JarAnalyzer
```

## Read / write / hash

| Symbol | Notes |
|--------|-------|
| `read_text(path, mode='r', encoding='utf-8', not_exists_ok=False, errors=None)` | `mode='rb'` for binary; `errors='ignore'/'backslashreplace'` |
| `read_json(path, encoding='utf-8', not_exists_ok=False)` | `{}` if missing and `not_exists_ok=True` |
| `read_lines(path, encoding='utf-8', not_exists_ok=False, unique=False)` | Skips blank lines; `unique=True` dedupes |
| `write_text` / `write_lines` / `write_json` | See source docstrings |
| `file_md5` / `file_sha1` / `file_sha256(path)` | Whole-file hex digest |
| `list_files` / `list_directories(directory)` | Non-recursive full paths |
| `touch(path, mode=0o666, exist_ok=True)` | Create or update mtime |

```python
from wtfutil import get_resource, read_lines, read_text

lines = read_lines(get_resource("urls.txt"), unique=True)
html = read_text("page.html", errors="backslashreplace")
```

## JarAnalyzer

```python
from wtfutil import JarAnalyzer

j = JarAnalyzer("app.jar")
print(j.jdk_version, j.is_spring_boot, j.recommended_executable, j.main_class)
```

Some analysis requires local `javap`.
