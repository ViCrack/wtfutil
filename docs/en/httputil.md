# wtfutil.httputil

Enhanced `requests` session, raw HTTP, URL/IP/DNS tools, SSL adapters.

```python
from wtfutil import requests_session, httpraw
```

## Module-level side effects (on import)

Applied once automatically:

- `urllib3.disable_warnings()` — suppress certificate warnings
- `remove_ssl_verify()` — disable global HTTPS verification (process-wide)
- `patch_redirect()` — fix redirect encoding edge case in `requests`
- `patch_getproxies()` — fix Windows registry proxy `https://` → `http://`

## requests_session()

Factory returning a pre-configured session (`CachedSession`, `BaseUrlSession`, or `RequestsSession`) with `verify=False`, retry adapters, and `CustomSslContextHttpAdapter` on HTTPS.

```python
def requests_session(
    proxies=False,          # False/None | dict | int (port) | str (url)
    timeout=None,
    debug=False,
    base_url=None,
    user_agent=None,
    use_cache=None,         # True | dict(**CachedSession kwargs)
    fake_ip=False,          # True → random X-Forwarded-For; str → fixed value
    rate_limit=None,
    chunked=False,          # True | ChunkedConfig
    max_retries=DEFAULT,
    pool_connections=10,
    pool_maxsize=10,
) -> RequestsSession: ...
```

**Examples:**

```python
from wtfutil import requests_session
from urllib3 import Retry

req = requests_session()
req = requests_session(proxies=10809, timeout=30)
req = requests_session(timeout=30, max_retries=3, pool_connections=100, pool_maxsize=100)
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
req = requests_session(use_cache={"cache_name": "./cache/http"})
req = requests_session(fake_ip=True)
req = requests_session(max_retries=Retry(total=3, backoff_factor=1, allowed_methods=["GET"]))
req = requests_session(debug=True)

from wtfutil.httputil import ChunkedConfig
req = requests_session(chunked=ChunkedConfig.aggressive())
```

## RequestsSession hooks

```python
session = requests_session()

@session.pre_request
def add_token(request):
    request.headers["Authorization"] = "Bearer xxx"

@session.pre_send
def log_url(prepared, kwargs):
    print(prepared.url)
```

## httpraw(raw, ssl=False, **kwargs)

Send a raw HTTP packet as text. First line `METHOD PATH HTTP/1.x`; headers `Key: Value`; must include `Host`.

```python
from wtfutil import httpraw

raw = """GET /api/info HTTP/1.1
Host: example.com
"""
resp = httpraw(raw, ssl=True, timeout=10)
```

## Other symbols

| Symbol | Description |
|--------|-------------|
| `EnhancedResponse` | Better debug on `json()` failure |
| `BaseUrlSession` | Fixed base URL |
| `CustomSslContextHttpAdapter` | Legacy TLS renegotiation |
| `ChunkedConfig` / `ChunkedAdapter` | Chunked encoding |
| `DESAdapter` | Randomised cipher list (JA3) |
| `is_private_ip` | Private/loopback; excludes `198.18.0.0/16` |
| `is_internal_url` | Internal IP check for URL |
| `is_wildcard_dns` / `is_wildcard_dns_batch` | Wildcard DNS |
| `get_maindomain` | Registered domain (`tldextract`) |
| `url2ip` | Resolve host |
| `is_port_in_use` | Local port listening |
| `get_base_url` / `build_absolute_url` | URL helpers |
