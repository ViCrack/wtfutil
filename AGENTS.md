## wtfutil 项目概览（给 AI / Agent 看）

本文件为 AI / Agent 提供 wtfutil 的项目结构速览与关键模块说明，便于在回答用户问题或修改代码时快速定位到合适的模块与示例。

---

### 1. 主要入口与导入方式

- **推荐入口**：`from wtfutil import util`
  - 一次性导入 HTTP、文件、字符串、数据库、进程、通知、翻译、单例、通用工具等常用函数。
- **按模块精细导入**：
  - `from wtfutil import httputil`：HTTP 相关
  - `from wtfutil import fileutil`：文件相关
  - `from wtfutil import strutil`：字符串与加解密
  - `from wtfutil import sqlutil`：数据库
  - `from wtfutil import procutil`：进程管理（Windows）
  - `from wtfutil import notifyutil`：通知
  - `from wtfutil import translateutil`：翻译
  - `from wtfutil import imgutil`：随机图片/头像拉取
  - `from wtfutil import singleinstance`：单实例运行

在需要示例代码时，优先引用外部文档目录中的 **`D:\Code\Python\wtfutil-readme\README.md`（英文）** 与 **`README_zh.md`（中文）**，而不是在回答中重复实现逻辑。

---

### 2. 主要模块及用途

- `wtfutil/util.py`
  - 聚合并重导出各子模块的常用函数，是推荐的统一入口。
  - 包含：requests 优化（代理、重试、超时、SSL 处理）、文件读写、字符串处理与加解密、数据库封装、通知工具、翻译、随机头像、单实例、时间测量、唯一队列等。

- `wtfutil/httputil.py`
  - HTTP 工具封装：
    - `requests_session`：带代理、重试、超时等增强能力的会话。
    - `httpraw`：发送原始 HTTP 报文。
  - 示例见 `wtfutil-readme/README.md` 中 HTTP / httputil 章节。

- `wtfutil/fileutil.py`
  - 文件工具：
    - 文本/二进制读写：`read_text` / `read_bytes` / `read_lines` / `write_text` / `write_lines` / `write_json` 等。
    - 文件哈希：`file_md5` / `file_sha1` / `file_sha256`。
    - JAR 分析：`JarAnalyzer`。

- `wtfutil/strutil.py`
  - 字符串和加解密：
    - Base64、URL 编码/解码。
    - 字符串哈希（MD5 / SHA1 / SHA256）。
    - RSA / DES 加解密。
    - 其他工具（前后缀处理、随机字符串、大小写随机等）。

- `wtfutil/sqlutil.py`
  - 数据库封装：
    - `SQLite`、`MYSQL` 工具类。
    - 支持常见 CRUD、批量插入、条件查询等操作。
    - 管理线程安全连接。

- `wtfutil/procutil.py`
  - 进程管理（**仅 Windows 有效**）：
    - 按名称或 PID 查找进程。
    - 挂起 / 恢复指定进程。
  - 示例见 `wtfutil-readme` 文档中 procutil 章节。

- `wtfutil/notifyutil.py`
  - 多通道通知：
    - 聚合方法：`send(title, content)`，将同一条消息并发发送到所有已正确配置的通道。
    - 常用通道：Bark、钉钉、飞书、Telegram、SMTP、ShowDoc、自定义 Webhook 等。
    - 典型用法与配置见 `wtfutil-readme/README_zh.md` 中 notifyutil 与配置章节。

- `wtfutil/translateutil.py`
  - 百度翻译封装：
  - 如 `BaiduTranslateApi.translate("你好", "zh", "en")`。
  - 示例见 `wtfutil-readme` 文档中 translateutil 章节。

- `wtfutil/imgutil.py`
  - 随机头像拉取（多源回退）：
  - `random_avatar_bytes()`：返回图片原始 `bytes`；内置 loliapi、dmoe、xjh、btstu、horosama 等直链/302 源，配置了 apihz 凭证时另含 JSON 源。
  - apihz 配置：`wtfconfig.ini` 的 `[img]` 段或环境变量 `APIHZ_IMG_ID` / `APIHZ_IMG_KEY`（环境变量优先）。

- `wtfutil/singleinstance.py`
  - 单实例运行控制：
    - 上下文管理器形式：`with single_instance(...): ...`
    - 装饰器形式：`@single_instance(flavor_id="job")`
  - 用于防止脚本在同一时间被多开，示例见 `wtfutil-readme` 文档中 singleinstance 章节。

---

### 3. 配置与环境（通知相关）

- 通知配置均通过 `wtfutil.notifyutil.push_config` 管理，加载顺序：
  1. 内置默认值。
  2. `wtfconfig.ini` 中的 `[notify]` 段。
  3. 环境变量（**优先级最高**）。
- `wtfconfig.ini` 的查找路径由 `util.get_resource("wtfconfig.ini")` 决定：
  - 当前工作目录。
  - `resource/wtfconfig.ini`。
  - 用户家目录 `~/wtfconfig.ini`。
- 详细 key 与示例配置：
  - 参见 `wtfutil-readme/README.md` 或 `README_zh.md` 的配置章节。

---

### 4. 示例与文档定位

- 当需要给出具体使用示例时，优先参考：
  - `D:\Code\Python\wtfutil-readme\README.md`（英文：使用示例 + API 参考）。
  - `D:\Code\Python\wtfutil-readme\README_zh.md`（中文：同上，含 httputil 等详细说明）。
- 如需更细分的说明，可结合各子模块源码的 `__all__` 与实现。

### 5. 新增 API 时的文档同步（必须）

**每次新增或变更对外公开 API（新模块、新函数、新配置项等）时，Agent 必须同步更新外部 README：**

- 目标文件：`D:\Code\Python\wtfutil-readme\README.md`
- **仅当该路径下文件存在时**才修改；不存在则跳过，勿新建该仓库外的目录结构。
- 在 README 中补充与现有章节风格一致的**详细用法**：功能说明、代码示例、配置项（如有）、注意事项。
- 同步更新本文件 `AGENTS.md` 中对应模块的简要说明（第 2 节）。
- 同步更新本仓库根目录 `README.md`（简短英文索引，指向 `wtfutil-readme`）。

**不要**再维护 `API_REFERENCE.md`（已合并进 `wtfutil-readme` 文档）。

---

### 6. 外部 README 路径速查

| 文件 | 用途 |
|------|------|
| `D:\Code\Python\wtfutil-readme\README.md` | 面向用户的详细用法与示例（新增 API 时同步更新） |
| 本仓库 `README.md` | 简短英文索引（安装、快速开始、文档链接） |
| 本仓库 `AGENTS.md` | Agent 项目结构与规则（本文件） |

