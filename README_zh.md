# wtfutil 使用说明与 API 参考（中文）

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

> **版本**：1.2.17（以 PyPI / `setup.py` 中 `__version__` 为准）  
> **正式导出符号**：以各子模块 `__all__` 为准。  
> **英文文档**：[README.md](./README.md)  
> **项目结构速览**（开发仓库）：`AGENTS.md`  

**wtfutil** 是面向日常脚本与自动化场景的 Python 工具库，涵盖 HTTP、文件、字符串与加解密、数据库、Windows 进程、多通道通知、翻译、随机图片等。

```bash
pip install wtfutil
```

---

## 1. 安装与导入

```text
pip install wtfutil
```

**推荐**（聚合常用能力，与 `wtfutil.util` 内容高度重叠）：

```python
from wtfutil import util
# 例如：util.requests_session(), util.read_text(), util.send(...)
```

**顶层包**（`from wtfutil import X`）：`wtfutil/__init__.py` 合并了各子模块 `__all__`，可直接 `from wtfutil import read_text, requests_session, send` 等。

**按子模块精细导入**：

```python
from wtfutil import httputil, fileutil, strutil, sqlutil, procutil, notifyutil, translateutil, imgutil, singleinstance, util
```

---

## 2. 使用示例

推荐 `from wtfutil import util`，与 `from wtfutil import httputil` 等子模块等价能力均可通过 `util` 访问。

### HTTP

```python
from wtfutil import util

req = util.requests_session(proxies=10809, timeout=30)
r = req.get("https://example.com/")
```

### 文件

```python
from wtfutil import util

lines = util.read_lines(util.get_resource("urls.txt"), unique=True)
util.write_json("out.json", {"ok": True})
```

### 通知

```python
from wtfutil import util, notifyutil

util.send("告警", "任务执行完成")

notifyutil.feishu_bot("标题", "正文")
notifyutil.showdoc("标题", "正文")
```

配置见本文末尾 **配置** 章节；`wtfconfig.ini` 的 `[notify]` 段或同名环境变量。

### 随机头像（imgutil）

```python
from wtfutil import util

data = util.random_avatar_bytes()
with open("avatar.jpg", "wb") as f:
    f.write(data)
```

### 单实例

```python
from wtfutil import single_instance, SingleInstanceException

try:
    with single_instance(flavor_id="job"):
        ...
except SingleInstanceException:
    print("已有实例在运行")
```

---

## 3. 模块总览

| 模块 | 说明 |
|------|------|
| `wtfutil.util` | 杂项：去重队列、计时装饰器、日期时间、列表切块、分组、资源路径解析等 |
| `wtfutil.httputil` | HTTP：增强 Session、原始报文、URL/IP/域名工具、SSL 相关适配器 |
| `wtfutil.fileutil` | 文件读写、哈希、目录列举、`JarAnalyzer` |
| `wtfutil.strutil` | 编码/解码、哈希、RSA/DES、字符串工具、UTF-7 等 |
| `wtfutil.sqlutil` | `SQLite` / `MYSQL` 封装、`Database` 抽象、`ScriptRunner`、SQL 拼接辅助 |
| `wtfutil.procutil` | Windows 进程查找、挂起/恢复（仅 Windows） |
| `wtfutil.notifyutil` | 多通道通知、`push_config`、`send` 聚合推送 |
| `wtfutil.translateutil` | 百度翻译 API 封装 |
| `wtfutil.imgutil` | 随机头像拉取（多源回退）、`img_config` |
| `wtfutil.singleinstance` | 单实例锁（文件锁 + portalocker） |

---

## 4. `wtfutil.util`

### 类

| 符号 | 说明 |
|------|------|
| `UniqueQueue` | `queue.Queue` 子类；同一对象（或等价 dict）重复 `put` 会忽略 |

### 装饰器

| 符号 | 说明 |
|------|------|
| `measure_time` | 打印被装饰函数的执行耗时（秒） |

### 函数

| 符号 | 说明 |
|------|------|
| `unique_items(iterable)` | 保序去重 |
| `current_datetime()` | `datetime.now()` |
| `format_datetime(dt, format=...)` | 格式化时间 |
| `parse_datetime(date_string, format=...)` | 解析时间字符串 |
| `cut_list(obj, size)` | 列表按固定长度切片成二维列表 |
| `group_data(data, group_by, remove_duplicates=False)` | 按列索引或 dict 键分组；可选组内去重 |
| `get_resource_dir(basedir=None)` | 向上查找含 `resource` 目录的路径 |
| `get_resource(filename)` | 解析资源文件：当前路径 → `resource/` → `~/filename` |

