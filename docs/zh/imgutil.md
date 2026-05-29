# wtfutil.imgutil

随机头像拉取（多源回退）、`img_config`。

```python
from wtfutil import random_avatar_bytes, img_config
```

## 符号

| 符号 | 说明 |
|------|------|
| `img_config` | 配置 dict：默认 ← `wtfconfig.ini` `[img]` ← 环境变量 |
| `ImageFetchError` | 全部源失败；`.errors` 为 `(provider, exc)` 列表 |
| `fetch_random_bytes(fetchers, session=None, timeout=30, shuffle=True)` | 自定义 fetcher 列表回退 |
| `random_avatar_bytes(session=None, timeout=30)` | 内置源随机顺序，返回 `bytes` |

内置源（直链/302）：loliapi、dmoe、xjh、btstu、horosama；配置 `APIHZ_IMG_ID` + `APIHZ_IMG_KEY` 时增加 apihz。

## 配置键

| 键 | 说明 |
|----|------|
| `APIHZ_IMG_ID` | apihz id（可选） |
| `APIHZ_IMG_KEY` | apihz key |
| `APIHZ_IMGTYPE` | 查询 `imgtype`，默认 `5` |
| `APIHZ_IMG_TYPE` | 查询 `type`，默认 `1` |

查找路径与 `get_resource("wtfconfig.ini")` 一致。

```python
from wtfutil import random_avatar_bytes

data = random_avatar_bytes()
```
