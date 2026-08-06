# wtfutil.memshellutil

MemShellParty HTTP 客户端：查询配置并生成 Java 内存马。默认服务 [https://party.mem.mk](https://party.mem.mk)。CLI 入口为 **`memshell`**（不进入 `__all__`）。

上游： [MemShellParty](https://github.com/ReaJason/MemShellParty) · [Issue #143](https://github.com/ReaJason/MemShellParty/issues/143)

**不做内置缓存**；相同配置若需复用结果，请由调用方自行缓存。

```python
from wtfutil import MemShellParty

with MemShellParty() as client:
    result = client.generate(
        shell_type="Listener",
        target_jre_version=53,
        behinder_pass="pass",
        header_value="secret",
    )
    print(result["packResult"])
    print(result["memShellResult"]["shellToolConfig"])
```

## 配置

优先级：构造参数 `base_url=` > 环境变量 `MEMSHELL_BASE_URL` > `wtfconfig.ini` `[memshell] BASE_URL` > 默认 `https://party.mem.mk`（经 [`configutil`](configutil.md)）。

## MemShellParty

| 方法 | 说明 |
|------|------|
| `get_config()` | `GET /api/config` → `{ server: { shellTool: [shellType…] } }` |
| `get_packers_tree()` | `GET /api/config/packers/tree` |
| `get_command_configs()` | `GET /api/config/command/configs` |
| `generate(body=None, **)` | `POST /api/memshell/generate`；kwargs 映射官方 camelCase 字段 |

默认：`Tomcat` / **Behinder** / `Listener` / JRE `50` / `serverVersion=unknown` / `shrink=True` / `staticInitialize=True` / `packer=DefaultBase64`。`target_jre_version >= 53` 未指定时自动 `byPassJavaModule=True`。Command 时 `encryptor`/`implementationClass` 默认 `RAW`/`RuntimeExec`。

## 参数说明（对齐官方）

| CLI / kwargs | 官方字段 | 含义 |
|--------------|----------|------|
| `--server` / `server` | shellConfig.server | 目标中间件/框架（Tomcat、Jetty、SpringWebMvc…） |
| `--server-version` | shellConfig.serverVersion | 服务版本；少数挂载类型因包名差异才需要 |
| `--shell-tool` | shellConfig.shellTool | 工具类型：Behinder / Godzilla / Command / AntSword… |
| `--shell-type` | shellConfig.shellType | 挂载形态：Listener / Filter / Valve / Servlet / Agent… |
| `--target-jre-version` | shellConfig.targetJreVersion | 目标字节码 class 主版本（50=Java6 … 65=Java21） |
| `--debug` | shellConfig.debug | 调试：注入器打印注入信息，Shell 打印异常堆栈 |
| `--by-pass-java-module` | shellConfig.byPassJavaModule | 绕过 JDK9+ 模块限制（Unsafe defineClass） |
| `--no-shrink` | shellConfig.shrink=false | 默认开启缩小字节码（ASM SKIP_DEBUG） |
| `--probe` | shellConfig.probe | 回显探测：把注入器放入回显马，便于非本地确认注入 |
| `--lambda-suffix` | shellConfig.lambdaSuffix | 类名追加 `$Proxy0$$Lambda$1`，便于绕过部分扫描 |
| `--url-pattern` | injectorConfig.urlPattern | 挂载/匹配 URL（默认 `/*`） |
| `--injector-class-name` | injectorConfig.injectorClassName | 注入器全限定类名（空则随机） |
| `--no-static-initialize` | injectorConfig.staticInitialize=false | 默认开：静态块调构造，适配 `Class.forName(...,true,...)` |
| `--shell-class-name` | shellToolConfig.shellClassName | Shell 全限定类名（空则随机） |
| `--behinder-pass` | shellToolConfig.behinderPass | 冰蝎密码（空则随机） |
| `--godzilla-pass` / `--godzilla-key` | godzillaPass / godzillaKey | 哥斯拉密码/密钥（空则随机） |
| `--ant-sword-pass` | antSwordPass | 蚁剑密码（空则随机） |
| `--password` / `password` | （按 shellTool 映射） | 通用密码 → Behinder/Godzilla/AntSword 对应 *Pass；专用 `--*-pass` 优先 |
| `--key` / `key` | godzillaKey | 通用密钥（哥斯拉）；`--godzilla-key` 优先 |
| `--header-name` / `--header-value` | headerName / headerValue | 入口特征请求头；匹配后才进马逻辑 |
| `--command-param-name` | commandParamName | Command：命令参数名或头名 |
| `--command-template` | commandTemplate | Command：模板，`{command}` 占位 |
| `--encryptor` | encryptor | Command：RAW / BASE64 / DOUBLE_BASE64 |
| `--implementation-class` | implementationClass | Command：RuntimeExec / ForkAndExec |
| `--shell-class-base64` | shellClassBase64 | Custom：自定义 `.class` Base64 |
| `--packer` | packer | 打包格式（DefaultBase64、JSP、SpEL…） |

CLI 也可用 `memshell generate --help` 查看完整说明。

## CLI：`memshell`

```bash
memshell generate --help
memshell generate -o payload.txt
memshell generate --shell-tool Godzilla --shell-type Filter --target-jre-version 53 -o out.txt
memshell install-skill --project
```

- **`-o PATH`**：文件仅写 `packResult`；stdout 为 meta JSON。
- **无 `-o`**：stdout 完整响应 JSON。

## JRE class version

| Java | targetJreVersion |
|------|------------------|
| 6 | 50 |
| 8 | 52 |
| 9 | 53 |
| 11 | 55 |
| 17 | 61 |
| 21 | 65 |

## 辅助

- `build_generate_body(...)` — 组装官方请求体（支持通用 `password` / `key`）
- `resolve_shell_credentials(...)` — 按 shellTool 映射通用密码
- `extract_generate_meta(result, output=...)` — CLI meta
- `MemShellPartyError` — API 错误

测试：`tests/test_memshell.py`（`python -m unittest tests.test_memshell`；`MEMSHELL_SKIP_LIVE=1` 可跳过联调）。
