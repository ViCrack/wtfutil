## wtfutil 项目概览（给 AI / Agent 看）

**文档根目录**：[`docs/`](docs/README.md)（按模块拆分的完整 API，`docs/en/` 英文、`docs/zh/` 中文）。

本文件为 AI / Agent 提供 wtfutil 的项目结构速览与关键模块说明，便于在回答用户问题或修改代码时快速定位到合适的模块与示例。

---

### 1. 主要入口与导入方式

从 wtfutil 1.3.0 开始，**物理子模块是唯一的公开 API 边界**。函数、类、常量和配置对象必须从其所属子模块导入，推荐写法：

```python
from wtfutil.fileutil import read_text
from wtfutil.httputil import requests_session
from wtfutil.notifyutil import send
from wtfutil.util import get_resource
```

仍支持通过 Python 的常规导入机制导入真实存在的公开子模块：

```python
from wtfutil import fileutil, httputil, procutil

text = fileutil.read_text("example.txt")
session = httputil.requests_session()
```

这只适用于物理子模块，不表示包根重新导出子模块内的符号。`wtfutil/__init__.py` 不维护符号映射、按需懒加载或包级公开符号列表。

- **查详细 API**：优先打开 `docs/zh/<module>.md` 或 `docs/en/<module>.md`（如 `docs/zh/httputil.md`）。
- **快速入门**：根目录 `README.md` / `README_zh.md`（安装、示例、模块索引链接）。
- **迁移规则**：遇到 `from wtfutil import Symbol` 或 `import wtfutil; wtfutil.Symbol`，应查明 `Symbol` 所属模块并改为 `from wtfutil.<module> import Symbol`；混合模块导入必须拆分。

---

### 2. 主要模块及用途

- `wtfutil/_resource.py`
  - 私有资源路径解析层（**不含任何 wtfutil 内部依赖**），供 `util` 与 `configutil` 安全导入。
  - 接收显式锚点路径，不通过调用栈推断内部调用者；不得作为公开 API 写入用户示例。

- `wtfutil/util.py`
  - **杂项工具**（不再聚合子模块）：
    - `UniqueQueue`：生命周期内去重队列（嵌套容器内容等价时重复 put 会被忽略）。
    - `measure_time`：计时装饰器。
    - `unique_items`、`cut_list`、`group_data`：列表/分组工具。
    - `current_datetime`、`format_datetime`、`parse_datetime`：日期时间。
    - `get_resource` / `get_resource_dir`：公开资源解析包装器；底层委托给 `_resource`。

- `wtfutil/httputil.py`
  - HTTP 工具封装：
    - `requests_session`：带代理、重试、超时、TLS、分块传输、速率限制等增强能力的会话工厂；为方便探测和旧环境兼容，默认 `verify=False`，调用方可显式传 `verify=True` 或 CA bundle。
    - 导入模块会把进程级默认 HTTPS context 切换为 unverified，并屏蔽 urllib3 的 `InsecureRequestWarning`；这是必须保留的兼容契约。导入不会修改全局 `requests.Session`、urllib3 连接类或系统代理函数，其余全局兼容补丁由调用方显式启用。
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
    - 不提供不受信任 pickle 的反序列化 API；`base64unpickle` 已移除。

- `wtfutil/sqlutil.py`
  - 数据库封装：
    - `SQLite`、`MYSQL` 工具类（继承 `Database` 抽象基类）。
    - 支持常见 CRUD、批量插入、条件查询等操作。
    - `ScriptRunner`：多语句 SQL 脚本执行器。

- `wtfutil/procutil.py`
  - 进程管理（基于 `psutil`，**跨平台**）：按名称 / 脚本路径 / 命令行查找与结束 Python 进程。
  - 挂起 / 恢复线程：**仅 Windows**（非 Windows 调用抛 `OSError`）；不依赖 `pywin32`。
  - Windows ctypes 后端位于私有模块 `_winproc.py`，并只在 Windows 挂起 / 恢复路径中按需导入。

