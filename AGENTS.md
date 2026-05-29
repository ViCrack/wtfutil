## wtfutil 项目概览（给 AI / Agent 看）

**文档根目录**：[`docs/`](docs/README.md)（按模块拆分的完整 API，`docs/en/` 英文、`docs/zh/` 中文）。

本文件为 AI / Agent 提供 wtfutil 的项目结构速览与关键模块说明，便于在回答用户问题或修改代码时快速定位到合适的模块与示例。

---

### 1. 主要入口与导入方式

**推荐做法**：所有公开符号均可从包顶层直接导入，IDE 可自动补全：

```python
from wtfutil import requests_session, read_text, send, get_resource
```

**按子模块精细导入**（用于只需特定功能、或需要访问子模块内部类时）：

```python
from wtfutil import httputil   # HTTP 相关
from wtfutil import fileutil   # 文件相关
from wtfutil import strutil    # 字符串与加解密
from wtfutil import sqlutil    # 数据库
from wtfutil import procutil   # 进程管理（Windows）
from wtfutil import notifyutil # 通知
from wtfutil import translateutil # 翻译
from wtfutil import imgutil    # 随机图片/头像拉取
from wtfutil import singleinstance # 单实例运行
from wtfutil import util       # 杂项工具（UniqueQueue、measure_time、get_resource 等）
```

- **查详细 API**：优先打开 `docs/zh/<module>.md` 或 `docs/en/<module>.md`（如 `docs/zh/httputil.md`）。
- **快速入门**：根目录 `README.md` / `README_zh.md`（安装、示例、模块索引链接）。

---

### 2. 主要模块及用途

- `wtfutil/_base.py`
  - 私有底层模块（**不含任何 wtfutil 内部依赖**），供各子模块安全导入。
  - 包含：`get_resource(filename)`、`get_resource_dir(basedir=None)`。
  - 这两个函数同时通过 `wtfutil.util` 与 `wtfutil.__init__` 重新导出。

- `wtfutil/util.py`
  - **杂项工具**（不再聚合子模块）：
    - `UniqueQueue`：去重队列（相同 dict 内容重复 put 会被忽略）。
    - `measure_time`：计时装饰器。
    - `unique_items`、`cut_list`、`group_data`：列表/分组工具。
    - `current_datetime`、`format_datetime`、`parse_datetime`：日期时间。
    - `get_resource` / `get_resource_dir`：re-export 自 `_base`。

- `wtfutil/httputil.py`
  - HTTP 工具封装：
    - `requests_session`：带代理、重试、超时、SSL 处理、分块传输、速率限制等增强能力的会话工厂。
    - `httpraw`：发送原始 HTTP 报文。
    - URL/IP/域名工具：`is_private_ip`、`get_maindomain`、`url2ip`、`is_wildcard_dns_batch` 等。
    - TLS 适配器：`CustomSslContextHttpAdapter`、`DESAdapter`。

- `wtfutil/fileutil.py`
  - 文件工具：
    - 文本/二进制读写：`read_text` / `read_lines` / `write_text` / `write_lines` / `write_json` 等。
    - 文件哈希：`file_md5` / `file_sha1` / `file_sha256`。
    - JAR 分析：`JarAnalyzer`。

- `wtfutil/strutil.py`
  - 字符串和加解密：
    - Base64、URL 编码/解码、QP 编码、uuencode。
    - 字符串哈希（MD5 / SHA1 / SHA256）。
    - RSA / DES 加解密。
    - 其他工具（前后缀处理、随机字符串、大小写随机、UTF-7、ghost bits 等）。

- `wtfutil/sqlutil.py`
  - 数据库封装：
    - `SQLite`、`MYSQL` 工具类（继承 `Database` 抽象基类）。
    - 支持常见 CRUD、批量插入、条件查询等操作。
    - `ScriptRunner`：多语句 SQL 脚本执行器。

- `wtfutil/procutil.py`
  - 进程管理（**仅 Windows 有效**）：
    - 按名称或 PID 查找进程；按脚本路径或命令行模式查找 Python 进程。
    - 挂起 / 恢复 / 杀死指定进程。

- `wtfutil/notifyutil.py`
  - 多通道通知：
    - 聚合方法：`send(title, content)`，将同一条消息并发发送到所有已配置通道。
    - 常用通道：Bark、钉钉、飞书、Telegram、SMTP、ShowDoc、自定义 Webhook 等。
    - `push_config`：配置字典，加载顺序：内置默认值 ← ini 文件 ← 环境变量。
    - **不在模块级添加任何 logging Handler**（符合库规范，由调用方配置）。

- `wtfutil/translateutil.py`
  - 百度翻译封装：`BaiduTranslateApi(appid, appkey).translate(query, from_lang, to_lang)`。

- `wtfutil/imgutil.py`
  - 随机头像拉取（多源回退）：
    - `random_avatar_bytes()`：返回图片原始 `bytes`；内置 loliapi、dmoe、xjh、btstu、horosama 等直链/302 源，配置了 apihz 凭证时另含 JSON 源。
    - `_load_img_config()` 延迟加载（首次调用时才读取配置文件）。
    - apihz 配置：`wtfconfig.ini` 的 `[img]` 段或环境变量 `APIHZ_IMG_ID` / `APIHZ_IMG_KEY`（环境变量优先）。