**`UniqueQueue` 示例**（同一任务只入队一次，常用于多线程抓取）：

```python
from wtfutil import util

q = util.UniqueQueue()
q.put({"url": "https://a.com"})   # 入队
q.put({"url": "https://a.com"})   # dict 内容相同 → 忽略
```

**`get_resource` 示例**：配置文件、黑名单等与脚本相对位置无关时，把文件放在 `resource/` 或用户家目录即可被找到（见第 5 节 `read_lines` 联用）。

> `util` 还通过 `from .xxx import *` 再导出了 **httputil / fileutil / strutil / sqlutil / procutil / notifyutil / singleinstance / translateutil / imgutil** 的全部公开符号，因此 `util.requests_session` 等与对应子模块一致。

---

## 5. `wtfutil.httputil`

### 5.0 模块副作用（导入即生效）

导入 `httputil` 时会做这些事（无需你手动调用）：

- `urllib3.disable_warnings()`，减少证书告警刷屏。
- `remove_ssl_verify()`：放宽全局 HTTPS 校验（影响**整个进程**内其它用到默认 SSL 上下文的代码，需注意）。
- `patch_redirect()`：修补 `requests` 在部分重定向场景下的编码问题。
- `patch_getproxies()`：在 Windows 上把注册表代理里错误的 `https://` 代理项改成 `http://`（与高版本 Python 行为有关）。
- 钩住 `urllib3.connection.HTTPConnection`，用于后续 **chunked** 模式下的注释插入等。

---

### 5.1 `requests_session()`（重点）

工厂函数，返回一个已配置好的会话实例。类型为以下之一：

| 条件 | 返回类型 |
|------|----------|
| `use_cache` 为真 | `requests_cache.CachedSession`（仍挂载本库的适配器与头） |
| `base_url` 非空 | `BaseUrlSession`（继承 `RequestsSession`） |
| 其它 | `RequestsSession` |

**无论哪种，实现里都会：`session.verify = False`，并为 `http://` / `https://` 挂载带重试的连接池适配器；HTTPS 使用 `CustomSslContextHttpAdapter`（含旧式重协商等兼容，便于扫站/老旧服务）。**

#### 函数签名（与源码一致）

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

类型标注里 `proxies` 未写 `str`，但实现支持 **`str`**；`fake_ip` 标注为 `bool`，实现里 **`非空 str` 会当作固定 `X-Forwarded-For` 值**（见下表）。

#### 参数说明

