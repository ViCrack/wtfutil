# wtfutil.httputil

Enhanced `requests` session, raw HTTP, URL/IP/DNS tools, SSL adapters.

```python
from wtfutil.httputil import httpraw, requests_session
```

## Default TLS policy and compatibility patches

Importing `wtfutil.httputil` switches the process-wide default HTTPS context to unverified mode and suppresses urllib3 insecure-request warnings. This is the library's compatibility-oriented default. Importing still does not modify the global `requests.Session`, urllib3 connection classes, or OS proxy functions. Redirect handling is bound only to sessions created by `requests_session`; chunked transport classes are local to `ChunkedAdapter`.

The legacy helpers remain available for explicit opt-in compatibility and affect the whole process when called:

- `remove_ssl_verify()` — replace the process-wide default HTTPS context; called automatically during import
- `patch_redirect()` — patch `requests.Session.get_redirect_target` globally
- `patch_getproxies()` — patch old Windows registry proxy handling globally

## requests_session()

Factory returning a pre-configured session (`CachedSession`, `BaseUrlSession`, or `RequestsSession`) with TLS verification disabled by default, retry adapters, and `CustomSslContextHttpAdapter` on HTTPS. Pass `verify=True` or a CA bundle path to opt into verification.

```python
def requests_session(
    proxies=False,          # False/None | dict | int (port) | str (URL)
    timeout=None,
    debug=False,
    base_url=None,
    user_agent=None,
    use_cache=None,         # True | dict(**CachedSession kwargs)
    fake_ip=False,          # True -> random X-Forwarded-For; str -> fixed value
    rate_limit=None,
    chunked=False,          # True | ChunkedConfig
    max_retries=DEFAULT,
    pool_connections=10,
    pool_maxsize=10,
    verify=False,           # bool | CA bundle path
) -> requests.Session: ...
```

**Examples:**

```python
from wtfutil.httputil import ChunkedConfig, requests_session
from urllib3 import Retry

req = requests_session()
req = requests_session(verify=True)  # explicitly enable certificate verification
req = requests_session(proxies=10809, timeout=30)
req = requests_session(timeout=30, max_retries=3, pool_connections=100, pool_maxsize=100)
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
req = requests_session(use_cache={"cache_name": "./cache/http"})
req = requests_session(fake_ip=True)
req = requests_session(max_retries=Retry(total=3, backoff_factor=1, allowed_methods=["GET"]))
req = requests_session(debug=True)

req = requests_session(chunked=ChunkedConfig.aggressive())
```

Importing the module and creating a session both disable certificate verification by default. Enabling chunked uploads does not replace urllib3's global connection methods and preserves the original HTTP, HTTPS, or SOCKS pool inheritance.

Install the optional SOCKS dependency when using SOCKS proxies:

```bash
pip install "wtfutil[socks]"
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
from wtfutil.httputil import httpraw

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
