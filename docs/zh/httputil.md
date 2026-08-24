# wtfutil.httputil

HTTP：增强 Session、原始报文、URL/IP/域名工具、SSL 相关适配器。

```python
from wtfutil.httputil import httpraw, requests_session
```

## TLS 默认策略与兼容补丁

导入 `httputil` 会把进程级默认 HTTPS 上下文切换为不校验证书，并屏蔽 urllib3 的不安全请求警告；这是该工具库面向探测和旧环境兼容场景的默认策略。导入不会修改全局 `requests.Session`、urllib3 连接类或系统代理函数。重定向编码处理只绑定到 `requests_session()` 创建的会话；chunked 连接类也只属于 `ChunkedAdapter`。

以下旧环境兼容函数仍保留：

- `remove_ssl_verify()`：替换进程级默认 HTTPS 上下文；导入时已自动调用。
- `patch_redirect()`：全局修改 `requests.Session.get_redirect_target`。
- `patch_getproxies()`：全局修补旧版 Windows 注册表代理协议。

## requests_session()

工厂函数，返回已配置好的会话。类型：

| 条件 | 返回类型 |
|------|----------|
| `use_cache` 为真 | `requests_cache.CachedSession` |
| `base_url` 非空 | `BaseUrlSession` |
| 其它 | 内部增强 Session |

无论哪种：TLS 证书默认不校验（`verify=False`），HTTPS 使用 `CustomSslContextHttpAdapter` 兼容旧式服务端连接；该兼容上下文同时用于直连和经过代理的 HTTPS 连接。调用方仍可传 `verify=True` 或 CA bundle 路径恢复校验。

### 函数签名

```python
def requests_session(
    proxies: Union[Dict[str, str], int, str, None] = False,
    timeout: Optional[float] = None,
    debug: bool = False,
    base_url: Optional[str] = None,
    user_agent: Optional[str] = None,
    use_cache: Union[bool, Dict[str, Any], None] = None,
    fake_ip: bool | str = False,
    rate_limit: Optional[int] = None,
    chunked: Union[bool, ChunkedConfig] = False,
    max_retries: int = requests.adapters.DEFAULT_RETRIES,
    pool_connections: int = requests.adapters.DEFAULT_POOLSIZE,
    pool_maxsize: int = requests.adapters.DEFAULT_POOLSIZE,
    verify: bool | str = False,
) -> requests.Session: ...
```

### 参数说明

| 参数 | 默认值 | 含义与行为 |
|------|--------|------------|
| `proxies` | `False` | `False`/`None`：不按此处设代理。`dict`：并 `trust_env=False`。`int`：`127.0.0.1:端口`。`str`：HTTP/HTTPS 同一代理 URL。 |
| `timeout` | `None` | 固定到每次 `request` 的默认超时。 |
| `debug` | `False` | 打印原始请求/响应。 |
| `base_url` | `None` | `BaseUrlSession`；请求路径开头的 `/` 会先被去除，再继续拼接到 `base_url` 的路径后。 |
| `user_agent` | `None` | `None` 则随机 UA。 |
| `use_cache` | `None` | `True` 或 `dict` 传给 `CachedSession`。 |
| `fake_ip` | `False` | `True` 随机 IPv4 写入 `X-Forwarded-For`；非空 str 为固定值。 |
| `rate_limit` | `None` | 每秒最大请求数；`<=0` 抛 `ValueError`。 |
| `chunked` | `False` | `True` 或 `ChunkedConfig` 启用分块上传适配器。 |
| `max_retries` | urllib3 默认 | 可传 `urllib3.Retry`。 |
| `pool_connections` / `pool_maxsize` | 10 | 连接池大小。 |
| `verify` | `False` | `False` 不校验证书；`True` 显式开启；字符串可指定 CA bundle 路径。 |

`use_cache` 不能与 `base_url`、`debug` 或 `rate_limit` 组合；这些组合会抛出 `ValueError`，避免静默忽略增强参数。显式传入固定 `user_agent` 时不会初始化随机 UA 提供器。

### 与 requests.Session 的配合

- 仅当通过 **`proxies` 参数**设置代理时，`trust_env=False`。
- 支持 `with requests_session(...) as s:`。
- 单次请求仍可覆盖 `headers`、`timeout` 等。
- `json()` 解析失败时，异常信息会带上 URL、状态码和截断正文预览；响应类型仍是 `requests.Response`。

### 用法示例

```python
from wtfutil.httputil import requests_session
from urllib3 import Retry

req = requests_session()
req = requests_session(verify=True)  # 需要安全校验时显式开启
req = requests_session(proxies=10809, timeout=30)
req = requests_session(timeout=30, max_retries=3, pool_connections=100, pool_maxsize=100)
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
req = requests_session(use_cache={"cache_name": "./data/http_cache"})
req = requests_session(debug=True, timeout=30)
req = requests_session(
    max_retries=Retry(total=3, read=3, backoff_factor=1, allowed_methods=["GET"]),
)
```

导入模块和新建会话都默认关闭证书校验。启用 chunked 不会替换 urllib3 的全局连接方法，并会保留原连接池的 HTTP、HTTPS 或 SOCKS 代理继承关系。

使用 SOCKS 代理需要安装可选依赖：

```bash
pip install "wtfutil[socks]"
```

分块传输：

```python
from wtfutil.httputil import ChunkedConfig, requests_session

s = requests_session(chunked=True)
s = requests_session(chunked=ChunkedConfig.aggressive())
```

### BaseUrlSession 路径拼接

`BaseUrlSession.create_url()` 会把 `base_url` 规范为以 `/` 结尾，并对请求路径执行 `lstrip("/")` 后再调用 `urljoin`。因此开头斜杠**不会替换** base path：

```python
from wtfutil.httputil import requests_session

session = requests_session(base_url="https://example.com/api/v1")
response = session.get("/users")
# 实际 URL：https://example.com/api/v1/users
```

## Session Hook

`prepare_request` 时自动补 `Referer`、`Origin`（若未提供）。非 `use_cache` 时，`requests_session()` 返回的会话还支持：

- `@session.pre_request`：在未 prepare 的 `Request` 上修改。
- `@session.pre_send`：在 `PreparedRequest` 上，第二参数为 `send` 的 `kwargs`。

## httpraw(raw, ssl=False, **kwargs)

将文本形式 HTTP 报文发给服务器。

- 第一行：`METHOD PATH HTTP/1.x`
- 头部 `Key: Value`；必须含 `Host`；会重算 body 的 `Content-Length`
- `ssl=True` 表示 `https://`
- `**kwargs` 传给 `session.request`
- 所有 HTTP 方法的 body 都会保留；仅 `application/json` 或 `+json` 媒体类型会解析后通过 `json=` 发送，其它正文保持原始文本

```python
from wtfutil.httputil import httpraw

raw = """GET / HTTP/1.1
Host: example.com
"""
resp = httpraw(raw, ssl=True, timeout=10)
```

## 其它导出符号

| 符号 | 说明 |
|------|------|
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
| `url2ip` | 解析 URL 或裸主机名；可选返回显式或默认端口 |
| `is_port_in_use` | 本机端口监听 |
| `get_base_url` / `build_absolute_url` | 校验/提取 HTTP(S) base URL，并解析相对 URL 组件 |
