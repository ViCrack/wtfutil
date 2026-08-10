# MemShellParty 网络韧性增强实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 `MemShellParty` 增加安全的连接级重试、统一且不泄露敏感信息的网络异常，并在 `AGENTS.md` 固化敏感信息保护规则。

**架构：** 重试策略只在 `MemShellParty` 内部创建 session 时通过 urllib3 `Retry` 注入，不改变通用 `requests_session()` 的默认行为，也不修改外部传入 session。四个 API 方法统一经过私有 `_request()`，网络异常转换为 `MemShellPartyError` 并保留原始异常链；HTTP 和 JSON 响应继续由 `_parse_response()` 处理。

**技术栈：** Python 3.10+、requests 2.x、urllib3 2.x、stdlib `unittest` / `unittest.mock`、Git。

---

## 文件结构

- 修改：`AGENTS.md`，增加项目级敏感信息保护章节，并将 Git 提交章节顺延编号。
- 修改：`wtfutil/memshellutil.py`，实现重试参数校验、connect-only Retry、统一请求和安全异常摘要。
- 修改：`tests/test_memshell.py`，覆盖重试配置、参数校验、外部 session、异常包装、敏感信息脱敏和 CLI 行为。
- 修改：`docs/zh/memshellutil.md`，记录新构造参数、重试边界和统一异常。
- 修改：`docs/en/memshellutil.md`，同步英文文档。
- 修改：`AGENTS.md` 的 MemShellParty 模块简介，记录默认连接级重试和敏感输出约束。

> 提交约束：`AGENTS.md` 要求仅在用户明确授权时执行 `git commit`。下列 Commit 步骤是检查点；未取得授权时只保留工作区改动并记录建议提交信息。

### 任务 1：固化敏感信息保护规则

**文件：**
- 修改：`AGENTS.md:178-242`

- [ ] **步骤 1：在 Git 提交说明之前加入项目级安全规则**

将现有 `### 7. Git 提交说明` 顺延为 `### 8. Git 提交说明`，并在其前加入：

```markdown
### 7. 敏感信息保护

Agent 修改代码、测试、文档、日志和提交内容时必须遵守：

1. 禁止提交密码、API key、Token、Cookie、Authorization、私钥、证书私钥、真实代理凭证或完整真实环境配置。
2. 禁止提交 MemShellParty 的真实凭证、`shellClassBase64`、`packResult`、`allPackResults` 或其他可直接使用的生成载荷。
3. 示例和测试只使用明显的虚构值，例如 `example-pass`、`example-key`；不要使用看起来像真实密钥的长随机字符串。
4. 异常、调试日志和 CLI 输出不得包含请求体、响应载荷、认证头或代理凭证。
5. 提交前检查暂存差异；发现疑似敏感信息时停止提交，先移除并提示轮换已经暴露的凭证。
```

- [ ] **步骤 2：验证规则存在且章节编号连续**

运行：

```bash
python -c "from pathlib import Path; p=Path('AGENTS.md').read_text(encoding='utf-8'); assert '### 7. 敏感信息保护' in p; assert '### 8. Git 提交说明' in p; assert 'packResult' in p"
```

预期：退出码 `0`，无输出。

- [ ] **步骤 3：检查文档格式**

运行：

```bash
git diff --check -- AGENTS.md
```

预期：退出码 `0`。

- [ ] **步骤 4：Commit 检查点**

用户已明确授权提交时运行：

```bash
git add -- AGENTS.md
git commit -m "docs: 增加敏感信息保护规则"
```

否则记录建议提交信息，不执行 commit。

### 任务 2：为内部 Session 增加连接级重试

**文件：**
- 修改：`tests/test_memshell.py:291-334`
- 修改：`wtfutil/memshellutil.py:10-17`
- 修改：`wtfutil/memshellutil.py:489-505`

- [ ] **步骤 1：编写失败测试，验证默认 Retry 配置**

在 `TestMemShellPartyClient` 增加：

```python
    @mock.patch("wtfutil.memshellutil.requests_session")
    def test_internal_session_uses_connect_only_retry(self, session_factory):
        session_factory.return_value = mock.Mock()

        client = MemShellParty(base_url="https://example.test")

        retry = session_factory.call_args.kwargs["max_retries"]
        self.assertEqual(retry.total, 2)
        self.assertEqual(retry.connect, 2)
        self.assertEqual(retry.read, 0)
        self.assertEqual(retry.status, 0)
        self.assertEqual(retry.other, 0)
        self.assertEqual(retry.redirect, 0)
        self.assertEqual(retry.backoff_factor, 0.25)
        self.assertEqual(retry.allowed_methods, frozenset({"GET", "POST"}))
        client.close()

    @mock.patch("wtfutil.memshellutil.requests_session")
    def test_connect_retries_can_be_disabled(self, session_factory):
        session_factory.return_value = mock.Mock()

        client = MemShellParty(connect_retries=0)

        retry = session_factory.call_args.kwargs["max_retries"]
        self.assertEqual(retry.total, 0)
        self.assertEqual(retry.connect, 0)
        client.close()
```

