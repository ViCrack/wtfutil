# MemShellParty 网络韧性增强设计

日期：2026-08-10

## 背景

`MemShellParty.generate()` 曾出现瞬时建连失败：

```text
HTTPSConnectionPool(host='party.mem.mk', port=443): Max retries exceeded ...
Failed to establish a new connection: [Errno 101] Network is unreachable
```

现场验证结果如下：

- `curl -4` 可通过 IPv4 访问 `https://party.mem.mk/api/config`。
- Python 3.13 下原生 `requests`、`MemShellParty.get_config()` 和 CLI 均可正常访问。
- 24 次并发探测全部成功。
- 服务器没有公网 IPv6 默认路由，但 Python 实际优先连接 IPv4，因此不能将该故障稳定归因于 IPv6。

该问题更符合瞬时路由、DNS 或上游节点抖动。现有客户端没有专门的连接级重试策略，并会把网络异常作为底层 `requests` 异常直接抛出，调用方得到的信息不统一。

## 目标

1. 仅增强 `wtfutil.memshellutil.MemShellParty`，不改变通用 HTTP 层的默认行为。
2. 对服务端大概率尚未收到请求的连接阶段错误做少量自动重试。
3. 不自动重试可能已经被服务端处理的请求，避免重复执行 `POST /api/memshell/generate`。
4. 将网络异常统一包装为 `MemShellPartyError`，同时保留原始异常链。
5. 错误信息可用于定位问题，但不得泄露生成请求中的密码、key、Base64 类数据等敏感内容。
6. 保持现有 SDK 和 CLI 调用方式兼容。

## 非目标

- 不强制使用 IPv4。
- 不修改全局 `socket`、DNS 或 urllib3 地址族行为。
- 不对 HTTP 4xx、5xx、读取超时、协议错误或 JSON 解析失败做自动重试。
- 不为 MemShellParty 增加缓存、健康检查服务或备用域名。
- 不改变外部传入 `session=` 的适配器和重试策略。

## 公共接口

`MemShellParty` 构造函数增加两个可选参数：

```python
MemShellParty(
    base_url: str | None = None,
    timeout: float = 60,
    session: Session | None = None,
    connect_retries: int = 2,
    retry_backoff: float = 0.25,
)
```

参数语义：

- `connect_retries`：连接阶段失败后的最大重试次数；`0` 表示关闭自动重试。
- `retry_backoff`：urllib3 Retry 使用的退避因子；必须是有限的非负数。
- 两个参数只应用于客户端内部创建的 session。
- 传入外部 `session=` 时不挂载或替换调用方的 adapter；调用方继续完全控制重试策略。

参数校验：

- `connect_retries` 必须是大于等于 `0` 的整数，布尔值不作为整数接受。
- `retry_backoff` 必须可转换为有限的非负浮点数；`NaN` 和无穷值均拒绝。
- 非法参数抛出 `ValueError` 或 `TypeError`，沿用项目现有参数错误风格。

## 重试策略

内部 session 使用 `urllib3.util.Retry`，并通过现有 `requests_session(max_retries=...)` 传给 HTTP/HTTPS adapter。

策略约束：

```python
Retry(
    total=connect_retries,
    connect=connect_retries,
    read=0,
    status=0,
    other=0,
    redirect=0,
    backoff_factor=retry_backoff,
    allowed_methods=frozenset({"GET", "POST"}),
)
```

设计依据：

- urllib3 将连接错误定义为服务端大概率尚未收到请求的错误，因此连接级重试可用于 GET 和 POST。
- 读取错误发生时，服务端可能已经开始处理请求，因此 `read=0`。
- 不按状态码重试，避免服务端已完成生成但响应异常时再次生成。
- 默认两次重试用于覆盖短暂网络抖动，同时限制额外等待时间。

如果底层库对某类错误不判定为 connect error，则不扩大到 `other` 重试，优先避免不安全的重复请求。

## 请求与异常处理

新增私有方法统一四个 HTTP API 的发送逻辑：

```python
_request(method: str, path: str, **kwargs: Any) -> Any
```

处理流程：

1. 使用 `_url(path)` 生成完整 URL。
2. 调用 `self.req.request(method, url, ...)`。
3. 捕获 `requests.exceptions.RequestException`。
4. 抛出 `MemShellPartyError`，并使用 `raise ... from exc` 保留原异常。
5. 成功获得响应后继续由 `_parse_response()` 处理 HTTP 状态和 JSON body；若响应为 `httputil.EnhancedResponse`，显式调用 `requests.Response.json()`，避免增强响应在解析失败时打印完整响应正文。

网络错误信息格式应包含：

