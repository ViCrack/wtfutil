# wtfutil.translateutil

百度翻译 API 封装。

```python
from wtfutil import BaiduTranslateApi
```

## BaiduTranslateApi

| 成员 | 说明 |
|------|------|
| `__init__(appid, appkey, from_lang='zh', to_lang='en')` | 构造客户端 |
| `translate(query, from_lang=None, to_lang=None) -> str` | 翻译文本；`from_lang`/`to_lang` 可覆盖构造默认值 |

内部使用 `ratelimit` 限频（约 1 次/秒）。

```python
t = BaiduTranslateApi(appid="xxx", appkey="yyy")
print(t.translate("你好", from_lang="zh", to_lang="en"))
```
