# wtfutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

**wtfutil** is a Python utility library for everyday scripting and automation: HTTP, files, strings & crypto, databases, Windows processes, multi-channel notifications, translation, and random images.

**Author**: [vicrack](https://github.com/vicrack)  
**中文文档**: [README_zh.md](./README_zh.md)  
**Full API reference**: [docs/](docs/README.md) (per-module, EN/ZH)  
**Agent notes**: [AGENTS.md](./AGENTS.md)

---

## Installation

```bash
pip install wtfutil
```

Requires Python 3.10+.

---

## Quick Start

```python
from wtfutil import requests_session, read_lines, write_json, send, get_resource

req = requests_session(proxies=10809, timeout=30)
r = req.get("https://example.com/")

lines = read_lines(get_resource("urls.txt"), unique=True)
write_json("out.json", {"ok": True})

send("Alert", "Task finished")
```

Sub-module imports work as well: `from wtfutil import httputil, fileutil, notifyutil, util`.

---

## CLI & single-instance

### `pykill` — kill Python processes (CLI)

Installed as a console script (not in `wtfutil.__all__`). Wraps `procutil` with Rich tables and optional interactive selection.

```bash
pykill                          # list all Python processes, pick PIDs to kill
pykill myscript.py              # kill by script path
pykill myscript.py -l           # list only
pykill -c "celery worker"       # match command-line substring
```

Details: [docs/en/pykill.md](docs/en/pykill.md) · [docs/zh/pykill.md](docs/zh/pykill.md)

### `singleinstance` — one instance per script

```python
from wtfutil import single_instance, SingleInstanceException

try:
    with single_instance(flavor_id="my_job"):
        run_job()
except SingleInstanceException:
    print("Already running")
```

`flavor_id` distinguishes multiple single-instance modes for the same script; lock file defaults to the system temp directory.  
Details: [docs/en/singleinstance.md](docs/en/singleinstance.md) · [docs/zh/singleinstance.md](docs/zh/singleinstance.md)

---

## Module Overview

| Module | Description | API docs |
|--------|-------------|----------|
| `wtfutil.httputil` | Enhanced `requests` session, raw HTTP, URL/IP/DNS, SSL adapters | [EN](docs/en/httputil.md) · [ZH](docs/zh/httputil.md) |
| `wtfutil.fileutil` | File I/O, hashing, `JarAnalyzer` | [EN](docs/en/fileutil.md) · [ZH](docs/zh/fileutil.md) |
| `wtfutil.strutil` | Encoding, hashing, RSA/DES, string tools | [EN](docs/en/strutil.md) · [ZH](docs/zh/strutil.md) |
| `wtfutil.sqlutil` | SQLite / MySQL wrappers, `Database`, SQL helpers | [EN](docs/en/sqlutil.md) · [ZH](docs/zh/sqlutil.md) |
| `wtfutil.procutil` | Windows process control (Windows only) | [EN](docs/en/procutil.md) · [ZH](docs/zh/procutil.md) |
| `wtfutil.notifyutil` | Multi-channel notifications | [EN](docs/en/notifyutil.md) · [ZH](docs/zh/notifyutil.md) |
| `wtfutil.translateutil` | Baidu Translate API | [EN](docs/en/translateutil.md) · [ZH](docs/zh/translateutil.md) |
| `wtfutil.imgutil` | Random avatar fetch | [EN](docs/en/imgutil.md) · [ZH](docs/zh/imgutil.md) |
| `wtfutil.singleinstance` | Single-instance lock (`SingleInstance`, `@single_instance`) | [EN](docs/en/singleinstance.md) · [ZH](docs/zh/singleinstance.md) |
| `wtfutil.util` | Misc helpers, `get_resource` | [EN](docs/en/util.md) · [ZH](docs/zh/util.md) |
| **`pykill`** (CLI) | List/kill Python processes (uses `procutil`) | [EN](docs/en/pykill.md) · [ZH](docs/zh/pykill.md) |

All public symbols are also exported at package top level (`from wtfutil import read_text, ...`). See `wtfutil/__init__.py` `__all__`.

---

## Configuration Summary

`wtfconfig.ini` is resolved by `get_resource("wtfconfig.ini")`: current dir → `resource/wtfconfig.ini` → `~/wtfconfig.ini`. **Environment variables override the file.**

```ini
[notify]
CONSOLE = true
FEISHU_KEY =
# ... see docs/en/notifyutil.md

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =
```

Details: [notifyutil](docs/en/notifyutil.md), [imgutil](docs/en/imgutil.md). Example file: `wtfconfig.ini.example`.

---

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/ViCrack/wtfutil).

When adding or changing public APIs, update the module `__all__`, `wtfutil/__init__.py`, and the matching files under `docs/en/` and `docs/zh/`. See [AGENTS.md](./AGENTS.md) for agent-oriented project notes.
