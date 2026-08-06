---
name: memshell
description: >-
  Generate Java memory shells via MemShellParty using the `memshell` CLI.
  Use when the user asks for memshell / memory shell / 内存马 / Behinder /
  Godzilla / AntSword / Suo5 / webshell payload generation or packing.
---

# memshell CLI

默认服务：`https://party.mem.mk`（`--base-url` / `MEMSHELL_BASE_URL`）。完整参数说明：`memshell generate --help`。

```bash
memshell install-skill --global    # 或 --project
```

## 标准调用

```bash
memshell generate -o payload.txt \
  --server tomcat --shell-tool behinder --shell-type listener \
  --jre 9 \
  --password PASS --header-name User-Agent --header-value SECRET
```

- **`-o`**：文件只有 `packResult`；不要把 payload 贴进对话。
- **stdout**：meta（类名、实际密码/头、`output` 路径）。
- **`--server` / `--shell-tool` / `--shell-type`**：已知名称内不区分大小写。

最小：`memshell generate -o payload.txt`（Tomcat+Behinder+Listener+JRE6+DefaultBase64）。

## 参数含义（常用）

| Flag | 用途 |
|------|------|
| `--server` | 目标中间件（Tomcat/Jetty/SpringWebMvc…；不区分大小写） |
| `--shell-tool` | 工具类型（Behinder/Godzilla/Command…；不区分大小写） |
| `--shell-type` | 挂载形态（Listener/Filter/Valve…；不区分大小写），须与 tool 匹配 |
| `--jre` | 目标 Java/JRE 发行版本：6 / 8 / 9 / 11 / 17 / 21（默认 6；JDK9+ 用 ≥9） |
| `--by-pass-java-module` | 绕过 JDK9+ 模块（Unsafe defineClass）；JRE≥9 默认自动开 |
| `--no-shrink` | 关闭缩小字节码（默认开 SKIP_DEBUG） |
| `--debug` | 打印注入/异常调试信息 |
| `--probe` | 回显探测模式（注入器放进回显马） |
| `--lambda-suffix` | 类名加 `$Proxy0$$Lambda$1` |
| `--url-pattern` | 挂载路径，默认 `/*` |
| `--no-static-initialize` | 关闭静态块调构造（默认开） |
| `--packer` | 打包格式（DefaultBase64/JSP/SpEL/AgentJar…） |
| `--password` | **推荐**：通用密码，按 `--shell-tool` 自动写入对应 *Pass |
| `--key` | 哥斯拉密钥（配合 Godzilla + `--password`） |
| `--header-name` / `--header-value` | 入口特征头；匹配才进马；值空=随机 |
| `--encryptor` / `--implementation-class` | 仅 Command：默认 RAW / RuntimeExec |
| `--command-param-name` / `--command-template` | 仅 Command：参数名与 `{command}` 模板 |

## 合法组合（勿混用）

### Tomcat

| shellTool | shellType |
|-----------|-----------|
| Behinder | Listener, JakartaListener, Filter, JakartaFilter, Valve, JakartaValve, ProxyValve, JakartaProxyValve, Servlet, JakartaServlet, AgentFilterChain, AgentContextValve |
| Godzilla / Command | 上表 + WebSocket 系；（Command 另有 Upgrade） |
| AntSword | Listener, Filter, Valve, ProxyValve, Servlet, AgentFilterChain, AgentContextValve |
| Suo5 / Suo5v2 / NeoreGeorg | 同 Behinder |
| Proxy | WebSocket, JakartaWebSocket, BypassNginxWebSocket, JakartaWebBypassNginxWebSocket |

### 其它（摘）

| server | shellType 示例 |
|--------|----------------|
| Jetty | Listener, Filter, Servlet, Handler, AgentHandler |
| Undertow | Listener, Filter, Servlet, AgentServletHandler |
| SpringWebMvc | Interceptor, ControllerHandler, AgentFrameworkServlet |
| WebLogic | Listener, Filter, Servlet, AgentServletContext |
| Struts2 | Action |

不确定时：`memshell config` / `packers` / `command-configs`。

## 规则

1. 用 CLI + `-o`，不要手写 curl，不要粘贴大段 payload。
2. Behinder 不要配 WebSocket。
3. 从 stdout meta 取实际密码/头与输出路径。
