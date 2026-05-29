# wtfutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

**wtfutil** 是一个面向日常脚本与自动化任务的 Python 工具库，把最常用的那些"轮子"都封装好：增强型 HTTP 会话、文件读写、编码/加解密、SQLite/MySQL、Windows 进程管理、多通道消息推送、翻译、随机图片等，一行导入即可使用。

**作者**：[vicrack](https://github.com/vicrack) &nbsp;|&nbsp;
**English**: [README.md](./README.md) &nbsp;|&nbsp;
**完整 API**：[docs/](docs/README.md)

---

## 安装

```bash
pip install wtfutil
```

需要 Python 3.10+。

---

## 核心功能速览

| 功能 | 亮点 |
|------|------|
| **HTTP** | 代理、重试、速率限制、缓存、伪造 IP、分块传输、随机 UA 一句话搞定 |
| **文件** | `read_lines` / `write_json`，`unique=True` 自动去重，`not_exists_ok` 容错读取 |
| **编码/加解密** | Base64、URL 编码、MD5/SHA1/SHA256、RSA、DES |
| **数据库** | SQLite / MySQL 同一套 API，批量插入、条件查询 |
| **通知推送** | 飞书、钉钉、Telegram、Bark、SMTP、Webhook 等十余个通道，一句 `send()` 并发推送 |
| **单实例** | 上下文管理器 / 装饰器，防止脚本重复运行 |
| **进程管理** | Windows 下按名称/命令行匹配、挂起/恢复/终止进程 |

---

## 快速开始

```python
from wtfutil import requests_session, read_lines, write_json, send, get_resource

# 带代理的 HTTP 会话（端口号即 127.0.0.1:10809）
req = requests_session(proxies=10809, timeout=30)
r = req.get("https://httpbin.org/ip")
print(r.json())

# 读取资源文件（自动查找 resource/ 或 ~ 目录）
lines = read_lines(get_resource("urls.txt"), unique=True)

# 写 JSON
write_json("out.json", {"status": "ok", "count": len(lines)})

# 一句话推送消息到所有已配置通道
send("任务完成", f"共处理 {len(lines)} 条数据")
```

---

## HTTP — `httputil`

```python
from wtfutil import requests_session
from urllib3 import Retry

# 最简用法（随机 UA，关闭 SSL 校验）
req = requests_session()

# 带代理 + 超时
req = requests_session(proxies=10809, timeout=30)

# 自定义重试策略 + 大连接池（高并发爬虫场景）
req = requests_session(
    timeout=30,
    max_retries=Retry(total=5, backoff_factor=0.5, allowed_methods=["GET"]),
    pool_connections=100,
    pool_maxsize=100,
)

# 固定 base_url，后续只写相对路径
req = requests_session(base_url="https://open.feishu.cn/open-apis", timeout=30)
r = req.get("/authen/v1/user_info")

# 限速：每秒最多 5 个请求（防封）
req = requests_session(rate_limit=5)

# 本地 HTTP 缓存，重复请求直接走磁盘
req = requests_session(use_cache={"cache_name": "./data/http_cache"})

# 伪造随机 X-Forwarded-For
req = requests_session(fake_ip=True)

# debug 模式：打印完整请求/响应
req = requests_session(debug=True)
```

发送原始 HTTP 报文：

```python
from wtfutil import httpraw

raw = """POST /api/login HTTP/1.1
Host: example.com
Content-Type: application/json

{"user":"admin","pass":"123"}
"""
resp = httpraw(raw, ssl=True, timeout=10)
```

URL / IP 工具：

```python
from wtfutil import httputil

httputil.is_private_ip("192.168.1.1")       # True
httputil.get_maindomain("sub.example.com")  # "example.com"
httputil.url2ip("example.com")              # "93.184.216.34"
httputil.is_port_in_use(8080)               # False
```

---

## 文件 — `fileutil`

```python
from wtfutil import read_text, read_lines, read_json, write_text, write_lines, write_json
from wtfutil import file_md5, get_resource

# 读行，跳空行，保序去重
lines = read_lines("targets.txt", unique=True)

# 文件不存在时返回空列表（容错读取，不抛异常）
lines = read_lines("state.txt", not_exists_ok=True)

# 读 JSON，文件不存在时返回 {}
config = read_json("config.json", not_exists_ok=True)

# 写 JSON（自动 ensure_ascii=False，缩进 2）
write_json("result.json", {"items": lines, "total": len(lines)})

# 写多行（自动换行）
write_lines("output.txt", ["line1", "line2", "line3"])

# 文件 MD5
print(file_md5("app.zip"))

# 资源文件定位：当前目录 → resource/ → ~/
path = get_resource("blacklist.txt")
blacklist = read_lines(path, unique=True)
```

---

## 字符串与加解密 — `strutil`

```python
from wtfutil import (
    str_md5, str_sha256,
    base64encode, base64decode,
    url_encode, url_decode,
    rsa_encrypt, rsa_decrypt,
    rand_base, get_middle_text,
)

# 哈希
str_md5("hello")                         # "5d41402abc4b2a76b9719d911017c592"
str_sha256(b"data")

# Base64
base64encode(b"hello world")             # "aGVsbG8gd29ybGQ="
base64decode("aGVsbG8gd29ybGQ=")         # b"hello world"

# URL 编码
url_encode("a=1&b=你好")                 # "a%3D1%26b%3D%E4%BD%A0%E5%A5%BD"

# 随机字符串（默认字母+数字）
token = rand_base(32)

# 从 HTML / 响应中提取两标记间的文本
value = get_middle_text(html, 'name="token" value="', '"')

# RSA 加密（支持长数据分段）
encrypted = rsa_encrypt(b"secret data", public_key_pem)
plaintext = rsa_decrypt(encrypted, private_key_pem)
```

---

## 数据库 — `sqlutil`

```python
from wtfutil import SQLite, MYSQL, next_id

# SQLite
db = SQLite("data.db")

# 建表 + 插入
db.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        url TEXT,
        status INTEGER DEFAULT 0
    )
""")
db.insert("items", {"id": next_id(), "url": "https://a.com", "status": 0})

# 批量插入
rows = [{"id": next_id(), "url": u, "status": 0} for u in url_list]
db.insert_many("items", rows)

# 查询
row = db.select_one("items", {"url": "https://a.com"})
all_rows = db.select("items", {"status": 0})

# 更新 / 删除
db.update("items", {"status": 1}, {"url": "https://a.com"})
db.delete("items", {"status": 0})

# MySQL（同一套 API）
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "xxx", "url": "https://b.com"})
```

---

## 通知推送 — `notifyutil`

通过 `wtfconfig.ini` 或环境变量配置通道，之后无论加几个通道，代码都只写一行：

```python
from wtfutil import send, push_config

# 方式一：ini 文件（推荐）
# [notify]
# FEISHU_KEY = your_webhook_key
# TG_BOT_TOKEN = 123456:xxx
# TG_USER_ID = 88888888
# BARK_PUSH = https://api.day.app/your_key

# 方式二：运行时直接赋值
push_config["FEISHU_KEY"] = "xxx"
push_config["CONSOLE"] = "true"   # 同时输出到控制台

# 一句话并发推到所有已配置通道
send("爬虫异常", "目标站点返回 403，已暂停 5 分钟")
```

也可单独调用某个通道：

```python
from wtfutil import feishu_bot, telegram_bot

feishu_bot("告警", "磁盘使用率超过 90%")
telegram_bot("告警", "磁盘使用率超过 90%")
```

---

## 单实例运行 — `singleinstance`

防止定时任务或脚本重复启动，上下文管理器和装饰器两种用法：

```python
from wtfutil import single_instance, SingleInstanceException

# 上下文管理器
try:
    with single_instance(flavor_id="crawler_job"):
        run_crawler()
except SingleInstanceException:
    print("已有实例在运行，跳过本次")

# 装饰器
from wtfutil import singleinstance

@singleinstance.single_instance(flavor_id="data_sync")
def sync_data():
    ...
```

---

## Windows 进程管理 — `procutil`

```python
from wtfutil import procutil

# 按脚本路径查找 Python 进程
procs = procutil.find_python_by_script("worker.py")

# 按命令行子串查找
procs = procutil.find_python_by_cmdline("celery worker")

# 挂起 / 恢复 / 终止
procutil.suspend_process(pid)
procutil.resume_process(pid)
procutil.kill_process(pid)
```

CLI 工具 `pykill`（安装后全局可用）：

```bash
pykill                       # 列出全部 Python 进程，交互式多选后 kill
pykill worker.py             # 直接按脚本路径终止
pykill worker.py -l          # 仅列出，不终止
pykill -c "celery worker"    # 按命令行子串匹配
```

---

## 杂项工具 — `util`

```python
from wtfutil import UniqueQueue, measure_time, cut_list, group_data

# 去重队列：相同内容重复 put 会被忽略（适合多线程爬虫任务分发）
q = UniqueQueue()
q.put({"url": "https://a.com"})
q.put({"url": "https://a.com"})  # 忽略
print(q.qsize())  # 1

# 计时装饰器
@measure_time
def heavy_task():
    ...

# 列表按固定大小切块（批量写库、批量请求）
for batch in cut_list(url_list, 50):
    process_batch(batch)

# 按字段分组
from wtfutil import group_data
groups = group_data(rows, group_by="status")  # {"0": [...], "1": [...]}
```

---

## 配置文件

`get_resource("wtfconfig.ini")` 按以下顺序查找，**环境变量优先级最高**：

> 当前工作目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`

```ini
[notify]
CONSOLE = true
FEISHU_KEY =
FEISHU_SECRET =
DD_BOT_TOKEN =
DD_BOT_SECRET =
TG_BOT_TOKEN =
TG_USER_ID =
BARK_PUSH =
SMTP_SERVER =
SMTP_EMAIL =
SMTP_PASSWORD =
WEBHOOK_URL =

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =
```

完整键列表见 `wtfconfig.ini.example`；API 详见 [notifyutil](docs/zh/notifyutil.md)、[imgutil](docs/zh/imgutil.md)。

---

## 模块总览

| 模块 | 说明 | API 文档 |
|------|------|----------|
| `wtfutil.httputil` | 增强 HTTP Session、原始报文、URL/IP/域名工具、SSL 适配器 | [中文](docs/zh/httputil.md) · [EN](docs/en/httputil.md) |
| `wtfutil.fileutil` | 文件读写、哈希、`JarAnalyzer` | [中文](docs/zh/fileutil.md) · [EN](docs/en/fileutil.md) |
| `wtfutil.strutil` | 编码/解码、哈希、RSA/DES、字符串工具 | [中文](docs/zh/strutil.md) · [EN](docs/en/strutil.md) |
| `wtfutil.sqlutil` | SQLite / MySQL 封装、`Database`、SQL 辅助 | [中文](docs/zh/sqlutil.md) · [EN](docs/en/sqlutil.md) |
| `wtfutil.procutil` | Windows 进程管理（仅 Windows） | [中文](docs/zh/procutil.md) · [EN](docs/en/procutil.md) |
| `wtfutil.notifyutil` | 多通道通知推送 | [中文](docs/zh/notifyutil.md) · [EN](docs/en/notifyutil.md) |
| `wtfutil.translateutil` | 百度翻译 API | [中文](docs/zh/translateutil.md) · [EN](docs/en/translateutil.md) |
| `wtfutil.imgutil` | 随机头像拉取（多源回退） | [中文](docs/zh/imgutil.md) · [EN](docs/en/imgutil.md) |
| `wtfutil.singleinstance` | 单实例锁（`SingleInstance`、`@single_instance`） | [中文](docs/zh/singleinstance.md) · [EN](docs/en/singleinstance.md) |
| `wtfutil.util` | 杂项工具、`get_resource`、`UniqueQueue` | [中文](docs/zh/util.md) · [EN](docs/en/util.md) |
| **`pykill`**（CLI） | 列出/终止 Python 进程 | [中文](docs/zh/pykill.md) · [EN](docs/en/pykill.md) |

所有公开符号均可从包顶层直接导入，`from wtfutil import read_text, requests_session, send, ...`，与 `wtfutil/__init__.py` 的 `__all__` 一致。

---

## 贡献

欢迎在 [GitHub](https://github.com/ViCrack/wtfutil) 提交 Issue 与 Pull Request。

增删公开 API 时请同步：子模块 `__all__`、`wtfutil/__init__.py`、对应 `docs/en/<module>.md` 与 `docs/zh/<module>.md`，必要时更新 [AGENTS.md](./AGENTS.md) 模块简介。