- `wtfutil/configutil.py`
  - 统一 `wtfconfig.ini` 加载：`get_wtfconfig_path` / `merge_section` / `ensure_section` / `reload_wtfconfig`。
  - 优先级：defaults ← ini 段 ← env；按 path+mtime 缓存，mtime 变化时热合并。
  - 文档：`docs/en/configutil.md`、`docs/zh/configutil.md`；测试：`tests/test_configutil.py`。

- `wtfutil/notifyutil.py`
  - 多通道通知：
    - 聚合方法：`send(title, content)`，将同一条消息并发发送到所有已配置通道。
    - 常用通道：Bark、钉钉、飞书、Telegram、SMTP、ShowDoc、自定义 Webhook、中国移动新消息（`cmcc_newmsg`，`websocket-client` 短连接）等。
    - `push_config`：经 `configutil.ensure_section`（`[notify]`）；`send` 前刷新，mtime 变则重建通道列表。
    - **不在模块级添加任何 logging Handler**（符合库规范，由调用方配置）。

- `wtfutil/translateutil.py`
  - 百度翻译封装：`BaiduTranslateApi(appid, appkey).translate(query, from_lang, to_lang)`；接口错误抛 `BaiduTranslateError`。

- `wtfutil/memshellutil.py`
  - MemShellParty HTTP 客户端：`MemShellParty(base_url=...).generate(...)` 返回 `MemShellGenerateResult`；`generate_probe(...)` 返回 `ProbeGenerateResult`；`get_config` / `get_packers_tree` / `get_command_configs`。
  - 默认 `https://party.mem.mk`；`[memshell] BASE_URL` / env `MEMSHELL_BASE_URL`（经 `configutil`）；默认 `shellTool=Behinder`；**无内置缓存**（调用方自行缓存）。
  - 目标运行时用 `jre=` / CLI `--jre`（6/8/9/11/17/21/22，后续版本按标准映射）；兼容 `target_jre_version`。
  - `server` / `shell_tool` / `shell_type` / `method` / `content` 可用 `Server` / `ShellTool` / `ShellType` / `ProbeMethod` / `ProbeContent` 枚举，已知名称内忽略大小写。
  - 内部 session 默认仅对连接阶段失败重试 2 次；网络异常统一包装为 `MemShellPartyError`。异常可带上服务端 `error` 字符串，但不得输出请求体、`packResult`、凭证或其它生成载荷；外部 session 的重试策略不被修改。
  - 通用凭证：`password` / `key`（或 CLI `--password` / `--key`）按 `shellTool` 映射到 `behinderPass` / `godzillaPass`+`godzillaKey` / `antSwordPass`。
  - 文档：`docs/en/memshellutil.md`、`docs/zh/memshellutil.md`；测试：`tests/test_memshell.py`（含可选 live 联调）。

- `wtfutil/memshell.py`
  - **CLI 实现模块**（`console_scripts`：`memshell=wtfutil.memshell:main`），不属于公开 SDK 子模块。
  - 子命令：`generate` / `probe`（`-o` 只写 packResult）、`config` / `packers` / `command-configs`、`install-skill`（`--global` / `--project` → `.agents/skills`）。
  - Skill 源：`wtfutil/skills/memshell/SKILL.md`。