| 参数 | 默认值 | 含义与行为 |
|------|--------|------------|
| **`proxies`** | `False` | **`False`/`None`**：不按此处设置代理（仍可能受环境变量影响，除非你再改 `trust_env`）。**`dict`**：如 `{"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}`，并 **`trust_env = False`**，避免与系统代理混用。**`int`**：等价于本机 `127.0.0.1:该端口`，HTTP/HTTPS 都走该端口（适合 Clash、MITM 代理固定端口）。**`str`**：HTTP 与 HTTPS 使用同一代理 URL。 |
| **`timeout`** | `None` | 非 `None` 时，用 `functools.partial` 固定到 `session.request(..., timeout=timeout)`，之后每次 `get/post/...` 默认带该超时（仍可在单次调用里覆盖）。 |
| **`debug`** | `False` | 为 `True` 时，每次请求后用 `requests_toolbelt.utils.dump` 打印原始请求/响应字节流；响应对象会换成 `EnhancedResponse`，`json()` 失败时打印 URL、状态码与 body 片段便于排错。 |
| **`base_url`** | `None` | 非空时使用 `BaseUrlSession`：`get("/api/foo")` 会与 `base_url` 做 `urljoin` 拼接。注意：`urljoin` 规则下，**路径若以 `/` 开头会替换掉 base 的路径部分**，与相对路径行为不同（与 `requests_toolbelt` 文档一致）。适合 OpenAPI/GitLab/飞书等固定主机前缀的客户端。 |
| **`user_agent`** | `None` | `None` 时用 `fake_useragent.UserAgent().random`；传入字符串则固定该 UA。 |
| **`use_cache`** | `None` | **`None`/`False`**：不缓存。**`True`**：默认 `CachedSession()`。**`dict`**：作为 `CachedSession(**dict)` 的参数，例如本地 SQLite 缓存：`{"cache_name": "./cache/http_cache"}`（实际项目里常用于减少重复下载）。 |
| **`fake_ip`** | `False` | 为 **`True`** 时随机生成中文语境 `faker` 的 IPv4 写入 **`X-Forwarded-For`**。若为 **非空字符串**，源码会把该字符串直接写入 `X-Forwarded-For`（类型标注未体现，但行为存在）。 |
| **`rate_limit`** | `None` | 正整数：每秒最多发起多少次请求；在 `RequestsSession.request` 里用 `sleep` 节流（适合温和爬取）。`<=0` 会在构造 `RequestsSession` 时抛 `ValueError`。 |
| **`chunked`** | `False` | **`True`**：使用 `ChunkedConfig.default()` 启用分块上传适配器（`Transfer-Encoding: chunked`，并按关键词拆分 body，用于部分 WAF/中间件绕过场景）。**`ChunkedConfig` 实例**：自定义块大小、块间延迟、chunk 注释长度、关键词列表等；也可用 `ChunkedConfig.aggressive()`。 |
| **`max_retries`** | urllib3 默认 | 传给 `HTTPAdapter`；可传入 **`urllib3.Retry`** 对象以细粒度控制重试（如仅对 `GET`、指数退避、是否重试读超时等）。 |
| **`pool_connections`** / **`pool_maxsize`** | 默认 10 | 连接池大小。高并发或大量不同主机时，实际项目里常调到 **50～100** 减轻排队。 |

#### 与 `requests.Session` 的配合说明

- **`trust_env`**：仅当通过 **`proxies` 参数**设置了代理时，实现里会置为 **`False`**。若你需要「环境变量代理 + 代码里再改 session」，要自己设回 `True` 或手动设 `proxies`。
- **单次请求**仍可传 `requests` 原有参数：`headers`、`cookies`、`allow_redirects`、`stream` 等。
- **上下文管理器**：返回的 session 支持 `with requests_session(...) as s:`（继承自 `requests.Session`），退出时关闭连接。

#### 用法示例（综合常见业务场景）

**1）最简：默认 Session（证书不校验、随机 UA）**

```python
from wtfutil import util

req = util.requests_session()
r = req.get("https://example.com/")
```

**2）统一超时 + 本机代理端口（如 Clash `10809`）**

```python
req = util.requests_session(proxies=10809, timeout=30)
```

**3）高并发抓取：放大连接池 + 限制重试次数**

```python
req = util.requests_session(
    timeout=30,
    max_retries=3,
    pool_connections=100,
    pool_maxsize=100,
)
```

**4）需要「伪造来源 IP」头（部分站点统计/风控）**

```python
req = util.requests_session(timeout=20, fake_ip=True)
# 或固定值（源码层支持 str）
# req = util.requests_session(fake_ip="203.0.113.1")
```

**5）REST 客户端：固定 `base_url`，只写相对路径**

```python
BASE = "https://open.feishu.cn/open-apis"
req = util.requests_session(base_url=BASE, timeout=30)
r = req.get("/auth/v3/tenant_access_token/internal")  # 自动拼完整 URL
```

**6）减少重复请求：HTTP 缓存**

```python
req = util.requests_session(use_cache={"cache_name": "./data/http_cache"})
```

**7）调试抓包：看完整请求/响应**

```python
req = util.requests_session(debug=True, timeout=30)
req.get("https://httpbin.org/get")
```

**8）细粒度重试（需 `from urllib3 import Retry`）**

```python
from urllib3 import Retry
from wtfutil import util

req = util.requests_session(
    timeout=30,
    max_retries=Retry(
        total=3,
        read=3,
        backoff_factor=1,
        allowed_methods=["GET"],
    ),
)
```

**9）分块传输（WAF/网关绕过，按需使用）**

```python
from wtfutil import httputil

s = httputil.requests_session(chunked=True)
# 或
s = httputil.requests_session(chunked=httputil.ChunkedConfig.aggressive())
```

> 下列用法来自 **`D:\Code\Python\Crawler`** 等工程中的常见模式，已抽象为示例；实际端口、路径请按你的环境修改。

---

### 5.2 `RequestsSession` 与 Hook

