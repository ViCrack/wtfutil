# wtfutil.translateutil

Baidu Translate API wrapper.

```python
from wtfutil import BaiduTranslateApi
```

## BaiduTranslateApi

```python
t = BaiduTranslateApi(appid="xxx", appkey="yyy")
result = t.translate("你好", from_lang="zh", to_lang="en")
```

- `__init__(appid, appkey, from_lang='zh', to_lang='en')`
- `translate(query, from_lang=None, to_lang=None) -> str`

Rate-limited to ~1 request/second via `ratelimit`.
