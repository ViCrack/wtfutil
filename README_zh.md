# wtfutil 使用说明（精简版）

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

**wtfutil** 面向日常脚本与自动化：HTTP、文件、字符串与加解密、数据库、Windows 进程、多通道通知、翻译、随机图片等。

**作者**：[vicrack](https://github.com/vicrack)  
**英文文档**：[README.md](./README.md)  
**完整 API 参考**：[docs/](docs/README.md)（按模块拆分，中英对照）  
**开发速览**：[AGENTS.md](./AGENTS.md)

---

## 安装

```bash
pip install wtfutil
```

需要 Python 3.10+。

---

## 快速开始

```python
from wtfutil import requests_session, read_lines, write_json, send, get_resource

req = requests_session(proxies=10809, timeout=30)
r = req.get("https://example.com/")

lines = read_lines(get_resource("urls.txt"), unique=True)
write_json("out.json", {"ok": True})

send("告警", "任务完成")
```

也可按子模块导入：`from wtfutil import httputil, fileutil, notifyutil, util`。

---

## 命令行与单实例

### `pykill` — 终止 Python 进程（CLI）

`pip install wtfutil` 后可用命令 **`pykill`**（未纳入包顶层 `__all__`）。基于 `procutil` 查找进程，用 Rich 表格展示，无参数时可交互多选 PID。

```bash
pykill                          # 列出全部 Python 进程并多选 kill
pykill myscript.py              # 按脚本路径匹配并终止
pykill myscript.py -l           # 仅列出
pykill -c "celery worker"       # 按命令行子串匹配
```

详见 [docs/zh/pykill.md](docs/zh/pykill.md) · [英文](docs/en/pykill.md)

### `singleinstance` — 单实例运行

```python
from wtfutil import single_instance, SingleInstanceException

try:
    with single_instance(flavor_id="job"):
        run_main()
except SingleInstanceException:
    print("已有实例在运行")
```

`flavor_id` 用于同一脚本的多套互斥任务；锁文件默认在系统临时目录。  
详见 [docs/zh/singleinstance.md](docs/zh/singleinstance.md) · [英文](docs/en/singleinstance.md)

---

## 模块总览

| 模块 | 说明 | API 文档 |
|------|------|----------|
| `wtfutil.httputil` | HTTP Session、原始报文、URL/IP/域名 | [英文](docs/en/httputil.md) · [中文](docs/zh/httputil.md) |
| `wtfutil.fileutil` | 文件读写、哈希、`JarAnalyzer` | [英文](docs/en/fileutil.md) · [中文](docs/zh/fileutil.md) |
| `wtfutil.strutil` | 编码、哈希、RSA/DES、字符串工具 | [英文](docs/en/strutil.md) · [中文](docs/zh/strutil.md) |
| `wtfutil.sqlutil` | SQLite / MySQL、`Database` | [英文](docs/en/sqlutil.md) · [中文](docs/zh/sqlutil.md) |
| `wtfutil.procutil` | Windows 进程（仅 Windows） | [英文](docs/en/procutil.md) · [中文](docs/zh/procutil.md) |
| `wtfutil.notifyutil` | 多通道通知 | [英文](docs/en/notifyutil.md) · [中文](docs/zh/notifyutil.md) |
| `wtfutil.translateutil` | 百度翻译 | [英文](docs/en/translateutil.md) · [中文](docs/zh/translateutil.md) |
| `wtfutil.imgutil` | 随机头像 | [英文](docs/en/imgutil.md) · [中文](docs/zh/imgutil.md) |
| `wtfutil.singleinstance` | 单实例锁（`SingleInstance`、`@single_instance`） | [英文](docs/en/singleinstance.md) · [中文](docs/zh/singleinstance.md) |
| `wtfutil.util` | 杂项、`get_resource` | [英文](docs/en/util.md) · [中文](docs/zh/util.md) |
| **`pykill`**（CLI） | 列出/终止 Python 进程（依赖 `procutil`） | [英文](docs/en/pykill.md) · [中文](docs/zh/pykill.md) |

包顶层 `from wtfutil import read_text, ...` 与 `wtfutil/__init__.py` 的 `__all__` 一致。

---

## 配置摘要

`get_resource("wtfconfig.ini")` 查找顺序：当前目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`。**环境变量优先于 ini。**

```ini
[notify]
CONSOLE = true
FEISHU_KEY =
# 完整键见 docs/zh/notifyutil.md

[img]
APIHZ_IMG_ID =
APIHZ_IMG_KEY =
```

详见 [notifyutil](docs/zh/notifyutil.md)、[imgutil](docs/zh/imgutil.md) 与仓库内 `wtfconfig.ini.example`。

---

## 贡献

欢迎在 [GitHub](https://github.com/ViCrack/wtfutil) 提交 Issue 与 Pull Request。

增删公开 API 时请同步：子模块 `__all__`、`wtfutil/__init__.py`、对应 `docs/en/<module>.md` 与 `docs/zh/<module>.md`，必要时更新 [AGENTS.md](./AGENTS.md) 模块简介。
