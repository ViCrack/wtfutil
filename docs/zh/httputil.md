# wtfutil.httputil

HTTP：增强 Session、原始报文、URL/IP/域名工具、SSL 相关适配器。

```python
from wtfutil import requests_session, httpraw
# 或
from wtfutil import httputil
```

## 模块副作用（导入即生效）

导入 `httputil` 时会做这些事（无需手动调用）：

- `urllib3.disable_warnings()`，减少证书告警刷屏。
- `remove_ssl_verify()`：放宽全局 HTTPS 校验（影响**整个进程**内其它用到默认 SSL 上下文的代码，需注意）。
- `patch_redirect()`：修补 `requests` 在部分重定向场景下的编码问题。
- `patch_getproxies()`：在 Windows 上把注册表代理里错误的 `https://` 代理项改成 `http://`。
- 钩住 `urllib3.connection.HTTPConnection`，用于后续 **chunked** 模式下的注释插入等。

## requests_session()

工厂函数，返回已配置好的会话。类型：

| 条件 | 返回类型 |
|------|----------|
| `use_cache` 为真 | `requests_cache.CachedSession` |
| `base_url` 非空 | `BaseUrlSession` |
| 其它 | `RequestsSession` |

无论哪种：`session.verify = False`，HTTPS 使用 `CustomSslContextHttpAdapter`。

### 函数签名

```python
def requests_session(
    proxies: Union[Dict[str, str], int, None] = False,
    timeout: Optional[float] = None,
    debug: bool = False,
    base_url: Optional[str] = None,
    user_agent: Optional[str] = None,
    use_cache: Union[bool, Dict[str, Any], None] = None,
    fake_ip: bool = False,
    rate_limit: Optional[int] = None,
    chunked: Union[bool, ChunkedConfig] = False,
    max_retries: int = requests.adapters.DEFAULT_RETRIES,
    pool_connections: int = requests.adapters.DEFAULT_POOLSIZE,
    pool_maxsize: int = requests.adapters.DEFAULT_POOLSIZE,
) -> RequestsSession: ...
```

类型标注里 `proxies` 未写 `str`，但实现支持 **`str`**；`fake_ip` 为 **非空 str** 时当作固定 `X-Forwarded-For`。

### 参数说明

| 参数 | 默认值 | 含义与行为 |
|------|--------|------------|
| `proxies` | `False` | `False`/`None`：不按此处设代理。`dict`：并 `trust_env=False`。`int`：`127.0.0.1:端口`。`str`：HTTP/HTTPS 同一代理 URL。 |
| `timeout` | `None` | 固定到每次 `request` 的默认超时。 |
| `debug` | `False` | 打印原始请求/响应；响应用 `EnhancedResponse`。 |
| `base_url` | `None` | `BaseUrlSession`；注意 `urljoin` 下以 `/` 开头的路径会替换 base 路径。 |
| `user_agent` | `None` | `None` 则随机 UA。 |
| `use_cache` | `None` | `True` 或 `dict` 传给 `CachedSession`。 |
| `fake_ip` | `False` | `True` 随机 IPv4 写入 `X-Forwarded-For`；非空 str 为固定值。 |
| `rate_limit` | `None` | 每秒最大请求数；`<=0` 抛 `ValueError`。 |
| `chunked` | `False` | `True` 或 `ChunkedConfig` 启用分块上传适配器。 |
| `max_retries` | urllib3 默认 | 可传 `urllib3.Retry`。 |
| `pool_connections` / `pool_maxsize` | 10 | 连接池大小。 |

### 与 requests.Session 的配合

- 仅当通过 **`proxies` 参数**设置代理时，`trust_env=False`。
- 支持 `with requests_session(...) as s:`。
- 单次请求仍可覆盖 `headers`、`timeout` 等。

### 用法示例

```python
from wtfutil import requests_session
from urllib3 import Retry

req = requests_session()
req = requests_session(proxies=10809, timeout=30)
req = requests_session(timeout=30, max_retries=3, pool_connections=100, pool_maxsize=100)
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
req = requests_session(use_cache={"cache_name": "./data/http_cache"})
req = requests_session(debug=True, timeout=30)
req = requests_session(
    max_retries=Retry(total=3, read=3, backoff_factor=1, allowed_methods=["GET"]),
)
```

分块传输：

```python
from wtfutil import httputil

s = httputil.requests_session(chunked=True)
s = httputil.requests_session(chunked=httputil.ChunkedConfig.aggressive())
```

## RequestsSession 与 Hook

`prepare_request` 时自动补 `Referer`、`Origin`（若未提供）。

- `@session.pre_request`：在未 prepare 的 `Request` 上修改。
- `@session.pre_send`：在 `PreparedRequest` 上，第二参数为 `send` 的 `kwargs`。

## httpraw(raw, ssl=False, **kwargs)

将文本形式 HTTP 报文发给服务器。

- 第一行：`METHOD PATH HTTP/1.x`
- 头部 `Key: Value`；必须含 `Host`；会重算 body 的 `Content-Length`
- `ssl=True` 表示 `https://`
- `**kwargs` 传给 `session.request`

```python
from wtfutil import httpraw

raw = """GET / HTTP/1.1
Host: example.com
"""
resp = httpraw(raw, ssl=True, timeout=10)
```

## 其它导出符号

| 符号 | 说明 |
|------|------|
| `EnhancedResponse` | `json()` 失败时更易排错 |
| `BaseUrlSession` | 固定 `base_url` |
| `CustomSslContextHttpAdapter` | 老旧 TLS 兼容 |
| `ChunkedConfig` / `ChunkedAdapter` | 分块编码 |
| `DESAdapter` | TLS 指纹变化 |
| `get_redirect_target` / `patch_redirect` | 重定向编码 |
| `remove_ssl_verify` / `patch_getproxies` | 全局 SSL / 代理修补 |
| `is_private_ip` / `is_valid_ip` | 私网判断排除 `198.18.0.0/16` |
| `is_internal_url` | URL 是否内网 |
| `is_wildcard_dns` / `is_wildcard_dns_batch` | 泛解析检测 |
| `get_maindomain` | 注册域名（`tldextract`） |
| `url2ip` | 主机名解析 |
| `is_port_in_use` | 本机端口监听 |
| `get_base_url` / `build_absolute_url` | URL 拼接 |
