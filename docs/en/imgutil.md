# wtfutil.imgutil

Random avatar fetch with multi-source fallback.

```python
from wtfutil.imgutil import img_config, random_avatar_bytes
```

## Symbols

| Symbol | Description |
|--------|-------------|
| `img_config` | Config dict: defaults ← `[img]` ← env (via `configutil.ensure_section`) |
| `ImageFetchError` | All sources failed; `.errors` is `(name, exc)` list |
| `fetch_random_bytes(fetchers, session=None, timeout=30, shuffle=True)` | Custom fetcher fallback |
| `random_avatar_bytes(session=None, timeout=30)` | Built-in sources, returns `bytes` |

Built-in sources (random order): `loliapi`, `dmoe`, `xjh`, `btstu`, `horosama`. Optional `apihz` when `APIHZ_IMG_ID` + `APIHZ_IMG_KEY` are set.

Responses must be HTTP 200, at least 256 bytes, and identify as an image through `Content-Type` or a PNG/JPEG/GIF/WebP signature. HTML error and rate-limit pages are rejected and the next provider is tried.

## Configuration

| Key | Description |
|-----|-------------|
| `APIHZ_IMG_ID` | apihz interface ID |
| `APIHZ_IMG_KEY` | apihz key |
| `APIHZ_IMGTYPE` | `imgtype` param (default `5`) |
| `APIHZ_IMG_TYPE` | `type` param (default `1`) |

```python
from wtfutil.imgutil import ImageFetchError, fetch_random_bytes

def my_fetcher(session):
    return session.get("https://my.cdn/avatar.jpg").content

try:
    data = fetch_random_bytes([my_fetcher], timeout=10)
except ImageFetchError as e:
    print(e.errors)
```