- `wtfutil/singleinstance.py`
  - 单实例运行控制：
    - 上下文管理器形式：`with SingleInstance(flavor_id="job"): ...`
    - 装饰器形式：`@single_instance(flavor_id="job")`
    - 文档：`docs/en/singleinstance.md`、`docs/zh/singleinstance.md`

- `wtfutil/pykill.py`
  - **CLI 工具**（`pyproject.toml` → `console_scripts`：`pykill=wtfutil.pykill:main`），**不在** `__init__.py` / `__all__`。
  - 列出/终止 Python 进程，封装 `procutil` + Rich + questionary。
  - 文档：`docs/en/pykill.md`、`docs/zh/pykill.md`；README 有「命令行与单实例」摘要。

---

### 3. 依赖层级（循环引用规则）

```
_base.py（纯 stdlib，零 wtfutil 依赖）
      ↑
fileutil / httputil / strutil / sqlutil / procutil / singleinstance
      ↑
notifyutil（from ._base + from .httputil；_req 延迟初始化）
imgutil（from ._base + from .httputil；config 延迟加载）
translateutil（from . import util，仅方法内使用）
      ↑
util.py（杂项工具；re-export get_resource from _base）
      ↑
__init__.py（显式导出所有公开符号，不使用 wildcard import）
```

**规则**：子模块若需要 `get_resource`，直接 `from ._base import get_resource`，**不得** `from . import util` 后在模块级调用 util 的函数（会造成循环引用）。

---

### 4. 配置与环境

- 通知配置均通过 `wtfutil.notifyutil.push_config` 管理，加载顺序：
  1. 内置默认值。
  2. `wtfconfig.ini` 中的 `[notify]` 段。
  3. 环境变量（**优先级最高**）。
- `wtfconfig.ini` 的查找路径：当前工作目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`。
- img 配置通过 `wtfutil.imgutil.img_config`，查找路径相同（`[img]` 段）。

---

### 5. 新增 API 时的文档同步（必须）

**每次新增或变更对外公开 API（新模块、新函数、新配置项等）时，Agent 必须同步：**

1. 更新对应子模块的 `__all__`。
2. 更新 `wtfutil/__init__.py` 的显式导入列表与 `__all__`。
3. 更新 **`docs/en/<module>.md`** 与 **`docs/zh/<module>.md`**（该模块的完整 API 说明）。
4. 若新增模块或配置段：更新根 `README.md` / `README_zh.md` 的模块索引表或配置摘要，并更新 [`docs/README.md`](docs/README.md) 索引。
5. 更新本文件 `AGENTS.md` 第 2 节中对应模块的简要说明（一行级）。

---

### 6. 文档路径速查

| 路径 | 用途 |
|------|------|
| `docs/en/*.md` | 英文完整 API（按子模块） |
| `docs/zh/*.md` | 中文完整 API（按子模块） |
| `docs/README.md` | 文档模块索引（中英链接） |
| `README.md` / `README_zh.md` | 快速入门 + 模块索引 + 配置摘要 |
| `AGENTS.md` | Agent 项目结构与规则（本文件） |

---

### 7. Git 提交说明（Agent 撰写 commit message）

**仅在用户明确要求提交时**才执行 `git commit`；message **一律使用简体中文**。

#### 格式

```
<type>: <简短主题（50 字以内，不用句号结尾）>

<可选正文：1～3 行，说明动机或影响范围，仍用中文>
```

- **一行提交**：改动简单时只写首行即可。
- **多行提交**：涉及多模块、破坏性变更或需交代迁移方式时再加正文。

#### type 前缀（小写英文，与仓库历史一致）

| type | 适用场景 |
|------|----------|
| `feat` | 新功能、新公开 API |
| `fix` | 缺陷修复 |
| `docs` | 仅文档 / README / `docs/` |
| `build` | 打包、`pyproject.toml`、`publish.py`、依赖与发布流程 |
| `chore` | 版本号、配置、杂项维护（无功能行为变化） |
| `refactor` | 重构，不改变对外行为 |
| `test` | 测试相关 |
| `perf` | 性能优化 |

#### 撰写要求

1. **主题写「做了什么 + 为了什么」**，避免只罗列文件名（反例：`更新 strutil.py`）。
2. **与 `git diff` 一致**：未改动的模块不要写进 message。
3. **破坏性变更**在正文注明「不兼容」及替代 API（如删除 `fetch_rows` → 改用 `select`）。
4. **不要**在 message 中写敏感信息（密钥、token、完整 `wtfconfig.ini` 内容）。
5. 参考近期历史：`git log --oneline -10`，保持风格一致（如 `docs: 补充 sqlutil 示例`、`build: 迁移到 pyproject.toml`）。

#### 示例

```
docs: 各模块文档补充可运行示例

sqlutil / procutil / fileutil 中英文档增加简短示例，API 表保留作索引。
```

```
fix: 修复 notifyutil 在空正文时不推送的问题
```

```
build: 发布脚本改为仅构建 wheel 并上传 PyPI
```

**不要**使用英文主题行（除非用户明确要求）；**不要**使用 emoji 前缀（除非用户明确要求）。
