# wtfutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

**wtfutil** 是一个面向日常脚本与自动化任务的 Python 工具库，把最常用的那些"轮子"都封装好：增强型 HTTP 会话、文件读写、编码/加解密、SQLite/MySQL、进程管理、多通道消息推送、翻译、随机图片等，并以职责清晰的子模块提供 API。

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

## 负责任使用

本项目中的安全敏感功能仅用于经授权的安全测试、研究、教育，以及管理您拥有或已获得明确评估许可的系统。

请勿使用本软件在未经授权的情况下访问、干扰、修改任何系统或向其部署代码。使用者须自行遵守适用的法律法规、组织政策及第三方服务条款。维护者不认可任何违法或滥用行为，也不对此类使用承担责任。

---

## ⚠️ 1.3.0 不兼容迁移：改用子模块导入

从 1.3.0 开始，**包根不再重新导出函数、类、常量或配置对象**。每个物理子模块是唯一的公开 API 边界，请把旧的包顶层导入拆分到符号实际所属的模块：

```python
# 1.2.x（1.3.0 已不再支持）
from wtfutil import read_lines, get_resource, requests_session

# 1.3.0+
from wtfutil.fileutil import read_lines
from wtfutil.httputil import requests_session
from wtfutil.util import get_resource
```

例如，`MemShellParty` 的规范 SDK 导入是：

```python
from wtfutil.memshellutil import MemShellParty, MemShellPartyError
```

`wtfutil.memshell` 是 CLI 实现模块，不再提供第二套 SDK 符号入口。

原先通过包根属性调用的代码也需要迁移：

```python
# 1.2.x（1.3.0 已不再支持）
import wtfutil

lines = wtfutil.read_lines("urls.txt")
resource_path = wtfutil.get_resource("urls.txt")
session = wtfutil.requests_session()

# 1.3.0+：直接导入符号（推荐）
from wtfutil.fileutil import read_lines
from wtfutil.httputil import requests_session
from wtfutil.util import get_resource

lines = read_lines("urls.txt")
resource_path = get_resource("urls.txt")
session = requests_session()
```

仍可用 `from wtfutil import fileutil, httputil, util` 导入真实存在的公开子模块，再调用 `fileutil.read_lines(...)`、`util.get_resource(...)` 和 `httputil.requests_session(...)`；这属于 Python 的子模块导入，不代表包根继续提供旧符号。

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
| **进程管理** | 按名称/命令行匹配、结束进程（跨平台）；挂起/恢复（Windows） |

---

## 快速开始

```python
from wtfutil.fileutil import read_lines, write_json
from wtfutil.httputil import requests_session
from wtfutil.notifyutil import send
from wtfutil.util import get_resource

# 带代理的 HTTP 会话（端口号即 127.0.0.1:10809）
req = requests_session(proxies=10809, timeout=30)
r = req.get("https://httpbin.org/ip")
print(r.json())

# 读取资源文件（自动查找 resource/ 或 ~ 目录）
resource_path = get_resource("urls.txt")
if resource_path is None:
    raise FileNotFoundError("urls.txt")
lines = read_lines(resource_path, unique=True)

# 写 JSON
write_json("out.json", {"status": "ok", "count": len(lines)})

# 一句话推送消息到所有已配置通道
send("任务完成", f"共处理 {len(lines)} 条数据")
```

---

## HTTP — `httputil`

```python
from wtfutil.httputil import requests_session
from urllib3 import Retry

# 最简用法（随机 UA，默认不校验 TLS 证书）
req = requests_session()

# 需要证书校验时显式开启
verified_req = requests_session(verify=True)

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

# debug 模式：发送前打印请求，成功后打印响应；失败时仍会打印请求
req = requests_session(debug=True)
```

发送原始 HTTP 报文：

```python
from wtfutil.httputil import httpraw

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
from wtfutil.fileutil import (
    file_md5,
    read_json,
    read_lines,
    read_text,
    write_json,
    write_lines,
    write_text,
)
from wtfutil.util import get_resource

# 读行，跳空行，保序去重
lines = read_lines("targets.txt", unique=True)

# 文件不存在时返回空列表（容错读取，不抛异常）
lines = read_lines("state.txt", not_exists_ok=True)

# 读 JSON，文件不存在时返回 {}
config = read_json("config.json", not_exists_ok=True)

# 写 JSON（自动 ensure_ascii=False，缩进 4）
write_json("result.json", {"items": lines, "total": len(lines)})

# 写多行（自动换行）
write_lines("output.txt", ["line1", "line2", "line3"])

# 文件 MD5
print(file_md5("app.zip"))

# 资源文件定位：当前目录 → resource/ → ~/
path = get_resource("blacklist.txt")
if path is None:
    raise FileNotFoundError("blacklist.txt")
blacklist = read_lines(path, unique=True)
```