`RequestsSession` 在 `prepare_request` 阶段若未显式提供，会自动补 **`Referer`**、**`Origin`**（根据 URL 的 scheme + netloc）。

- **`@session.pre_request`**：注册在 **未 prepare** 的 `Request` 上改 headers、URL 等。
- **`@session.pre_send`**：注册在 **已 PreparedRequest** 上，第二个参数为本次 `send` 的 **`kwargs` 字典**（可改 timeout、proxies 等）。

`rate_limit` 与 `debug` 在 `request()` 一层生效。

---

### 5.3 `httpraw(raw, ssl=False, **kwargs)`

将 **文本形式** 的 HTTP 报文发给服务器。

- 第一行必须是：`METHOD PATH HTTP/1.x`（如 `GET /path HTTP/1.1`）。
- 头部行用 **`Key: Value`**（冒号后要有空格）；解析用 `strutil.extract_dict`。
- 必须包含 **`Host`** 头；实现会删掉 `Content-Length`，按 body 重新构造。
- **`ssl=True`** 表示目标为 `https://`（仍走 `requests_session()` 发送）。
- **`**kwargs`** 会传给 `session.request`（可覆盖 `headers`、`timeout`、`allow_redirects` 等）。

**POST 示例（空行后为 body）：**

```text
POST /api/login HTTP/1.1
Host: example.com
Content-Type: application/x-www-form-urlencoded

user=1&pass=2
```

```python
from wtfutil import httputil

raw = """GET / HTTP/1.1
Host: example.com
"""
resp = httputil.httpraw(raw, ssl=True, timeout=10)
```

---

### 5.4 其它导出符号（速查）

| 符号 | 说明 |
|------|------|
| `EnhancedResponse` | 替换响应类，`json()` 解码失败时更易读 |
| `BaseUrlSession` | 见上文 `base_url` |
| `CustomSslContextHttpAdapter` | HTTPS 适配器，兼容部分老旧 TLS 行为 |
| `ChunkedConfig` / `ChunkedAdapter` | 分块编码与关键词切分 |
| `DESAdapter` | 随机化 Cipher 列表，改变 TLS 指纹（JA3 等场景） |
| `get_redirect_target` / `patch_redirect` | 重定向目标字符串编码修复 |
| `remove_ssl_verify` / `patch_getproxies` | 全局 SSL / 系统代理修补 |
| `is_private_ip` / `is_valid_ip` | IPv4/IPv6；私网判断时 **排除** `198.18.0.0/16`（常见 fake-ip） |
| `is_internal_url` | 根据 URL 主机判断是否内网 |
| `is_wildcard_dns` / `is_wildcard_dns_batch` | 泛解析检测（DNS 查询） |
| `get_maindomain` | 取注册域名（依赖 `tldextract`） |
| `url2ip` | 主机名解析 |
| `is_port_in_use` | 本机端口是否监听 |
| `get_base_url` / `build_absolute_url` | 绝对 URL 拼接 |

---

## 6. `wtfutil.fileutil`

### 6.1 读写与哈希

| 符号 | 参数要点 | 说明 |
|------|----------|------|
| `read_text(filepath, mode='r', encoding='utf-8', not_exists_ok=False, errors=None)` | `mode='rb'` 时不按文本编码读；`not_exists_ok=True` 且文件不存在返回 `''`；`errors` 同内置 `open`（如 `'ignore'`、`'backslashreplace'` 用于脏编码 HTML） | 读整个文件为 str |
| `read_json(filepath, encoding='utf-8', not_exists_ok=False)` | 不存在且 `not_exists_ok=True` 返回 `{}` | 读 JSON 为 dict |
| `read_lines(filepath, encoding='utf-8', not_exists_ok=False, unique=False)` | 跳过空行；`unique=True` 时保序去重 | 适合域名列表、关键词表 |
| `write_text` / `write_lines` / `write_json` | `write_lines` 的 `newline` 与平台转换行为见源码 docstring | 写文件 |
| `file_md5` / `file_sha1` / `file_sha256` | 路径可为 `str` 或 `Path` | 整文件哈希 hex 字符串 |
| `list_files` / `list_directories` | 单层目录，返回子项**全路径** | 非递归 |
| `touch(filepath, mode=0o666, exist_ok=True)` | | 创建或更新时间戳 |

**用法示例（与 Crawler 中常见模式一致）：**

