# wtfutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

**wtfutil** is a Python utility library for everyday scripting and automation: HTTP, files, strings & crypto, databases, Windows processes, multi-channel notifications, translation, and random images.

**Author**: [vicrack](https://github.com/vicrack)  
**中文文档**: [README_zh.md](./README_zh.md)

---

## Installation

```bash
pip install wtfutil
```

Requires Python 3.10+.

---

## Quick Start

```python
# All public symbols are available directly from the package
from wtfutil import requests_session, read_text, send, get_resource

# HTTP session (no SSL verify, random UA, optional proxy/timeout/debug/cache)
req = requests_session(proxies=10809, timeout=30)
r = req.get("https://example.com/")

# File utilities
lines = read_lines(get_resource("urls.txt"), unique=True)
write_json("out.json", {"ok": True})

# Notification (all configured channels, concurrent)
send("Alert", "Task finished")

# Or import by sub-module for IDE autocompletion
from wtfutil import httputil, fileutil, notifyutil, util
```

---

## Module Overview

| Module | Description |
|--------|-------------|
| `wtfutil.httputil` | Enhanced `requests` session, raw HTTP, URL/IP/DNS tools, SSL adapters |
| `wtfutil.fileutil` | File read/write, hashing, directory listing, `JarAnalyzer` |
| `wtfutil.strutil` | Encoding/decoding, hashing, RSA/DES, string utilities |
| `wtfutil.sqlutil` | `SQLite` / `MySQL` wrappers, `Database` abstraction, SQL helpers |
| `wtfutil.procutil` | Windows process find/suspend/resume (Windows only) |
| `wtfutil.notifyutil` | Multi-channel push notifications, `send()` aggregator |
| `wtfutil.translateutil` | Baidu Translate API wrapper |
| `wtfutil.imgutil` | Random avatar fetch with multi-source fallback |
| `wtfutil.singleinstance` | Single-instance lock via file lock + portalocker |
| `wtfutil.util` | Misc: `UniqueQueue`, `measure_time`, datetime helpers, `get_resource` |

---

## httputil

### `requests_session()`

Factory that returns a pre-configured session. Depending on parameters it returns a `CachedSession`, `BaseUrlSession`, or `RequestsSession` — all with `verify=False`, random UA, retry adapters, and the custom SSL context adapter.

```python
def requests_session(
    proxies=False,          # False/None | dict | int (port) | str (url)
    timeout=None,           # seconds, applied to every request
    debug=False,            # print full request/response packets
    base_url=None,          # BaseUrlSession: relative paths joined to this
    user_agent=None,        # None → random fake UA
    use_cache=None,         # True | dict(**CachedSession kwargs)
    fake_ip=False,          # True → random residential X-Forwarded-For
    rate_limit=None,        # max requests per second (int)
    chunked=False,          # True | ChunkedConfig — chunked Transfer-Encoding
    max_retries=DEFAULT,    # int or urllib3.Retry
    pool_connections=10,
    pool_maxsize=10,
) -> RequestsSession: ...
```

**Common examples:**

```python
from wtfutil import requests_session
from urllib3 import Retry

# Basic
req = requests_session()

# Local proxy (Clash on 10809), 30 s timeout
req = requests_session(proxies=10809, timeout=30)

# High concurrency scraping
req = requests_session(timeout=30, max_retries=3,
                       pool_connections=100, pool_maxsize=100)

# Fixed base URL (REST client)
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
r = req.get("/auth/v3/tenant_access_token/internal")

# HTTP response caching
req = requests_session(use_cache={"cache_name": "./cache/http"})

# Fake X-Forwarded-For
req = requests_session(fake_ip=True)

# Granular retry control
req = requests_session(
    max_retries=Retry(total=3, backoff_factor=1, allowed_methods=["GET"]),
)

# Debug — print raw request/response
req = requests_session(debug=True)

# WAF bypass via chunked transfer encoding
from wtfutil.httputil import ChunkedConfig
req = requests_session(chunked=ChunkedConfig.aggressive())
```

**Module-level side effects on import** (applied once automatically):
- `urllib3.disable_warnings()` — suppress certificate warnings
- `remove_ssl_verify()` — disable global HTTPS verification
- `patch_redirect()` — fix redirect encoding edge case in `requests`
- `patch_getproxies()` — fix Windows registry proxy `https://` → `http://`

### `RequestsSession` hooks

```python
session = requests_session()

@session.pre_request
def add_token(request):
    request.headers["Authorization"] = "Bearer xxx"

@session.pre_send
def log_url(prepared, kwargs):
    print(prepared.url)
```

### `httpraw(raw, ssl=False, **kwargs)`

Send a raw HTTP packet as text:

```python
from wtfutil import httpraw

raw = """GET /api/info HTTP/1.1
Host: example.com
"""
resp = httpraw(raw, ssl=True, timeout=10)
```

### Other `httputil` symbols

| Symbol | Description |
|--------|-------------|
| `EnhancedResponse` | Replaces response class; prints debug info on `json()` decode failure |
| `BaseUrlSession` | Session with a fixed base URL |
| `CustomSslContextHttpAdapter` | HTTPS adapter compatible with legacy TLS renegotiation |
| `ChunkedConfig` / `ChunkedAdapter` | Chunked encoding with keyword-aware splitting |
| `DESAdapter` | Randomises TLS cipher list (JA3 fingerprint evasion) |
| `is_private_ip(ip)` | Detect private/loopback IPs; excludes `198.18.0.0/16` (fake-ip) |
| `is_internal_url(url)` | Check if URL resolves to an internal IP |
| `is_wildcard_dns(domain)` | Detect wildcard DNS on a root domain |
| `is_wildcard_dns_batch(domains, thread_num, show_progress)` | Batch wildcard check |
| `get_maindomain(subdomain)` | Extract registered domain (uses `tldextract`) |
| `url2ip(url, with_port=False)` | Resolve URL host to IP |
| `is_port_in_use(port)` | Check if a local port is listening |
| `get_base_url(url)` | Extract `scheme://host` from any URL |
| `build_absolute_url(base, relative)` | Resolve a relative URL against a base |

---

## fileutil

| Symbol | Notes |
|--------|-------|
| `read_text(path, mode='r', encoding='utf-8', not_exists_ok=False, errors=None)` | `mode='rb'` for binary; `errors='ignore'/'backslashreplace'` for dirty encodings |
| `read_json(path, encoding='utf-8', not_exists_ok=False)` | Returns `{}` if file missing and `not_exists_ok=True` |
| `read_lines(path, encoding='utf-8', not_exists_ok=False, unique=False)` | Skips blank lines; `unique=True` for deduplicated list |
| `write_text(path, content, mode='w', encoding='utf-8', newline='')` | |
| `write_lines(path, lines, mode='w', encoding='utf-8', unique=False, newline='')` | |
| `write_json(path, json_obj, encoding='utf-8')` | Pretty-printed with `ensure_ascii=False` |
| `file_md5 / file_sha1 / file_sha256(path)` | Whole-file hex digest |
| `list_files(directory)` | Non-recursive; returns full paths |
| `list_directories(directory)` | Non-recursive; returns full paths |
| `touch(path, mode=0o666, exist_ok=True)` | Create or update timestamp |

**`JarAnalyzer`** — inspect a `.jar` file:

```python
from wtfutil import JarAnalyzer

j = JarAnalyzer("app.jar")
print(j.jdk_version)        # e.g. 17
print(j.is_spring_boot)     # True/False
print(j.recommended_executable)  # "java" or "javaw"
print(j.main_class)
```

---

## strutil

| Category | Symbols |
|----------|---------|
| Type conversion | `tobytes`, `tostr`, `tobool` |
| String manipulation | `removesuffix`, `removeprefix`, `get_middle_text`, `splitlines`, `normalize_spaces`, `align_text`, `match1`, `string_to_bash_variable` |
| URL / Base64 | `url_encode_all`, `url_encode`, `url_decode`, `qp_encode_all`, `uuencode`, `base64encode`, `base64decode`, `base64_urlencode`, `base64_urldecode`, `urlsafe_base64encode`, `urlsafe_base64decode`, `base64pickle`, `base64unpickle` |
| Crypto | `rsa_encrypt`, `rsa_decrypt`, `des_encrypt`, `des_decrypt` |
| Hash | `str_md5`, `str_sha1`, `str_sha256` |
| Misc encoding | `rand_base`, `rand_case`, `format_bytes`, `extract_dict`, `utf8_overlong_encoding`, `utf7_encode`, `unicode_digit_hex_escape`, `unicode_digit_hex_encode`, `ghost_bits_byte`, `ghost_bits_encode`, `ghost_bits_decode_to_bytes`, `ghost_bits_decode` |

---

## sqlutil

### Classes

| Symbol | Description |
|--------|-------------|
| `Dict` | `dict` subclass supporting attribute-style access (`d.key`) |
| `Database` | Abstract base class defining common CRUD / query interface |
| `SQLite` | SQLite implementation: `SQLite(db_file: str)` |
| `MYSQL` | PyMySQL implementation: `MYSQL(host, user, password, database, charset='utf8mb4', port=3306, ssl=None)` |
| `ScriptRunner` | Execute multi-statement SQL scripts with basic `DELIMITER` support |

### Common `Database` methods

`insert`, `insert_or_replace`, `insert_many`, `update`, `delete`, `count`, `select`, `select_one`, `execute`, `query`, `get`, `record_exists`, `select_by_id`, `fetch_rows`, `fetchone`, `bulk_insert`, `replace`, `exists`, `fetch_by_id`, `close`

### Helper functions

| Symbol | Description |
|--------|-------------|
| `next_id(t=None)` | 50-char ID (timestamp + UUID) |
| `join_field_value(data)` | Build `UPDATE SET` fragment |
| `join_field(data)` | Build column name list |
| `join_value(data)` | Build value placeholder list |

---

## procutil (Windows only)

| Symbol | Description |
|--------|-------------|
| `find_process_by_name(name)` | Find processes by name, return PID list |
| `suspend_process(name)` | Suspend all threads of matching processes |
| `suspend_process_by_pid(pid)` | Suspend by PID |
| `resume_process(name)` | Resume all threads of matching processes |
| `resume_process_by_pid(pid)` | Resume by PID |
| `find_python_process_by_script(script)` | Find first Python process running a script |
| `find_python_processes_by_script(script)` | Find all Python processes running a script |
| `find_python_process_details_by_script(script)` | Detailed info list |
| `kill_python_processes_by_script(script)` | Kill matching Python processes |
| `find_python_processes_by_cmdline(pattern)` | Match by command line |
| `find_python_process_details_by_cmdline(pattern)` | Detailed info list |
| `kill_python_processes_by_cmdline(pattern)` | Kill matching |
| `list_all_python_process_details()` | List all Python processes |

---

## notifyutil

### Configuration

`push_config` is loaded in order (later overrides earlier):
1. Built-in defaults (all empty / `False`)
2. `wtfconfig.ini` `[notify]` section
3. Environment variables (highest priority)

`wtfconfig.ini` is located by `get_resource("wtfconfig.ini")`: current dir → `resource/wtfconfig.ini` → `~/wtfconfig.ini`.

```ini
[notify]
CONSOLE = true
BARK_PUSH =
FEISHU_KEY =
FEISHU_SECRET =
DD_BOT_TOKEN =
DD_BOT_SECRET =
TG_BOT_TOKEN =
TG_USER_ID =
SMTP_SERVER =
SMTP_EMAIL =
SMTP_PASSWORD =
SHOWDOC_KEY =
WEBHOOK_URL =
WEBHOOK_METHOD = POST
WEBHOOK_CONTENT_TYPE = application/json
WEBHOOK_BODY =
```

### Sending

```python
from wtfutil import send, push_config

# Concurrent push to all configured channels
send("Title", "Message content")

# Adjust config at runtime
push_config["FEISHU_KEY"] = "xxx"
```

Or via environment variable:

```powershell
$env:FEISHU_KEY = "your_key"
```

### Supported channels

`bark`, `console`, `dingding_bot`, `feishu_bot`, `feishu_text`, `feishu_richtext`, `go_cqhttp`, `gotify`, `iGot`, `serverJ`, `pushdeer`, `chat`, `pushplus_bot`, `qmsg_bot`, `wecom_app`, `wecom_bot`, `telegram_bot`, `aibotk`, `smtp`, `pushme`, `pipehub`, `xtuis`, `aiops_phone`, `showdoc`, `notifyx`, `chronocat`, `custom_notify`

Each can also be called directly:

```python
from wtfutil import feishu_bot, telegram_bot
feishu_bot("Title", "Body")
```

---

## translateutil

```python
from wtfutil import BaiduTranslateApi

t = BaiduTranslateApi(appid="xxx", appkey="yyy")
result = t.translate("你好", from_lang="zh", to_lang="en")
print(result)  # "Hello"
```

Rate-limited to ~1 request/second internally via `ratelimit`.

---

## imgutil

```python
from wtfutil import random_avatar_bytes

data = random_avatar_bytes()          # bytes of a random anime avatar
with open("avatar.jpg", "wb") as f:
    f.write(data)
```

Built-in sources (tried in random order): `loliapi`, `dmoe`, `xjh`, `btstu`, `horosama`.  
Optional `apihz` source activated when `APIHZ_IMG_ID` + `APIHZ_IMG_KEY` are configured.

**Configuration** (`[img]` section in `wtfconfig.ini` or environment variables):

| Key | Description |
|-----|-------------|
| `APIHZ_IMG_ID` | apihz interface ID |
| `APIHZ_IMG_KEY` | apihz interface key |
| `APIHZ_IMGTYPE` | `imgtype` query param (default `5`) |
| `APIHZ_IMG_TYPE` | `type` query param (default `1`) |

```python
from wtfutil import fetch_random_bytes, ImageFetchError

# Custom fetcher list with fallback
def my_fetcher(session):
    return session.get("https://my.cdn/avatar.jpg").content

try:
    data = fetch_random_bytes([my_fetcher], timeout=10)
except ImageFetchError as e:
    print(e.errors)
```

---

## singleinstance

Prevent a script from running more than one instance at a time.

```python
from wtfutil import single_instance, SingleInstanceException

# Context manager
try:
    with single_instance(flavor_id="my_job"):
        run_job()
except SingleInstanceException:
    print("Already running")

# Decorator
@single_instance(flavor_id="my_job")
def main():
    run_job()
```

Lock file is created in the OS temp directory, named from the script path + `flavor_id`.

---

## util (misc)

```python
from wtfutil.util import UniqueQueue, measure_time, get_resource

# Deduplicated queue (same dict value → ignored)
q = UniqueQueue()
q.put({"url": "https://a.com"})
q.put({"url": "https://a.com"})  # ignored

# Timing decorator
@measure_time
def heavy():
    ...

# Resolve a resource file relative to the script / resource/ / home dir
path = get_resource("blacklist.txt")
```

| Symbol | Description |
|--------|-------------|
| `UniqueQueue` | `queue.Queue` that ignores duplicate items |
| `measure_time` | Decorator that prints execution time |
| `unique_items(iterable)` | Order-preserving deduplication |
| `current_datetime()` | `datetime.now()` |
| `format_datetime(dt, format=...)` | Format datetime to string |
| `parse_datetime(date_string, format=...)` | Parse datetime string |
| `cut_list(obj, size)` | Chunk a list into sublists of `size` |
| `group_data(data, group_by, remove_duplicates=False)` | Group rows by column index or dict key |
| `get_resource(filename)` | Locate a resource file (current dir → resource/ → ~/filename) |
| `get_resource_dir(basedir=None)` | Walk up to find the directory containing `resource/` |

---

## Configuration Summary

`wtfconfig.ini` searched in order: current dir → `resource/wtfconfig.ini` → `~/wtfconfig.ini`.  
Environment variables override the file.

```ini
[notify]
HITOKOTO = false
CONSOLE = true
BARK_PUSH =
FEISHU_KEY =
FEISHU_SECRET =
DD_BOT_TOKEN =
DD_BOT_SECRET =
TG_BOT_TOKEN =
TG_USER_ID =
SMTP_SERVER =
SMTP_EMAIL =
SMTP_PASSWORD =
SHOWDOC_KEY =
WEBHOOK_URL =
WEBHOOK_METHOD = POST
WEBHOOK_CONTENT_TYPE = application/json
WEBHOOK_BODY =

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =
```

---

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/vicrack).  
When adding or changing public APIs, update each module's `__all__` and this README.
