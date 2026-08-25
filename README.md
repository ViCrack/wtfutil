# wtfutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

**wtfutil** is a Python utility library for everyday scripting and automation. It packs the most commonly needed "wheels" into one package: enhanced HTTP sessions, file I/O, encoding & crypto, SQLite/MySQL, process control, multi-channel push notifications, translation, and random images — organized into focused public submodules.

**Author**: [vicrack](https://github.com/vicrack) &nbsp;|&nbsp;
**中文文档**: [README_zh.md](./README_zh.md) &nbsp;|&nbsp;
**Full API reference**: [docs/](docs/README.md)

---

## Installation

```bash
pip install wtfutil
```

Requires Python 3.10+.

---

## Responsible Use

Security-sensitive features in this project are intended only for authorized security testing, research, education, and administration of systems you own or have explicit permission to assess.

Do not use this software to access, disrupt, modify, or deploy code to systems without authorization. Users are solely responsible for complying with applicable laws, regulations, organizational policies, and third-party terms of service. The maintainers do not endorse or accept responsibility for unlawful or abusive use.

---

## ⚠️ 1.3.0 Breaking Migration: Import from Submodules

> [!IMPORTANT]
> wtfutil 1.3.0 removes package-root symbol re-exports. Import functions, classes, constants, and configuration objects from the public submodule that owns them.

| Legacy package-root name | Import in 1.3.0+ |
|--------------------------|------------------|
| `requests_session` imported from `wtfutil` | `from wtfutil.httputil import requests_session` |
| `read_lines` imported from `wtfutil` | `from wtfutil.fileutil import read_lines` |
| `get_resource` imported from `wtfutil` | `from wtfutil.util import get_resource` |
| `send` imported from `wtfutil` | `from wtfutil.notifyutil import send` |
| `MemShellParty` imported from `wtfutil` | `from wtfutil.memshellutil import MemShellParty` |

Replace legacy package attributes such as `wtfutil.read_lines(...)`, `wtfutil.get_resource(...)`, and `wtfutil.requests_session(...)` with attributes on their owning modules:

```python
import wtfutil.fileutil as fileutil
import wtfutil.httputil as httputil
import wtfutil.util as util

lines = fileutil.read_lines(util.get_resource("urls.txt"), unique=True)
session = httputil.requests_session(timeout=30)
```

Importing a physical public submodule (for example, `from wtfutil import procutil`) remains valid Python, but direct imports from `wtfutil.<module>` make ownership and migration clearer.

For example, `from wtfutil.memshellutil import MemShellParty, MemShellPartyError` is the canonical SDK import. `wtfutil.memshell` remains the CLI implementation module rather than a second SDK owner.

---

## Feature Highlights

| Feature | What it gives you |
|---------|-------------------|
| **HTTP** | Proxy, retry, rate-limit, cache, fake IP, chunked upload, random UA — one factory call |
| **Files** | `read_lines` / `write_json`, `unique=True` dedup, `not_exists_ok` graceful reads |
| **Encoding / Crypto** | Base64, URL encode, MD5/SHA1/SHA256, RSA, DES |
| **Database** | Unified API for SQLite & MySQL — insert, query, bulk insert, upsert |
| **Notifications** | Feishu, DingTalk, Telegram, Bark, SMTP, Webhook and more — one `send()` call fans out concurrently |
| **Single instance** | Context manager or decorator to prevent duplicate script runs |
| **Process control** | Find/kill by name or cmdline (cross-platform); suspend/resume (Windows) |

---

## Quick Start

```python
from wtfutil.fileutil import read_lines, write_json
from wtfutil.httputil import requests_session
from wtfutil.notifyutil import send
from wtfutil.util import get_resource

# HTTP session with proxy (int = 127.0.0.1:<port>)
req = requests_session(proxies=10809, timeout=30)
r = req.get("https://httpbin.org/ip")
print(r.json())

# Read a resource file (looks in cwd -> resource/ -> ~/)
resource_path = get_resource("urls.txt")
if resource_path is None:
    raise FileNotFoundError("urls.txt")
lines = read_lines(resource_path, unique=True)

# Write JSON
write_json("out.json", {"status": "ok", "count": len(lines)})

# Push to all configured channels at once
send("Job done", f"Processed {len(lines)} items")
```

---

## HTTP — `httputil`

```python
from wtfutil.httputil import requests_session
from urllib3 import Retry

# Minimal (random UA, TLS certificate verification disabled)
req = requests_session()

# Explicitly enable certificate verification when required
verified_req = requests_session(verify=True)

# Proxy + timeout
req = requests_session(proxies=10809, timeout=30)

# Custom retry + large connection pool (high-concurrency scraping)
req = requests_session(
    timeout=30,
    max_retries=Retry(total=5, backoff_factor=0.5, allowed_methods=["GET"]),
    pool_connections=100,
    pool_maxsize=100,
)

# Fixed base URL — use relative paths afterwards
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
r = req.get("/authen/v1/user_info")

# Rate limit: max 5 requests/sec
req = requests_session(rate_limit=5)

# Disk-based HTTP cache
req = requests_session(use_cache={"cache_name": "./data/http_cache"})

# Random X-Forwarded-For
req = requests_session(fake_ip=True)

# Debug mode: prints full request/response
req = requests_session(debug=True)
```

Send raw HTTP messages:

```python
from wtfutil.httputil import httpraw

raw = """POST /api/login HTTP/1.1
Host: example.com
Content-Type: application/json

{"user":"admin","pass":"123"}
"""
resp = httpraw(raw, ssl=True, timeout=10)
```

URL / IP utilities:

```python
from wtfutil.httputil import get_maindomain, is_port_in_use, is_private_ip, url2ip

is_private_ip("192.168.1.1")       # True
get_maindomain("sub.example.com")  # "example.com"
url2ip("example.com")              # "93.184.216.34"
is_port_in_use(8080)               # False
```

---

## Files — `fileutil`

```python
from wtfutil.fileutil import (
    file_md5,
    read_json,
    read_lines,
    read_text,
    write_json,
    write_lines,
    write_text,
)
from wtfutil.util import get_resource

# Read lines, skip blanks, preserve-order dedup
lines = read_lines("targets.txt", unique=True)

# Graceful read — returns [] instead of raising if file is missing
lines = read_lines("state.txt", not_exists_ok=True)

# Read JSON, returns {} if file is missing
config = read_json("config.json", not_exists_ok=True)

# Write JSON (ensure_ascii=False, indent=4)
write_json("result.json", {"items": lines, "total": len(lines)})

# Write lines
write_lines("output.txt", ["line1", "line2", "line3"])

# File MD5
print(file_md5("app.zip"))

# Resource file lookup: cwd → resource/ → ~/
path = get_resource("blacklist.txt")
if path is None:
    raise FileNotFoundError("blacklist.txt")
blacklist = read_lines(path, unique=True)
```

---

## Strings & Crypto — `strutil`

```python
from wtfutil.strutil import (
    str_md5, str_sha256,
    base64encode, base64decode,
    url_encode, url_decode,
    rsa_encrypt, rsa_decrypt,
    rand_base, get_middle_text,
)

# Hashing
str_md5("hello")                         # "5d41402abc4b2a76b9719d911017c592"
str_sha256(b"data")

# Base64
base64encode(b"hello world")             # "aGVsbG8gd29ybGQ="
base64decode("aGVsbG8gd29ybGQ=")         # "hello world"

# URL encoding
url_encode("a=1&b=hello world")          # "a%3D1%26b%3Dhello%20world"

# Random token (default charset: lowercase letters + digits, a-z0-9; pass letters= to customize)
token = rand_base(32)

# Extract text between two markers (useful for HTML scraping)
value = get_middle_text(html, 'name="token" value="', '"')

# RSA encryption (auto-segments long data)
encrypted = rsa_encrypt(b"secret data", public_key_pem)
plaintext = rsa_decrypt(encrypted, private_key_pem)
```

---

## Database — `sqlutil`

```python
from wtfutil.sqlutil import MYSQL, SQLite, next_id

# SQLite
db = SQLite("data.db")

db.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        url TEXT,
        status INTEGER DEFAULT 0
    )
""")

# Single insert
db.insert("items", {"id": next_id(), "url": "https://a.com", "status": 0})

# Bulk insert
rows = [{"id": next_id(), "url": u, "status": 0} for u in url_list]
db.insert_many("items", rows)

# Query
row = db.select_one("items", where_clause={"url": "https://a.com"})
rows = db.select("items", where_clause={"status": 0})

# Update / delete
db.update("items", {"status": 1}, {"url": "https://a.com"})
db.delete("items", {"status": 0})

# MySQL — same API
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "xxx", "url": "https://b.com"})
```

---

## Notifications — `notifyutil`

Configure channels before importing `notifyutil` (via `wtfconfig.ini` or environment variables), then your code stays unchanged regardless of how many channels you add:

```python
from wtfutil.notifyutil import send

# wtfconfig.ini
# [notify]
# FEISHU_KEY = your_webhook_key
# TG_BOT_TOKEN = 123456:xxx
# TG_USER_ID = 88888888
# BARK_PUSH = https://api.day.app/your_key

# Fan out to all configured channels concurrently
send("Scraper error", "Target site returned 403, pausing for 5 minutes")
```

Changing values in `push_config` at runtime does not rebuild the enabled-channel list, so use the ini file or environment variables to enable new channels.

Call a single channel directly:

```python
from wtfutil.notifyutil import feishu_bot, telegram_bot

feishu_bot("Alert", "Disk usage exceeded 90%")
telegram_bot("Alert", "Disk usage exceeded 90%")
```

---

## Single Instance — `singleinstance`

Prevent a script or scheduled job from running more than once at a time:

```python
from wtfutil.singleinstance import SingleInstance, SingleInstanceException, single_instance

# Context manager
try:
    with SingleInstance(flavor_id="crawler_job"):
        run_crawler()
except SingleInstanceException:
    print("Already running, skipping")

# Decorator
@single_instance(flavor_id="data_sync")
def sync_data():
    ...
```

`flavor_id` lets multiple independent lock modes coexist in the same script.  
Details: [docs/en/singleinstance.md](docs/en/singleinstance.md)

---

## Process Control — `procutil`

Find/kill is cross-platform; suspend/resume is Windows-only.

```python
from wtfutil.procutil import (
    find_python_processes_by_cmdline,
    find_python_processes_by_script,
    kill_python_processes_by_script,
    resume_process_by_pid,
    suspend_process_by_pid,
)

# Find Python processes by script path
procs = find_python_processes_by_script("worker.py")

# Find by command-line substring
procs = find_python_processes_by_cmdline("celery worker")

# Suspend / resume (Windows only) / kill by script (cross-platform)
suspend_process_by_pid(pid)
resume_process_by_pid(pid)
kill_python_processes_by_script("worker.py")
```

`pykill` CLI (installed with the package):

```bash
pykill                       # list all Python processes, interactive multi-select kill
pykill worker.py             # kill by script path
pykill worker.py -l          # list only, no kill
pykill -c "celery worker"    # match by command-line substring
```

Details: [docs/en/pykill.md](docs/en/pykill.md)

`memshell` CLI (MemShellParty memory-shell generator):

```bash
memshell config
memshell generate --shell-tool Behinder --shell-type Listener -o payload.txt
memshell probe -o payload.txt
memshell install-skill --project   # install to ./.agents/skills/memshell
```

Details: [docs/en/memshellutil.md](docs/en/memshellutil.md)

---

## Misc Utilities — `util`

```python
from wtfutil.util import UniqueQueue, cut_list, group_data, measure_time

# Dedup queue: duplicate dicts are silently dropped (great for multi-thread crawlers)
q = UniqueQueue()
q.put({"url": "https://a.com"})
q.put({"url": "https://a.com"})  # ignored
print(q.qsize())  # 1

# Timing decorator
@measure_time
def heavy_task():
    ...

# Slice a list into fixed-size batches (bulk DB writes, batch API calls)
for batch in cut_list(url_list, 50):
    process_batch(batch)

# Group rows by a field
groups = group_data(rows, group_by="status")  # {0: [...], 1: [...]}
```

---

## Configuration

Loaded via `wtfutil.configutil` (mtime hot-reload on `ensure_section`). Search order — **env vars always win**:

> current working directory → `resource/wtfconfig.ini` → `~/wtfconfig.ini`

```ini
[notify]
CONSOLE = true
FEISHU_KEY =
FEISHU_SECRET =
DD_BOT_TOKEN =
DD_BOT_SECRET =
TG_BOT_TOKEN =
TG_USER_ID =
BARK_PUSH =
SMTP_SERVER =
SMTP_EMAIL =
SMTP_PASSWORD =
WEBHOOK_URL =

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =

[memshell]
# BASE_URL = https://party.mem.mk
```

Full key list: `wtfconfig.ini.example`; API details: [configutil](docs/en/configutil.md), [notifyutil](docs/en/notifyutil.md), [imgutil](docs/en/imgutil.md), [memshellutil](docs/en/memshellutil.md).

---

## Module Overview

| Module | Description | API docs |
|--------|-------------|----------|
| `wtfutil.httputil` | Enhanced `requests` session, raw HTTP, URL/IP/DNS, SSL adapters | [EN](docs/en/httputil.md) · [ZH](docs/zh/httputil.md) |
| `wtfutil.fileutil` | File I/O, hashing, `JarAnalyzer` | [EN](docs/en/fileutil.md) · [ZH](docs/zh/fileutil.md) |
| `wtfutil.strutil` | Encoding, hashing, RSA/DES, string tools | [EN](docs/en/strutil.md) · [ZH](docs/zh/strutil.md) |
| `wtfutil.sqlutil` | SQLite / MySQL wrappers, `Database`, SQL helpers | [EN](docs/en/sqlutil.md) · [ZH](docs/zh/sqlutil.md) |
| `wtfutil.procutil` | Process control (find/kill cross-platform; suspend/resume Windows only) | [EN](docs/en/procutil.md) · [ZH](docs/zh/procutil.md) |
| `wtfutil.configutil` | Unified `wtfconfig.ini` load + mtime hot-reload | [EN](docs/en/configutil.md) · [ZH](docs/zh/configutil.md) |
| `wtfutil.notifyutil` | Multi-channel push notifications | [EN](docs/en/notifyutil.md) · [ZH](docs/zh/notifyutil.md) |
| `wtfutil.translateutil` | Baidu Translate API | [EN](docs/en/translateutil.md) · [ZH](docs/zh/translateutil.md) |
| `wtfutil.memshellutil` | MemShellParty memory-shell SDK | [EN](docs/en/memshellutil.md) · [ZH](docs/zh/memshellutil.md) |
| `wtfutil.imgutil` | Random avatar fetch (multi-source fallback) | [EN](docs/en/imgutil.md) · [ZH](docs/zh/imgutil.md) |
| `wtfutil.singleinstance` | Single-instance lock (`SingleInstance`, `@single_instance`) | [EN](docs/en/singleinstance.md) · [ZH](docs/zh/singleinstance.md) |
| `wtfutil.util` | Misc helpers, `get_resource`, `UniqueQueue` | [EN](docs/en/util.md) · [ZH](docs/zh/util.md) |
| **`pykill`** (CLI) | List/kill Python processes (wraps `procutil`) | [EN](docs/en/pykill.md) · [ZH](docs/zh/pykill.md) |
| **`memshell`** (CLI) | MemShellParty generate / probe / install-skill | [EN](docs/en/memshellutil.md) · [ZH](docs/zh/memshellutil.md) |

Public SDK APIs live in the physical submodules listed above. Import each symbol from its owning `wtfutil.<module>` path.

---

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/ViCrack/wtfutil).

When adding or changing public APIs, update the owning module's API documentation under `docs/en/` and `docs/zh/`. See [AGENTS.md](./AGENTS.md) for agent-oriented project notes.