- `wtfutil/daydaymaputil.py`
  - DayDayMap SDK：`DayDayMapClient.count()` 固定匿名聚合优先；不可用且有 Key 时自动用单行 API 计数（可能扣积分）。
  - Key 池、聚合计数、分桶和资产去重辅助逻辑位于本文件。
  - `find_key_file()` 按工作目录、`resource/`、用户目录寻找第一份 `daydaymap_keys.txt`；`load_keys()` 和 `from_key_file()` 可省略路径启用发现。SDK 不读 CLI 凭证环境变量，普通构造器不自动加载文件。
  - `search()` 流式分页，外部 Key 文件加载和轮询；2001/2003/2004 换 Key 重试同页，2005 仅标记窗口截断。聚合计数始终标记估算，`ip_num` 不当成资产总量。
  - `max_effort` 一层聚合拆分及资产去重，不保证完整；配额状态仅客户端生命周期有效，无数据库依赖。
  - `build_query()` 始终添加 `ip.tag!="蜜罐"`，原查询带括号；`is_china`（大陆排除港澳台）/`is_domain` 可选，默认不限制地域/域名/IPv4。免费聚合、回退、分页与拆分均保留过滤，不能保证排除未标记蜜罐。
  - `query_from_icon()` 为图标原字节 MD5，`query_from_certificate()` 为 HTTPS 叶子 DER MD5；返回原始条件供 count/search 使用。`daydaymaputil.py` 内部私有实现管理有界图标下载和 TLS/SNI/CONNECT/HTTPS/SOCKS 传输，并脱敏来源错误。显式代理优先且失败不直连，否则遵循环境/系统代理和 NO_PROXY。
  - `search(on_count=...)` 在首条资产前报告免费预检或首个正常 API total，不额外发付费计数请求。
  - 文档：`docs/en/daydaymaputil.md`、`docs/zh/daydaymaputil.md`；测试：`tests/test_daydaymap*.py`（SDK、来源、真实本地代理与子进程管道）。

- `wtfutil/daydaymap.py`
  - **CLI 实现模块**（`daydaymap=wtfutil.daydaymap:main`），只导出 `main`，SDK 符号从 `daydaymaputil` 导入。
  - 扁平入口默认搜索，`--count` 计数；位置参数 `search` / `count` 不作为查询词（如需查同名字面量使用 `-q count`）。`--count` 显式搭配 `--fields`/`--exclude-fields`/`--page-size`/`--limit`/`--max-effort`/`--max-effort-depth`/`--format`/`--quiet` 也在请求前报错；单独的 `--max-effort-depth` 没有意义，同样拒绝。凭证优先级：重复的 `--key-file` > `DAYDAYMAP_KEY_FILE` > `DAYDAYMAP_API_KEY` > 自动发现的 `daydaymap_keys.txt`。只用首个来源；不依赖 INI 段。
  - 无显式来源且 stdin 非终端时自动逐行读取；混合输入使用 `--query-file -`。UTF-8/BOM/注释/顺序去重，模板仅支持双引号内的 `{}` 并转义输入。图标和证书只解析一次，与各查询 AND 组合。
  - 计数免费优先、有 Key 时允许 API 回退（可能扣积分）。stdout 为 JSONL/URL 数据，stderr 为预检/摘要/错误；截断 4，Key 耗尽 3，中断 130，正常断管 0（含 Windows EINVAL）。输出打开前保护所有命名输入文件和同文件链接，并验证来源。`-o -` 表示 stdout。

- `wtfutil/imgutil.py`
  - 随机头像拉取（多源回退）：
    - `random_avatar_bytes()`：返回图片原始 `bytes`；内置 loliapi、dmoe、xjh、btstu、horosama 等直链/302 源，配置了 apihz 凭证时另含 JSON 源。
    - `_load_img_config()` 经 `configutil.ensure_section`（`[img]`），使用前刷新。
    - apihz 配置：`wtfconfig.ini` 的 `[img]` 段或环境变量 `APIHZ_IMG_ID` / `APIHZ_IMG_KEY`（环境变量优先）。

- `wtfutil/singleinstance.py`
  - 单实例运行控制：
    - 上下文管理器形式：`with SingleInstance(flavor_id="job"): ...`
    - 装饰器形式：`@single_instance(flavor_id="job")`
    - 文档：`docs/en/singleinstance.md`、`docs/zh/singleinstance.md`

- `wtfutil/pykill.py`
  - **CLI 实现模块**（`pyproject.toml` → `console_scripts`：`pykill=wtfutil.pykill:main`），不属于公开 SDK 子模块。
  - 列出/终止 Python 进程，封装 `procutil` + Rich + questionary。
  - 文档：`docs/en/pykill.md`、`docs/zh/pykill.md`；README 有「命令行与单实例」摘要。

---

### 3. 依赖层级（循环引用规则）