- [ ] **步骤 2：编写失败测试，验证参数边界**

```python
    def test_retry_options_reject_invalid_values(self):
        for value in (-1, True, 1.5, "2"):
            with self.subTest(connect_retries=value):
                with self.assertRaises((TypeError, ValueError)):
                    MemShellParty(connect_retries=value)

        for value in (-0.1, "invalid", True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(retry_backoff=value):
                with self.assertRaises((TypeError, ValueError)):
                    MemShellParty(retry_backoff=value)
```

- [ ] **步骤 3：编写失败测试，验证外部 Session 不被修改**

```python
    @mock.patch("wtfutil.memshellutil.requests_session")
    def test_external_session_retry_configuration_is_untouched(self, session_factory):
        session = mock.Mock()
        adapter = object()
        session.adapters = {"https://": adapter}
        session.proxies = {"https": "http://proxy.example"}
        session.trust_env = False

        client = MemShellParty(
            session=session,
            connect_retries=5,
            retry_backoff=1.0,
        )

        session_factory.assert_not_called()
        self.assertIs(client.req, session)
        self.assertIs(session.adapters["https://"], adapter)
        self.assertEqual(session.proxies, {"https": "http://proxy.example"})
        self.assertFalse(session.trust_env)
        client.close()
        session.close.assert_not_called()
```

- [ ] **步骤 4：运行新增测试并确认失败**

运行：

```bash
python -m unittest tests.test_memshell.TestMemShellPartyClient -v
```

预期：新增测试 FAIL，原因包括构造函数不接受 `connect_retries`，以及内部 session 尚未收到 `max_retries`。

- [ ] **步骤 5：实现参数校验和 Retry 配置**

在导入区加入：

```python
import math

from urllib3.util import Retry
```

将构造函数扩展为：

```python
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 60,
        session: Session | None = None,
        connect_retries: int = 2,
        retry_backoff: float = 0.25,
    ) -> None:
        if isinstance(connect_retries, bool) or not isinstance(connect_retries, int):
            raise TypeError("connect_retries must be a non-negative integer")
        if connect_retries < 0:
            raise ValueError("connect_retries must be a non-negative integer")
        if isinstance(retry_backoff, bool):
            raise TypeError("retry_backoff must be a finite non-negative number")
        try:
            retry_backoff_value = float(retry_backoff)
        except (TypeError, ValueError) as exc:
            raise TypeError("retry_backoff must be a finite non-negative number") from exc
        if retry_backoff_value < 0 or not math.isfinite(retry_backoff_value):
            raise ValueError("retry_backoff must be a finite non-negative number")

        _load_memshell_config()
        self.base_url = (base_url or memshell_config.get("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.connect_retries = connect_retries
        self.retry_backoff = retry_backoff_value
        self._owns_session = session is None
        if session is None:
            retry = Retry(
                total=connect_retries,
                connect=connect_retries,
                read=0,
                status=0,
                other=0,
                redirect=0,
                backoff_factor=retry_backoff_value,
                allowed_methods=frozenset({"GET", "POST"}),
            )
            self.req = requests_session(timeout=timeout, max_retries=retry)
        else:
            self.req = session
```

同步构造函数 docstring，明确重试参数只作用于内部 session。

- [ ] **步骤 6：运行客户端测试验证通过**

运行：

```bash
python -m unittest tests.test_memshell.TestMemShellPartyClient -v
```

预期：全部 PASS。

- [ ] **步骤 7：Commit 检查点**

用户已明确授权提交时运行：

```bash
git add -- wtfutil/memshellutil.py tests/test_memshell.py
git commit -m "feat: 为 MemShellParty 增加连接级重试"
```

否则记录建议提交信息，不执行 commit。

### 任务 3：统一网络异常并保护敏感信息

**文件：**
- 修改：`tests/test_memshell.py:291-334`
- 修改：`wtfutil/memshellutil.py:10-17`
- 修改：`wtfutil/memshellutil.py:517-586`

- [ ] **步骤 1：把现有成功路径测试切换到统一 request 调用**

