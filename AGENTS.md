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
  - `from wtfutil import singleinstance`：单实例运行

在需要示例代码时，优先引用 `README.md` / `README_zh.md` 里的现有用法，而不是在回答中重复实现逻辑。

---

### 2. 主要模块及用途

- `wtfutil/util.py`
  - 聚合并重导出各子模块的常用函数，是推荐的统一入口。
  - 包含：requests 优化（代理、重试、超时、SSL 处理）、文件读写、字符串处理与加解密、数据库封装、通知工具、翻译、单实例、时间测量、唯一队列等。

- `wtfutil/httputil.py`
  - HTTP 工具封装：
    - `requests_session`：带代理、重试、超时等增强能力的会话。
    - `httpraw`：发送原始 HTTP 报文。
  - 示例见 `README.md` 中 *HTTP Utilities* 小节。

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
  - 示例见 `README.md` 中 *Process Utilities* 小节。

- `wtfutil/notifyutil.py`
  - 多通道通知：
    - 聚合方法：`send(title, content)`，将同一条消息并发发送到所有已正确配置的通道。
    - 常用通道：Bark、钉钉、飞书、Telegram、SMTP、ShowDoc、自定义 Webhook 等。
    - 典型用法（飞书 / ShowDoc / 自定义 Webhook）与配置示例见 `README.md` 的 *Notification Utilities* 与 *Configuration* 小节，以及 `README_zh.md` 中对应的中文说明。

- `wtfutil/translateutil.py`
  - 百度翻译封装：
    - 如 `BaiduTranslateApi.translate("你好", "zh", "en")`。
  - 示例见 `README.md` 中 *Translation Utilities* 小节。

- `wtfutil/singleinstance.py`
  - 单实例运行控制：
    - 上下文管理器形式：`with single_instance(...): ...`
    - 装饰器形式：`@single_instance(flavor_id="job")`
  - 用于防止脚本在同一时间被多开，示例见 `README.md` 的 *Single Instance Utility* 小节。

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
  - 参见 `README.md` 的 *Configuration* 小节（英文）。
  - 参见 `README_zh.md` 中“通知工具 notifyutil 使用说明”与“通知配置（wtfconfig.ini / 环境变量）”。

---

### 4. 示例与文档定位

- 当需要给出具体使用示例时，优先参考：
  - 根目录 `README.md`（英文，完整 API 示例）。
  - 根目录 `README_zh.md`（中文说明，重点补充 notifyutil 与配置）。
- 如需更细分的说明，可结合：
  - 源码文件（例如 `wtfutil/notifyutil.py` 的 `__all__` 列表与函数实现）。