包根 `wtfutil/__init__.py` 不聚合公开符号。子模块之间遵守：

```
_resource.py（纯 stdlib，零 wtfutil 依赖）
├── configutil.py（统一 wtfconfig 加载）
└── util.py（公开资源路径函数）

httputil.py ──> strutil.py
notifyutil.py / imgutil.py / memshellutil.py ──> configutil.py + httputil.py
translateutil.py ──> httputil.py + strutil.py
daydaymap.py ──> daydaymaputil.py（SDK、查询辅助 + 私有图标/TLS 传输） ──> httputil.py

procutil.py ──(仅 Windows 挂起/恢复路径)──> _winproc.py
fileutil.py / sqlutil.py / singleinstance.py（无其它 wtfutil 模块依赖）
```

**规则**：公开代码从 `wtfutil.util` 使用 `get_resource`；内部底层模块若需要资源解析，应直接依赖 `_resource` 的显式锚点函数，不得通过 `from . import util` 间接获取。配置读取统一走 `configutil`，不要各自创建 `ConfigObj`。

---

### 4. 配置与环境

- 统一 API：`wtfutil.configutil`（`merge_section` / `ensure_section` / `reload_wtfconfig`）。
- 加载顺序（各段相同）：
  1. 内置默认值。
  2. `wtfconfig.ini` 对应段（`[notify]` / `[img]` / `[memshell]`）。
  3. 环境变量（**优先级最高**）。
- `wtfconfig.ini` 的查找路径：当前工作目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`。
- 热加载：业务在使用前 `ensure_section`；仅当 ini path/mtime 变化时写回目标 dict 并（notify）重建通道列表；未变则保留运行时对手动改写的 dict。
- 各模块字典：`notifyutil.push_config`、`imgutil.img_config`、`memshellutil.memshell_config`（`BASE_URL` ↔ env `MEMSHELL_BASE_URL`）。

---

### 5. 新增 API 时的文档同步（必须）

**每次新增或变更对外公开 API（新模块、新函数、新配置项等）时，Agent 必须同步：**

1. 更新对应子模块的 `__all__`。
2. 更新 **`docs/en/<module>.md`** 与 **`docs/zh/<module>.md`**（该模块的完整 API 说明）。
3. **同步或补充测试用例**（`tests/`，stdlib `unittest` 即可）：覆盖核心行为、边界与错误路径；外部 HTTP live 用例必须默认跳过，并用显式环境变量（如 `MEMSHELL_RUN_LIVE=1`）启用。改完后应能跑通相关测试。
4. 若新增公开子模块或配置段，再更新根 `README.md` / `README_zh.md` 的模块索引或配置摘要、[`docs/README.md`](docs/README.md) 索引，以及本文件第 2 节的模块简介。

无需在包根 `__init__.py` 维护公开符号映射，也没有包根类型声明文件的同步要求。

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

### 7. 敏感信息保护

Agent 修改代码、测试、文档、日志和提交内容时必须遵守：

1. 禁止提交密码、API key、Token、Cookie、Authorization、私钥、证书私钥、真实代理凭证或完整真实环境配置。
2. 禁止提交 MemShellParty 的真实凭证、`shellClassBase64`、`packResult`、`allPackResults` 或其他可直接使用的生成载荷。
3. 示例和测试只使用明显的虚构值，例如 `example-pass`、`example-key`；不要使用看起来像真实密钥的长随机字符串。
4. 异常、调试日志和 CLI stderr 不得包含请求体、响应载荷、认证头或代理凭证；CLI 成功 stdout 和输出文件按用户明确请求的命令契约返回结果。
5. 提交前必须检查所有拟提交文件（包括未跟踪文件）的内容和 `git diff --cached`；至少搜索密码、API key、Token、Cookie、Authorization、私钥、证书私钥、代理凭证、`shellClassBase64`、`packResult` 等敏感项。发现疑似敏感信息时停止提交，先移除并提示轮换已经暴露的凭证。

---

### 8. Git 提交说明（Agent 撰写 commit message）

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