将 `test_get_config` 和 `test_generate_posts_json` 的 mock 从 `session.get` / `session.post` 改为 `session.request`：

```python
    def test_get_config(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp({"Tomcat": {"Behinder": ["Listener"]}})
        client = MemShellParty(base_url="https://example.test", session=session)

        cfg = client.get_config()

        self.assertEqual(cfg["Tomcat"]["Behinder"], ["Listener"])
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/api/config"))
        self.assertEqual(kwargs["timeout"], 60)
        client.close()
```

```python
    def test_generate_posts_json(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(
            {
                "packResult": "abc",
                "memShellResult": {"shellClassName": "S", "shellToolConfig": {"pass": "p"}},
            }
        )
        client = MemShellParty(base_url="https://example.test/", session=session)

        result = client.generate(shell_tool="Behinder", behinder_pass="example-pass")

        self.assertEqual(result["packResult"], "abc")
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/api/memshell/generate"))
        self.assertEqual(kwargs["json"]["shellConfig"]["shellTool"], "Behinder")
        self.assertEqual(kwargs["json"]["shellToolConfig"]["behinderPass"], "example-pass")
        client.close()
```

同时将现有 HTTP/body error 测试改为设置 `session.request.return_value`。

- [ ] **步骤 2：编写失败测试，验证网络异常包装和异常链**

在测试导入区加入：

```python
from requests.exceptions import ConnectionError as RequestsConnectionError
```

增加：

```python
    def test_transport_error_is_wrapped_and_preserves_cause(self):
        session = mock.Mock()
        cause = RequestsConnectionError(OSError(101, "example-sensitive-detail"))
        session.request.side_effect = cause
        client = MemShellParty(base_url="https://example.test", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        self.assertIs(ctx.exception.__cause__, cause)
        self.assertIsNone(ctx.exception.status_code)
        self.assertIsNone(ctx.exception.body)
        self.assertIn("GET https://example.test/api/config", str(ctx.exception))
        self.assertIn("ConnectionError", str(ctx.exception))
        self.assertIn("[Errno 101]", str(ctx.exception))
        self.assertNotIn("example-sensitive-detail", str(ctx.exception))
```

- [ ] **步骤 3：编写失败测试，验证 URL 凭证和请求凭证不泄露**

```python
    def test_transport_error_redacts_credentials_and_request_body(self):
        session = mock.Mock()
        session.request.side_effect = RequestsConnectionError(
            "proxy https://proxy-user:proxy-pass@proxy.example unavailable"
        )
        client = MemShellParty(
            base_url="https://api-user:api-pass@example.test",
            session=session,
        )

        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate(
                shell_tool="Behinder",
                behinder_pass="example-pass",
                shell_class_base64="example-class-data",
            )

        message = str(ctx.exception)
        self.assertIn("POST https://example.test/api/memshell/generate", message)
        self.assertIn("ConnectionError: transport error", message)
        for secret in (
            "api-user",
            "api-pass",
            "proxy-user",
            "proxy-pass",
            "example-pass",
            "example-class-data",
        ):
            self.assertNotIn(secret, message)

    def test_transport_error_handles_malformed_base_url(self):
        session = mock.Mock()
        cause = RequestsConnectionError("example-sensitive-detail")
        session.request.side_effect = cause
        client = MemShellParty(base_url="https://[example-invalid", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        self.assertIs(ctx.exception.__cause__, cause)
        self.assertIn("GET /api/config", str(ctx.exception))
        self.assertNotIn("example-invalid", str(ctx.exception))
        self.assertNotIn("example-sensitive-detail", str(ctx.exception))

    def test_transport_error_redacts_base_url_path(self):
        session = mock.Mock()
        session.request.side_effect = RequestsConnectionError("example-sensitive-detail")
        client = MemShellParty(
            base_url="https://example.test/example-path-secret",
            session=session,
        )

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        message = str(ctx.exception)
        self.assertIn("GET https://example.test/api/config", message)
        self.assertNotIn("example-path-secret", message)
        self.assertNotIn("example-sensitive-detail", message)
```

- [ ] **步骤 4：运行测试确认失败**

运行：

```bash
python -m unittest tests.test_memshell.TestMemShellPartyClient -v
```

预期：FAIL，原因是尚无 `_request()`、异常仍直接抛出、URL 未脱敏。

- [ ] **步骤 5：实现安全 URL 和异常摘要辅助函数**

在导入区加入：

```python
from urllib.parse import urlsplit

from requests.exceptions import RequestException
```

在 `MemShellParty` 类之前加入：