```python
from wtfutil import util

# 资源文件：当前目录 / resource/ / 用户目录
path = util.get_resource("blacklist.txt")
lines = util.read_lines(path, unique=True)

# 可选文件不存在 → 空列表
domains = util.read_lines("./state/domains.txt", not_exists_ok=True)

# 损坏编码的网页文件
html = util.read_text("page.html", errors="backslashreplace")
```

### 6.2 `JarAnalyzer`

构造时传入 `.jar` 路径；自动分析 JDK 版本线索、是否 Spring Boot、是否偏 GUI（`javaw`）、`Main-Class` / 可执行 JAR 等。部分分支依赖本机安装 **`javap`**。

### 6.3 与 `httputil` 联用

从文件读入 URL 或域名列表后，常用 **`httputil.get_maindomain`** 归一化主域名；配合 **`util.UniqueQueue`**（见第 3 节）可做去重抓取队列（Crawler 里常见组合）。

---

## 7. `wtfutil.strutil`

| 类别 | 符号 |
|------|------|
| 类型转换 | `tobytes`, `tostr`, `tobool` |
| 字符串处理 | `removesuffix`, `removeprefix`, `get_middle_text`, `splitlines`, `normalize_spaces`, `align_text`, `match1`, `string_to_bash_variable` |
| URL / Base64 | `url_encode_all`, `url_decode`, `url_encode`, `qp_encode_all`, `uuencode`, `base64decode`, `base64encode`, `base64_urlencode`, `base64_urldecode`, `urlsafe_base64encode`, `urlsafe_base64decode`, `base64pickle`, `base64unpickle` |
| 加解密 | `rsa_encrypt`, `rsa_decrypt`, `des_encrypt`, `des_decrypt` |
| 哈希 | `str_md5`, `str_sha1`, `str_sha256` |
| 随机与编码 | `rand_base`, `rand_case`, `format_bytes`, `extract_dict`, `utf8_overlong_encoding`, `utf7_encode` |

---

## 8. `wtfutil.sqlutil`

### 类

| 符号 | 说明 |
|------|------|
| `Dict` | 支持 `d.key` 访问的 dict 子类 |
| `Database` | 抽象基类，定义通用 CRUD / 查询接口 |
| `SQLite` | SQLite 实现，`__init__(db_file: str)` |
| `MYSQL` | PyMySQL 实现，`__init__(host, user, password, database, charset='utf8mb4', port=3306, ssl=None)` |
| `ScriptRunner` | `run_script(sql)`：按分隔符执行多语句脚本（含简单 `DELIMITER` 处理） |

### `Database` 体系常见方法（具体行为见源码 docstring）

`insert`, `insert_or_replace`, `insert_many`, `update`, `delete`, `count`, `select`, `select_one`, `execute`, `query`, `get`, `record_exists`, `select_by_id`, `fetch_rows`, `fetchone`, `bulk_insert`, `replace`, `exists`, `fetch_by_id`, `close`

### 函数

| 符号 | 说明 |
|------|------|
| `next_id(t=None)` | 50 字符 ID（时间 + UUID） |
| `join_field_value` / `join_field` / `join_value` | 拼接 `UPDATE`/`INSERT` 片段用字符串（占位符风格配合执行） |

---

## 9. `wtfutil.procutil`（Windows）

| 符号 | 说明 |
|------|------|
| `find_process_by_name` | 按进程名找 PID |
| `suspend_process` / `suspend_process_by_pid` | 挂起线程 |
| `resume_process` / `resume_process_by_pid` | 恢复线程 |

---

## 10. `wtfutil.notifyutil`

### 配置

| 符号 | 说明 |
|------|------|
| `push_config` | 配置字典：内置默认值 ← `wtfconfig.ini` `[notify]` ← 环境变量（环境变量优先） |

配置文件搜索与 `util.get_resource("wtfconfig.ini")` 一致：当前工作目录、`resource/wtfconfig.ini`、`~/wtfconfig.ini`。常用 key 见本文 **配置** 章节。

### 聚合发送

| 符号 | 说明 |
|------|------|
| `send(title, content)` | 并发调用所有已配置通道；内容为空则记录错误；可经 `SKIP_PUSH_TITLE` 跳过标题；可选一言（`HITOKOTO`）追加 |

### 单通道函数（均可单独调用；是否生效取决于 `push_config` / 环境变量）

