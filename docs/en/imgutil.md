# wtfutil.imgutil

Random avatar fetch with multi-source fallback.

```python
from wtfutil import random_avatar_bytes, img_config
```

## Symbols

| Symbol | Description |
|--------|-------------|
| `img_config` | Config dict: defaults ← `[img]` in ini ← env vars |
| `ImageFetchError` | All sources failed; `.errors` is `(name, exc)` list |
| `fetch_random_bytes(fetchers, session=None, timeout=30, shuffle=True)` | Custom fetcher fallback |
| `random_avatar_bytes(session=None, timeout=30)` | Built-in sources, returns `bytes` |

Built-in sources (random order): `loliapi`, `dmoe`, `xjh`, `btstu`, `horosama`. Optional `apihz` when `APIHZ_IMG_ID` + `APIHZ_IMG_KEY` are set.

## Configuration

| Key | Description |
|-----|-------------|
| `APIHZ_IMG_ID` | apihz interface ID |
| `APIHZ_IMG_KEY` | apihz key |
| `APIHZ_IMGTYPE` | `imgtype` param (default `5`) |
| `APIHZ_IMG_TYPE` | `type` param (default `1`) |

```python
from wtfutil import fetch_random_bytes, ImageFetchError

def my_fetcher(session):
    return session.get("https://my.cdn/avatar.jpg").content

try:
    data = fetch_random_bytes([my_fetcher], timeout=10)
except ImageFetchError as e:
    print(e.errors)
```