```python
_SAFE_REQUEST_PATHS = frozenset(
    {
        "/api/config",
        "/api/config/packers/tree",
        "/api/config/command/configs",
        "/api/memshell/generate",
    }
)


def _safe_request_url(base_url: str, path: str) -> str:
    safe_path = path if path in _SAFE_REQUEST_PATHS else "/<redacted>"
    try:
        parsed = urlsplit(base_url)
        scheme = parsed.scheme.casefold()
        host = parsed.hostname
        if scheme not in {"http", "https"} or not host:
            return safe_path
        if ":" in host:
            host = f"[{host}]"
        try:
            port = f":{parsed.port}" if parsed.port is not None else ""
        except ValueError:
            port = ""
        return f"{scheme}://{host}{port}{safe_path}"
    except (TypeError, ValueError):
        return safe_path


def _safe_transport_error(exc: RequestException) -> str:
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, OSError):
            error_number = current.errno
            if isinstance(error_number, int) and not isinstance(error_number, bool):
                return f"[Errno {error_number}]"
        for attribute in ("reason", "original_error", "__cause__", "__context__"):
            nested = getattr(current, attribute, None)
            if isinstance(nested, BaseException):
                pending.append(nested)
        for argument in getattr(current, "args", ()):
            if isinstance(argument, BaseException):
                pending.append(argument)
    return "transport error"
```

只输出异常类型和可信的操作系统 errno；不拼接任意异常文本，避免代理 URL、认证信息或查询参数进入 CLI 日志。

- [ ] **步骤 6：实现统一 `_request()` 并迁移四个 API 方法**

在 `_url()` 后加入：

```python
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            return self.req.request(method, url, timeout=self.timeout, **kwargs)
        except RequestException as exc:
            retry_note = ""
            if self._owns_session:
                retry_note = f" with up to {self.connect_retries} connection retries"
            message = (
                f"{method.upper()} {_safe_request_url(self.base_url, path)} "
                f"request failed{retry_note}: "
                f"{type(exc).__name__}: {_safe_transport_error(exc)}"
            )
            raise MemShellPartyError(message) from exc
```

四个 API 方法改为：

```python
resp = self._request("GET", "/api/config")
resp = self._request("GET", "/api/config/packers/tree")
resp = self._request("GET", "/api/config/command/configs")
resp = self._request(
    "POST",
    "/api/memshell/generate",
    json=req_body,
    headers={"Content-Type": "application/json", "Accept": "*/*"},
)
```

不要把 `req_body` 传入错误字符串或日志。

- [ ] **步骤 7：运行客户端测试验证通过**

运行：

```bash
python -m unittest tests.test_memshell.TestMemShellPartyClient -v
```

预期：全部 PASS。

- [ ] **步骤 8：Commit 检查点**

用户已明确授权提交时运行：

```bash
git add -- wtfutil/memshellutil.py tests/test_memshell.py
git commit -m "fix: 统一 MemShellParty 网络异常并脱敏"
```

否则记录建议提交信息，不执行 commit。

### 任务 4：补齐 CLI、双语文档和 Agent 模块说明

**文件：**
- 修改：`tests/test_memshell.py:337-525`
- 修改：`docs/zh/memshellutil.md:63-78`
- 修改：`docs/zh/memshellutil.md:288-309`
- 修改：`docs/en/memshellutil.md:63-78`
- 修改：`docs/en/memshellutil.md:288-309`
- 修改：`AGENTS.md:99-105`

- [ ] **步骤 1：增加 CLI 网络错误测试**

在 `TestMemshellCli` 增加：

```python
    def test_cli_reports_wrapped_transport_error_without_traceback(self):
        error_output = io.StringIO()
        with mock.patch("wtfutil.memshell.MemShellParty") as client_class:
            client_class.return_value.get_config.side_effect = MemShellPartyError(
                "GET https://example.test/api/config request failed: ConnectionError"
            )
            with mock.patch("sys.stderr", error_output):
                code = memshell_main(["config"])

        self.assertEqual(code, 1)
        self.assertIn("request failed", error_output.getvalue())
        self.assertNotIn("Traceback", error_output.getvalue())
```

- [ ] **步骤 2：运行 CLI 测试验证现有处理契约**

运行：

```bash
python -m unittest tests.test_memshell.TestMemshellCli.test_cli_reports_wrapped_transport_error_without_traceback -v
```

预期：PASS；CLI 已捕获 `MemShellPartyError`，该测试固定回归契约。

- [ ] **步骤 3：更新中文构造参数和错误处理文档**

在构造参数表加入：