---

## 字符串与加解密 — `strutil`

```python
from wtfutil.strutil import (
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
base64decode("aGVsbG8gd29ybGQ=")         # "hello world"

# URL 编码
url_encode("a=1&b=你好")                 # "a%3D1%26b%3D%E4%BD%A0%E5%A5%BD"

# 随机字符串（默认小写字母+数字，即 a-z0-9，可用 letters= 自定义字符集）
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
from wtfutil.sqlutil import MYSQL, SQLite, next_id

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
row = db.select_one("items", where_clause={"url": "https://a.com"})
all_rows = db.select("items", where_clause={"status": 0})

# 更新 / 删除
db.update("items", {"status": 1}, {"url": "https://a.com"})
db.delete("items", {"status": 0})

# MySQL（同一套 API）
db = MYSQL(host="127.0.0.1", user="root", password="pass", database="mydb")
db.insert_or_replace("items", {"id": "xxx", "url": "https://b.com"})
```

---

## 通知推送 — `notifyutil`

在导入 `notifyutil` 前通过 `wtfconfig.ini` 或环境变量配置通道，之后无论启用几个通道，代码都只写一行：

```python
from wtfutil.notifyutil import send

# wtfconfig.ini（推荐）
# [notify]
# FEISHU_KEY = your_webhook_key
# TG_BOT_TOKEN = 123456:xxx
# TG_USER_ID = 88888888
# BARK_PUSH = https://api.day.app/your_key
# CMCC_NEWMSG_KEY = ak_example-key

# 一句话并发推到所有已配置通道
send("爬虫异常", "目标站点返回 403，已暂停 5 分钟")
```

运行时直接修改 `push_config` 不会重建已启用通道列表，因此新增通道应使用 ini 或环境变量配置。

也可单独调用某个通道：

```python
from wtfutil.notifyutil import cmcc_newmsg, feishu_bot, telegram_bot

feishu_bot("告警", "磁盘使用率超过 90%")
telegram_bot("告警", "磁盘使用率超过 90%")
cmcc_newmsg("告警", "磁盘使用率超过 90%")
```

---

## 单实例运行 — `singleinstance`

防止定时任务或脚本重复启动，上下文管理器和装饰器两种用法：

```python
from wtfutil.singleinstance import SingleInstance, SingleInstanceException, single_instance

# 上下文管理器
try:
    with SingleInstance(flavor_id="crawler_job"):
        run_crawler()
except SingleInstanceException:
    print("已有实例在运行，跳过本次")

# 装饰器
@single_instance(flavor_id="data_sync")
def sync_data():
    ...
```

---

## 进程管理 — `procutil`

查找 / 结束进程跨平台；挂起 / 恢复仅 Windows。

```python
from wtfutil.procutil import (
    find_python_processes_by_cmdline,
    find_python_processes_by_script,
    kill_python_processes_by_script,
    resume_process_by_pid,
    suspend_process_by_pid,
)

# 按脚本路径查找 Python 进程
procs = find_python_processes_by_script("worker.py")

# 按命令行子串查找
procs = find_python_processes_by_cmdline("celery worker")

# 挂起 / 恢复（仅 Windows）/ 按脚本结束（跨平台）
suspend_process_by_pid(pid)
resume_process_by_pid(pid)
kill_python_processes_by_script("worker.py")
```

CLI 工具 `pykill`（安装后全局可用）：

```bash
pykill                       # 列出全部 Python 进程，交互式多选后 kill
pykill worker.py             # 直接按脚本路径终止
pykill worker.py -l          # 仅列出，不终止
pykill -c "celery worker"    # 按命令行子串匹配
```

CLI 工具 `memshell`（MemShellParty 内存马生成）：

```bash
memshell config
memshell generate --shell-tool Behinder --shell-type Listener -o payload.txt
memshell probe -o payload.txt
memshell install-skill --project   # 安装到 ./.agents/skills/memshell
```