`bark`, `console`, `dingding_bot`, `feishu_bot`, `feishu_text`, `feishu_richtext`, `go_cqhttp`, `gotify`, `iGot`, `serverJ`, `pushdeer`, `chat`, `pushplus_bot`, `qmsg_bot`, `wecom_app`, `WeCom`, `wecom_bot`, `telegram_bot`, `aibotk`, `smtp`, `pushme`, `pipehub`, `xtuis`, `aiops_phone`, `showdoc`, `notifyx`, `chronocat`, `custom_notify`, `one`（一言）

---

## 11. `wtfutil.translateutil`

| 符号 | 说明 |
|------|------|
| `BaiduTranslateApi` | `__init__(appid, appkey, from_lang='zh', to_lang='en')`；`translate(query, from_lang=None, to_lang=None) -> str`；内部使用 `ratelimit` 限频（约 1 次/秒） |

---

## 12. `wtfutil.imgutil`

| 符号 | 说明 |
|------|------|
| `img_config` | 配置字典：默认值 ← `wtfconfig.ini` `[img]` ← 环境变量（环境变量优先） |
| `ImageFetchError` | 所有源均失败；`.errors` 为 `(provider_name, exc)` 列表 |
| `fetch_random_bytes(fetchers, session=None, timeout=30, shuffle=True)` | 通用多 fetcher 回退 |
| `random_avatar_bytes(session=None, timeout=30)` | 内置头像源随机顺序尝试，返回 `bytes`（直链/302：loliapi、dmoe、xjh、btstu、horosama；可选 apihz） |

**配置键**（`[img]` 段或同名环境变量）：

| 键 | 说明 |
|----|------|
| `APIHZ_IMG_ID` | apihz 接口 id（可选；未配置则跳过 apihz 源） |
| `APIHZ_IMG_KEY` | apihz 接口 key |
| `APIHZ_IMGTYPE` | 查询参数 `imgtype`，默认 `5` |
| `APIHZ_IMG_TYPE` | 查询参数 `type`，默认 `1` |

配置文件搜索与 `util.get_resource("wtfconfig.ini")` 一致。

```python
from wtfutil import util

data = util.random_avatar_bytes()
```

---

## 13. `wtfutil.singleinstance`

| 符号 | 说明 |
|------|------|
| `SingleInstanceException` | 已有实例时抛出 |
| `SingleInstance` | 上下文管理器：`with SingleInstance(flavor_id=..., lockfile=...):` |
| `single_instance` | 装饰器工厂：`@single_instance(flavor_id="...")` |

锁文件默认在系统临时目录，由脚本路径 + `flavor_id` 派生命名。

---

## 14. 包级 `wtfutil.__all__`

为以下子模块 `__all__` 的**拼接**（顺序：`fileutil`, `httputil`, `notifyutil`, `procutil`, `sqlutil`, `strutil`, `translateutil`, `imgutil`, `util`, `singleinstance`）。若需确认是否导出某名称，以对应源文件末尾 `__all__` 为准。

---

## 15. 配置（wtfconfig.ini / 环境变量）

`[notify]` 与 `[img]` 均通过 `util.get_resource("wtfconfig.ini")` 查找：当前工作目录、`resource/wtfconfig.ini`、`~/wtfconfig.ini`。**环境变量优先于 ini 文件。**

```ini
[notify]
HITOKOTO = false
CONSOLE = true
BARK_PUSH =
FEISHU_KEY =
FEISHU_SECRET =
DD_BOT_TOKEN =
DD_BOT_SECRET =
TG_BOT_TOKEN =
TG_USER_ID =
SMTP_SERVER =
SMTP_EMAIL =
SMTP_PASSWORD =
SHOWDOC_KEY =
WEBHOOK_URL =
WEBHOOK_METHOD = POST
WEBHOOK_CONTENT_TYPE = application/json
WEBHOOK_BODY =

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =
```

```powershell
$env:FEISHU_KEY = "your_key"
$env:APIHZ_IMG_ID = "your_id"
$env:APIHZ_IMG_KEY = "your_key"
```

---

## 16. 维护说明

- 增删公开 API 时，请同步更新各模块 `__all__`，并修订 **README.md（英文）** 与 **README_zh.md（中文）**。
- 开发仓库 `AGENTS.md` 规定：新增 API 时必须同步更新本目录文档。