```markdown
| `connect_retries` | `2` | 仅重试连接阶段失败；`0` 表示关闭 |
| `retry_backoff` | `0.25` | 连接重试退避因子，必须是有限的非负数 |
```

在错误处理章节将“网络层异常可能直接抛出”改为：

```markdown
网络层 `requests` 异常统一包装为 `MemShellPartyError`，原异常保存在 `e.__cause__`。内部 session 默认只对连接阶段失败重试 2 次；不重试读取超时、HTTP 状态错误或响应解析错误。外部传入的 session 保留调用方自己的重试策略。
```

- [ ] **步骤 4：同步英文文档**

加入对应参数：

```markdown
| `connect_retries` | `2` | Retry connection-establishment failures only; `0` disables retries |
| `retry_backoff` | `0.25` | Connection retry backoff factor; must be finite and non-negative |
```

错误说明使用：

```markdown
Transport-level `requests` exceptions are wrapped in `MemShellPartyError`, with the original exception available as `e.__cause__`. Internally owned sessions retry connection-establishment failures twice by default. Read timeouts, HTTP status failures, and response parsing failures are not retried. Externally supplied sessions keep the caller's retry policy.
```

- [ ] **步骤 5：更新 AGENTS.md 模块简介**

在 MemShellParty 条目补充：

```markdown
- 内部 session 默认仅对连接阶段失败重试 2 次；网络异常统一包装为 `MemShellPartyError`，不得在错误信息中输出请求体、凭证或生成载荷；外部 session 的重试策略不被修改。
```

- [ ] **步骤 6：运行相关测试和格式检查**

运行：

```bash
python -m unittest tests.test_memshell -v
git diff --check -- AGENTS.md docs/zh/memshellutil.md docs/en/memshellutil.md
```

预期：memshell 测试全部通过，4 个 live 测试按默认配置跳过；`git diff --check` 退出码 `0`。

- [ ] **步骤 7：Commit 检查点**

用户已明确授权提交时运行：

```bash
git add -- AGENTS.md docs/zh/memshellutil.md docs/en/memshellutil.md tests/test_memshell.py
git commit -m "docs: 补充 MemShellParty 重试与安全说明"
```

否则记录建议提交信息，不执行 commit。

### 任务 5：完成回归验证和敏感信息审计

**文件：**
- 验证：`wtfutil/memshellutil.py`
- 验证：`tests/test_memshell.py`
- 验证：`docs/zh/memshellutil.md`
- 验证：`docs/en/memshellutil.md`
- 验证：`AGENTS.md`

- [ ] **步骤 1：运行目标测试**

运行：

```bash
python -m unittest tests.test_memshell -v
```

预期：所有非 live 测试通过，live 测试按环境变量配置跳过。

- [ ] **步骤 2：运行完整测试套件**

运行：

```bash
python -m unittest discover -v
```

预期：至少保持基线 `165` 项通过；新增测试也通过；4 个 live 测试跳过；0 failures、0 errors。

- [ ] **步骤 3：运行静态检查**

运行：

```bash
python -m ruff check wtfutil/memshellutil.py tests/test_memshell.py
```

预期：退出码 `0`。若环境未安装 ruff，明确记录“未运行：ruff 不可用”，不得声称静态检查通过。

- [ ] **步骤 4：检查格式和工作区范围**

运行：

```bash
git diff --check
git status --short
git diff --stat
```

预期：`git diff --check` 退出码 `0`；改动只涉及计划列出的文件。

- [ ] **步骤 5：审计差异中的敏感信息**

运行：

```bash
git diff -- AGENTS.md wtfutil/memshellutil.py tests/test_memshell.py docs/zh/memshellutil.md docs/en/memshellutil.md
```

人工确认：

- 没有真实密码、Token、Cookie、Authorization、私钥或代理凭证。
- 没有 `packResult`、`allPackResults` 或可使用的生成载荷值。
- 测试只使用 `example-pass`、`example-key`、`example-class-data` 等明显虚构值。
- 异常消息从未拼接请求 JSON、headers 或响应载荷。

- [ ] **步骤 6：可选 live 验证**

仅在网络可用且明确接受外部调用时运行：

```bash
MEMSHELL_RUN_LIVE=1 python -m unittest tests.test_memshell.TestMemShellPartyLive.test_live_get_config -v
```

预期：PASS。该步骤不生成载荷，不运行 live generate 测试。

- [ ] **步骤 7：最终 Commit 检查点**

用户已明确授权提交且仍有未提交改动时，按实际差异选择中文提交信息并只暂存计划文件。未获授权时保留改动供用户审查。