详情见 [docs/zh/memshellutil.md](docs/zh/memshellutil.md)。

---

## 杂项工具 — `util`

```python
from wtfutil.util import UniqueQueue, cut_list, group_data, measure_time

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

# 按字段分组（键保留原值类型）
groups = group_data(rows, group_by="status")  # {0: [...], 1: [...]}
```

---

## 配置文件

由 `wtfutil.configutil` 统一加载（`ensure_section` 按 mtime 热更新）。查找顺序，**环境变量优先级最高**：

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
CMCC_NEWMSG_KEY =

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =

[memshell]
# BASE_URL = https://party.mem.mk
```

完整键列表见 `wtfconfig.ini.example`；API 详见 [configutil](docs/zh/configutil.md)、[notifyutil](docs/zh/notifyutil.md)、[imgutil](docs/zh/imgutil.md)、[memshellutil](docs/zh/memshellutil.md)。

---

## 模块总览

| 模块 | 说明 | API 文档 |
|------|------|----------|
| `wtfutil.httputil` | 增强 HTTP Session、原始报文、URL/IP/域名工具、SSL 适配器 | [中文](docs/zh/httputil.md) · [EN](docs/en/httputil.md) |
| `wtfutil.fileutil` | 文件读写、哈希、`JarAnalyzer` | [中文](docs/zh/fileutil.md) · [EN](docs/en/fileutil.md) |
| `wtfutil.strutil` | 编码/解码、哈希、RSA/DES、字符串工具 | [中文](docs/zh/strutil.md) · [EN](docs/en/strutil.md) |
| `wtfutil.sqlutil` | SQLite / MySQL 封装、`Database`、SQL 辅助 | [中文](docs/zh/sqlutil.md) · [EN](docs/en/sqlutil.md) |
| `wtfutil.procutil` | 进程管理（查找/结束跨平台；挂起/恢复仅 Windows） | [中文](docs/zh/procutil.md) · [EN](docs/en/procutil.md) |
| `wtfutil.configutil` | 统一 `wtfconfig.ini` 加载与 mtime 热更新 | [中文](docs/zh/configutil.md) · [EN](docs/en/configutil.md) |
| `wtfutil.notifyutil` | 多通道通知推送 | [中文](docs/zh/notifyutil.md) · [EN](docs/en/notifyutil.md) |
| `wtfutil.translateutil` | 百度翻译 API | [中文](docs/zh/translateutil.md) · [EN](docs/en/translateutil.md) |
| `wtfutil.memshellutil` | MemShellParty 内存马生成 SDK | [中文](docs/zh/memshellutil.md) · [EN](docs/en/memshellutil.md) |
| `wtfutil.imgutil` | 随机头像拉取（多源回退） | [中文](docs/zh/imgutil.md) · [EN](docs/en/imgutil.md) |
| `wtfutil.singleinstance` | 单实例锁（`SingleInstance`、`@single_instance`） | [中文](docs/zh/singleinstance.md) · [EN](docs/en/singleinstance.md) |
| `wtfutil.util` | 杂项工具、`get_resource`、`UniqueQueue` | [中文](docs/zh/util.md) · [EN](docs/en/util.md) |
| **`pykill`**（CLI） | 列出/终止 Python 进程 | [中文](docs/zh/pykill.md) · [EN](docs/en/pykill.md) |
| **`memshell`**（CLI） | MemShellParty 生成 / probe / install-skill | [中文](docs/zh/memshellutil.md) · [EN](docs/en/memshellutil.md) |

从 1.3.0 起，表中的 `wtfutil.<module>` SDK 子模块都是独立且唯一的公开 API 边界。推荐直接从所属子模块导入符号，例如 `from wtfutil.fileutil import read_text`；也可使用 `from wtfutil import fileutil` 导入物理子模块。包根不维护符号映射、懒加载或包级公开符号列表；`pykill` 与 `memshell` 两行则是控制台命令。

---

## 贡献

欢迎在 [GitHub](https://github.com/ViCrack/wtfutil) 提交 Issue 与 Pull Request。

增删公开 API 时请同步：对应子模块 `__all__`、`docs/en/<module>.md`、`docs/zh/<module>.md` 与测试；新增公开子模块时再更新模块索引和 [AGENTS.md](./AGENTS.md) 模块简介。
