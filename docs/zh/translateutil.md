# wtfutil.translateutil

百度翻译 API 封装。

```python
from wtfutil.translateutil import BaiduTranslateApi, BaiduTranslateError
```

## BaiduTranslateApi

| 成员 | 说明 |
|------|------|
| `__init__(appid, appkey, from_lang='zh', to_lang='en', *, timeout=30, session=None)` | 构造客户端；可传外部 Session |
| `translate(query, from_lang=None, to_lang=None) -> str` | 翻译文本；`from_lang`/`to_lang` 可覆盖构造默认值 |
| `close()` | 只关闭客户端自行创建的 Session |
| `BaiduTranslateError` | API 错误码或响应结构无效时抛出 |

请求使用 HTTPS，并通过 `ratelimit` 限频（约 1 次/秒）。HTTP 状态错误仍由 `requests` 异常表示。

```python
from wtfutil.translateutil import BaiduTranslateApi, BaiduTranslateError

try:
    with BaiduTranslateApi(appid="xxx", appkey="yyy", timeout=30) as translator:
        print(translator.translate("你好", from_lang="zh", to_lang="en"))
except BaiduTranslateError as error:
    print(error)
```
