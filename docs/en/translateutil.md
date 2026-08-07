# wtfutil.translateutil

Baidu Translate API wrapper.

```python
from wtfutil.translateutil import BaiduTranslateApi, BaiduTranslateError
```

## BaiduTranslateApi

```python
from wtfutil.translateutil import BaiduTranslateApi, BaiduTranslateError

try:
    with BaiduTranslateApi(appid="xxx", appkey="yyy", timeout=30) as translator:
        result = translator.translate("你好", from_lang="zh", to_lang="en")
except BaiduTranslateError as error:
    print(error)
```

- `__init__(appid, appkey, from_lang='zh', to_lang='en', *, timeout=30, session=None)`
- `translate(query, from_lang=None, to_lang=None) -> str`
- `close()` closes only a session created by the client; caller-provided sessions remain owned by the caller.
- `BaiduTranslateError` reports API error codes and invalid response structures. HTTP errors continue to come from `requests`.

Requests use HTTPS and are rate-limited to about one request per second via `ratelimit`.