- HTTP 方法。
- 安全目标：合法 HTTP(S) base URL 只保留 scheme、host、port，并附加固定 API 路径；畸形 base URL 只显示固定 API 路径。
- 底层异常类型；若异常链中存在整数操作系统 errno，则只包含 errno 数字，否则只显示通用 transport error。
- 内部 session 使用的连接重试次数。

不得直接拼接任意底层异常文本，因为代理 URL、认证信息或查询参数可能出现在异常字符串中。

错误信息不得包含：

- JSON 请求体、原始响应 body 或服务端 `error` 字段原文。
- `password`、`key`、`behinderPass`、`godzillaPass`、`godzillaKey`、`antSwordPass`。
- `shellClassBase64` 或生成结果。

现有 `MemShellPartyError.status_code` 和 `body` 属性保持兼容。SDK 产生的网络、HTTP 和响应解析错误均使用 `body=None`，避免异常对象或日志保留响应载荷；HTTP 和解析错误仍保留 `status_code`。原始 `requests` 或 JSON 解析异常通过 `exception.__cause__` 获取，不新增重复的公开 cause 属性。

## 外部 Session 行为

当调用方传入 `session=`：

- `MemShellParty.close()` 仍不关闭该 session。
- 不修改 `session.trust_env`、`session.proxies`、headers 或 adapter。
- `connect_retries` 和 `retry_backoff` 不应用于该 session。
- 网络异常仍统一包装为 `MemShellPartyError`。

该规则避免 SDK 隐式改变调用方已经配置好的代理、证书和重试策略。

## CLI 行为

CLI 参数暂不增加重试开关，使用 SDK 默认值：

- 默认连接重试 2 次。
- 网络错误由现有 `except MemShellPartyError` 输出。
- 保留 `except RequestException` 作为防御性兜底，避免其他 CLI 路径的底层异常导致 traceback。

CLI 仍返回退出码 `1`，不改变 stdout 的成功结果格式。

## 测试

在 `tests/test_memshell.py` 增加以下单元测试：

1. 内部 session 获得 connect-only Retry 配置。
2. `connect_retries=0` 可禁用重试。
3. 非法重试次数和退避参数被拒绝。
4. 外部 session 的 adapter、代理和 `trust_env` 不被修改。
5. GET 网络异常被包装成 `MemShellPartyError`，并保留 `__cause__`。
6. POST 网络异常被包装，错误文本不包含请求体和凭证。
7. HTTP 错误、JSON 错误和响应 `error` 字段只公开固定类别与状态码，不保留响应载荷；真实 `EnhancedResponse` 的非法 JSON 路径不得向 stdout/stderr 打印响应正文。
8. CLI 对包装后的网络错误输出单行错误并返回 `1`，不打印 traceback。

可选 live 测试继续由 `MEMSHELL_RUN_LIVE=1` 控制，不将外部网络稳定性纳入默认测试结果。

## 文档

同步更新：

- `docs/zh/memshellutil.md`
- `docs/en/memshellutil.md`
- `AGENTS.md` 中 MemShellParty 简介

文档应明确：

- 默认仅重试连接阶段失败。
- 不重试读取超时和 HTTP 状态错误。
- 外部 session 自行管理重试。
- 不保证通过自动重试修复持续性出口网络或 DNS 故障。

`AGENTS.md` 必须增加项目级敏感信息保护规则：

- 禁止提交密码、API key、Token、Cookie、Authorization、私钥、证书私钥或真实代理凭证。
- 禁止提交 MemShellParty 生成请求中的真实凭证、`shellClassBase64`、`packResult`、`allPackResults` 或其他可用载荷。
- 示例、测试和文档只使用明显的虚构值，并避免看起来像真实密钥的长随机字符串。
- 调试日志和异常信息不得输出请求体、响应载荷或凭证；提交前检查暂存差异。
- 发现疑似敏感信息时停止提交，先移除并提示轮换已经暴露的凭证。

## 兼容性与风险

兼容性：

- 现有构造调用不需要修改。
- 现有返回结构不变。
- 现有 `MemShellPartyError` 属性不变；SDK 产生的错误不再将原始响应写入 `body`。
- 外部 session 所有权语义不变。

主要风险：

- 瞬时故障时请求耗时增加。默认两次连接重试和较小退避将该影响限制在可控范围内。
- urllib3 不同版本对底层错误分类可能有差异。测试只验证 Retry 配置和异常边界，不依赖真实网络制造特定 errno。
- 自动重试无法修复持续性路由故障，最终错误仍以不含敏感内容的固定摘要暴露。

## 验收标准

1. 默认调用在连接阶段瞬时失败时最多重试 2 次。
2. POST 不发生读取错误或状态码重试。
3. 最终网络失败统一表现为 `MemShellPartyError`，原始异常链可检查。
4. 错误输出不包含凭证或请求体。
5. 外部 session 配置不被修改。
6. 相关单元测试和现有测试通过。
7. 中英文文档与实际行为一致。
