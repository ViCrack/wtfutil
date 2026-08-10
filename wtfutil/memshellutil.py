"""
MemShellParty HTTP API 客户端：生成内存马 / 查询配置。

默认服务：https://party.mem.mk（可通过构造参数、环境变量或 wtfconfig.ini [memshell] 覆盖）。
本模块不做结果缓存；频繁调用时请由调用方自行缓存。
"""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlsplit

from requests import Session
from requests.exceptions import RequestException
from urllib3.util import Retry

from .configutil import ensure_section
from .httputil import requests_session

DEFAULT_BASE_URL = "https://party.mem.mk"

_MEMSHELL_DEFAULTS = {
    "BASE_URL": DEFAULT_BASE_URL,
}

memshell_config = dict(_MEMSHELL_DEFAULTS)

# 请求体默认值：字段名对齐 MemShellGenerateRequest / ShellConfig / InjectorConfig / ShellToolConfigDTO
# shellTool 默认 Behinder（冰蝎）；其余与官方 UI 常用默认一致
_DEFAULT_SHELL_CONFIG = {
    "server": "Tomcat",
    "serverVersion": "unknown",
    "shellTool": "Behinder",
    "shellType": "Listener",
    "targetJreVersion": 50,
    "debug": False,
    "byPassJavaModule": False,
    "shrink": True,
    "probe": False,
    "lambdaSuffix": False,
}

_DEFAULT_INJECTOR_CONFIG = {
    "urlPattern": "/*",
    "injectorClassName": "",
    "staticInitialize": True,
}

# 对齐 MemShellGenerateRequest.ShellToolConfigDTO
_DEFAULT_SHELL_TOOL_CONFIG = {
    "shellClassName": "",
    "godzillaPass": "",
    "godzillaKey": "",
    "commandParamName": "",
    "commandTemplate": "",
    "behinderPass": "",
    "antSwordPass": "",
    "headerName": "User-Agent",
    "headerValue": "",
    "shellClassBase64": "",
    "encryptor": "",
    "implementationClass": "",
}

_DEFAULT_PACKER = "DefaultBase64"

# Java/JRE 发行版本 → 字节码 class 主版本（官方 API 的 targetJreVersion）
JRE_RELEASE_TO_CLASS = {
    6: 50,
    7: 51,
    8: 52,
    9: 53,
    10: 54,
    11: 55,
    12: 56,
    13: 57,
    14: 58,
    15: 59,
    16: 60,
    17: 61,
    18: 62,
    19: 63,
    20: 64,
    21: 65,
    22: 66,
}

# 官方常见写法（来自 party.mem.mk /api/config）；用于忽略大小写归一。
# 可能滞后于上游；未命中则原样上传，可用 get_config() / memshell config 核对。
KNOWN_SERVERS = (
    "Apusic",
    "BES",
    "Dubbo",
    "GlassFish",
    "InforSuite",
    "JBoss",
    "Jetty",
    "Jetty5",
    "Resin",
    "Resin2",
    "SpringWebFlux",
    "SpringWebMvc",
    "Struts2",
    "Tomcat",
    "TongWeb",
    "Undertow",
    "WebLogic",
    "WebSphere",
    "XXLJOB",
)

KNOWN_SHELL_TOOLS = (
    "AntSword",
    "Behinder",
    "Command",
    "Custom",
    "Godzilla",
    "NeoreGeorg",
    "Proxy",
    "Suo5",
    "Suo5v2",
)

KNOWN_SHELL_TYPES = (
    "Action",
    "AgentContextValve",
    "AgentFilterChain",
    "AgentFilterManager",
    "AgentFrameworkServlet",
    "AgentHandler",
    "AgentServletContext",
    "AgentServletHandler",
    "AlibabaDubboService",
    "ApacheDubboService",
    "BypassNginxWebSocket",
    "ControllerHandler",
    "Customizer",
    "Filter",
    "Handler",
    "HandlerFunction",
    "HandlerMethod",
    "Interceptor",
    "JakartaControllerHandler",
    "JakartaFilter",
    "JakartaHandler",
    "JakartaInterceptor",
    "JakartaListener",
    "JakartaProxyValve",
    "JakartaServlet",
    "JakartaValve",
    "JakartaWebBypassNginxWebSocket",
    "JakartaWebSocket",
    "Listener",
    "NettyHandler",
    "ProxyValve",
    "Servlet",
    "Upgrade",
    "Valve",
    "WebFilter",
    "WebSocket",
)


def _casefold_lookup(names: tuple[str, ...]) -> dict[str, str]:
    return {n.casefold(): n for n in names}


_SERVER_LOOKUP = _casefold_lookup(KNOWN_SERVERS)
_SHELL_TOOL_LOOKUP = _casefold_lookup(KNOWN_SHELL_TOOLS)
_SHELL_TYPE_LOOKUP = _casefold_lookup(KNOWN_SHELL_TYPES)


class MemShellPartyError(Exception):
    """MemShellParty API 调用失败。"""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)


def resolve_jre_class_version(value: int | str) -> int:
    """
    将「JRE 发行版本」或「class 主版本」统一为官方 API 所需的 class 主版本。

    - ``6`` / ``8`` / ``9`` / ``11`` / ``17`` / ``21`` / ``22`` 等 → 映射为 50/52/53/…
    - 已是 class 主版本（如 ``50``、``61``）则原样返回
    """
    try:
        v = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid jre / target_jre_version: {value!r}") from exc
    if v in JRE_RELEASE_TO_CLASS:
        return JRE_RELEASE_TO_CLASS[v]
    if 1 <= v < 45:
        return v + 44
    return v


def canonicalize_server(value: str) -> str:
    """将 server 归一为官方大小写；未知名称原样返回。"""
    if value is None or value == "":
        return value
    return _SERVER_LOOKUP.get(str(value).casefold(), value)


def canonicalize_shell_tool(value: str) -> str:
    """将 shell_tool 归一为官方大小写；未知名称原样返回。"""
    if value is None or value == "":
        return value
    return _SHELL_TOOL_LOOKUP.get(str(value).casefold(), value)


def canonicalize_shell_type(value: str) -> str:
    """将 shell_type 归一为官方大小写；未知名称原样返回。"""
    if value is None or value == "":
        return value
    return _SHELL_TYPE_LOOKUP.get(str(value).casefold(), value)


def _canonicalize_shell_config(shell_config: dict) -> None:
    """就地归一 shellConfig 中的 server / shellTool / shellType。"""
    if shell_config.get("server"):
        shell_config["server"] = canonicalize_server(shell_config["server"])
    if shell_config.get("shellTool"):
        shell_config["shellTool"] = canonicalize_shell_tool(shell_config["shellTool"])
    if shell_config.get("shellType"):
        shell_config["shellType"] = canonicalize_shell_type(shell_config["shellType"])


def _load_memshell_config(*, force_reload: bool = False) -> None:
    """延迟加载 [memshell] 与环境变量 MEMSHELL_BASE_URL（支持 ini 热更新）。"""
    ensure_section(
        memshell_config,
        _MEMSHELL_DEFAULTS,
        "memshell",
        uppercase_keys=True,
        env_map={"BASE_URL": "MEMSHELL_BASE_URL"},
        force_reload=force_reload,
    )


def _deep_merge(base: dict, override: dict | None) -> dict:
    """深度合并字典；override 覆盖同名键。"""
    result = dict(base)
    if not override:
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_shell_credentials(
    shell_tool: str,
    *,
    password: str = "",
    key: str = "",
    godzilla_pass: str = "",
    godzilla_key: str = "",
    behinder_pass: str = "",
    ant_sword_pass: str = "",
) -> dict[str, str]:
    """
    将通用 password/key 按 shellTool 映射到官方 shellToolConfig 字段。

    ``shell_tool`` 在已知集合内不区分大小写。
    专用参数（behinder_pass / godzilla_pass 等）优先于通用 ``password`` / ``key``。
    - Behinder → behinderPass
    - Godzilla → godzillaPass；key → godzillaKey
    - AntSword → antSwordPass
    其它工具：通用 password 不写入；key 仅在显式传入时写入 godzillaKey（一般无意义）。
    """
    tool = canonicalize_shell_tool((shell_tool or "").strip())
    gp = godzilla_pass or ""
    gk = godzilla_key or ""
    bp = behinder_pass or ""
    ap = ant_sword_pass or ""

    if password:
        if tool == "Behinder" and not bp:
            bp = password
        elif tool == "Godzilla" and not gp:
            gp = password
        elif tool == "AntSword" and not ap:
            ap = password

    if key and not gk:
        gk = key

    return {
        "godzilla_pass": gp,
        "godzilla_key": gk,
        "behinder_pass": bp,
        "ant_sword_pass": ap,
    }


def build_generate_body(
    body: dict | None = None,
    *,
    server: str = "Tomcat",
    server_version: str = "unknown",
    shell_tool: str = "Behinder",
    shell_type: str = "Listener",
    jre: int | str | None = None,
    target_jre_version: int | str | None = None,
    debug: bool = False,
    by_pass_java_module: bool | None = None,
    shrink: bool = True,
    probe: bool = False,
    lambda_suffix: bool = False,
    packer: str = _DEFAULT_PACKER,
    url_pattern: str = "/*",
    static_initialize: bool = True,
    shell_class_name: str = "",
    password: str = "",
    key: str = "",
    godzilla_pass: str = "",
    godzilla_key: str = "",
    behinder_pass: str = "",
    ant_sword_pass: str = "",
    command_param_name: str = "",
    command_template: str = "",
    encryptor: str = "",
    implementation_class: str = "",
    header_name: str = "User-Agent",
    header_value: str = "",
    shell_class_base64: str = "",
    injector_class_name: str = "",
) -> dict:
    """
    组装官方 POST /api/memshell/generate 请求体（camelCase 字段）。

    kwargs 对应官方 JSON：serverVersion、shellTool、targetJreVersion、behinderPass 等。
    ``server`` / ``shell_tool`` / ``shell_type`` 在已知集合内**不区分大小写**
    （如 ``tomcat`` → ``Tomcat``）；未知名称原样上传。
    目标字节码版本请优先传 ``jre``（Java 发行版：6/8/9/11/17/21/22）；
    ``target_jre_version`` 仍可用（发行版或 class 主版本均可，见 :func:`resolve_jre_class_version`）。
    二者同时传入时以 ``jre`` 为准。默认 JRE 6。
    也可传通用 ``password`` / ``key``，按**最终** shellTool 自动映射（见 :func:`resolve_shell_credentials`）；
    若 ``body`` 覆盖了 shellTool，会在合并后再按新工具映射，避免密码写到错误字段。
    若同时传入 ``body``，则在 kwargs 组装结果上深度合并覆盖。
    ``body`` 内的 ``targetJreVersion`` 按官方语义原样使用（不会再做发行版换算）；发行版请用 kwargs ``jre``。
    ``by_pass_java_module`` 为 None 时：解析后的 class 版本对应 Java 9+（≥53）自动 True。
    shellTool=Command 且未指定时，encryptor 默认 RAW，implementationClass 默认 RuntimeExec。
    """
    server = canonicalize_server(server)
    shell_tool = canonicalize_shell_tool(shell_tool)
    shell_type = canonicalize_shell_type(shell_type)

    if jre is not None:
        class_ver = resolve_jre_class_version(jre)
    elif target_jre_version is not None:
        class_ver = resolve_jre_class_version(target_jre_version)
    else:
        class_ver = JRE_RELEASE_TO_CLASS[6]

    if by_pass_java_module is None:
        by_pass_java_module = class_ver >= JRE_RELEASE_TO_CLASS[9]

    # 专用凭证先写入；通用 password/key 等 merge + 最终 shellTool 确定后再映射
    if body is not None and not isinstance(body, dict):
        raise TypeError("body must be a dictionary or None")

    built = {
        "shellConfig": {
            **_DEFAULT_SHELL_CONFIG,
            "server": server,
            "serverVersion": server_version,
            "shellTool": shell_tool,
            "shellType": shell_type,
            "targetJreVersion": class_ver,
            "debug": debug,
            "byPassJavaModule": by_pass_java_module,
            "shrink": shrink,
            "probe": probe,
            "lambdaSuffix": lambda_suffix,
        },
        "shellToolConfig": {
            **_DEFAULT_SHELL_TOOL_CONFIG,
            "shellClassName": shell_class_name,
            "godzillaPass": godzilla_pass or "",
            "godzillaKey": godzilla_key or "",
            "commandParamName": command_param_name,
            "commandTemplate": command_template,
            "behinderPass": behinder_pass or "",
            "antSwordPass": ant_sword_pass or "",
            "headerName": header_name,
            "headerValue": header_value,
            "shellClassBase64": shell_class_base64,
            "encryptor": encryptor,
            "implementationClass": implementation_class,
        },
        "injectorConfig": {
            **_DEFAULT_INJECTOR_CONFIG,
            "urlPattern": url_pattern,
            "injectorClassName": injector_class_name,
            "staticInitialize": static_initialize,
        },
        "packer": packer,
    }
    if body:
        built = _deep_merge(built, body)

    sc = built.get("shellConfig")
    if not isinstance(sc, dict):
        raise TypeError("body.shellConfig must be an object")
    _canonicalize_shell_config(sc)

    stc = built.get("shellToolConfig")
    if not isinstance(stc, dict):
        raise TypeError("body.shellToolConfig must be an object")
    injector_config = built.get("injectorConfig")
    if not isinstance(injector_config, dict):
        raise TypeError("body.injectorConfig must be an object")

    final_tool = sc.get("shellTool") or shell_tool
    creds = resolve_shell_credentials(
        final_tool,
        password=password,
        key=key,
        godzilla_pass=stc.get("godzillaPass") or "",
        godzilla_key=stc.get("godzillaKey") or "",
        behinder_pass=stc.get("behinderPass") or "",
        ant_sword_pass=stc.get("antSwordPass") or "",
    )
    stc["godzillaPass"] = creds["godzilla_pass"]
    stc["godzillaKey"] = creds["godzilla_key"]
    stc["behinderPass"] = creds["behinder_pass"]
    stc["antSwordPass"] = creds["ant_sword_pass"]

    if final_tool == "Command":
        if not stc.get("encryptor"):
            stc["encryptor"] = "RAW"
        if not stc.get("implementationClass"):
            stc["implementationClass"] = "RuntimeExec"

    return built


def extract_generate_meta(result: dict, *, output: str | None = None) -> dict:
    """
    从 generate 响应提取紧凑元信息（类名、连接参数、尺寸等），不含大段 packResult。

    供 CLI ``-o`` 模式向 stdout 打印，便于 AI/脚本解析。
    """
    if not isinstance(result, dict):
        raise TypeError("result must be a dictionary")
    mem = result.get("memShellResult", {})
    if not isinstance(mem, dict):
        raise TypeError("result.memShellResult must be an object")
    injector_cfg = mem.get("injectorConfig", {})
    if not isinstance(injector_cfg, dict):
        raise TypeError("result.memShellResult.injectorConfig must be an object")
    meta: dict[str, Any] = {
        "shellClassName": mem.get("shellClassName"),
        "injectorClassName": mem.get("injectorClassName"),
        "shellSize": mem.get("shellSize"),
        "injectorSize": mem.get("injectorSize"),
        "shellConfig": mem.get("shellConfig"),
        "shellToolConfig": mem.get("shellToolConfig"),
        "injectorConfig": {
            k: v
            for k, v in injector_cfg.items()
            if k
            not in (
                "shellClassBytes",
                "helperClassBytes",
                "shellClassBase64",
                "injectorClassBytes",
            )
            and not (isinstance(k, str) and k.endswith("Bytes"))
        },
        "hasPackResult": bool(result.get("packResult")),
        "hasAllPackResults": bool(result.get("allPackResults")),
    }
    if output is not None:
        meta["output"] = output
    return meta


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


class MemShellParty:
    """
    MemShellParty HTTP 客户端。

    不做内置缓存；CLI 每次进程独立，脚本侧如需复用相同配置的结果请自行缓存。
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 60,
        session: Session | None = None,
        connect_retries: int = 2,
        retry_backoff: float = 0.25,
    ) -> None:
        """
        :param base_url: 服务根地址，默认 https://party.mem.mk
        :param timeout: 请求超时（秒）
        :param session: 可选复用的 requests session；未传则内部创建并在 close 时关闭
        :param connect_retries: 内部 session 的连接失败重试次数；0 表示禁用
        :param retry_backoff: 内部 session 的有限非负连接重试退避因子
        """
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

    def close(self) -> None:
        """关闭内部创建的 session（外部传入的 session 不关闭）。"""
        if self._owns_session:
            self.req.close()

    # Keep the concrete type to avoid a typing_extensions runtime dependency on Python 3.10.
    def __enter__(self) -> MemShellParty:  # noqa: PYI034
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

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

    def _parse_response(self, resp: Any) -> Any:
        """解析 JSON；错误仅公开固定类别和 HTTP 状态码。"""
        try:
            data = resp.json()
        except Exception as exc:
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {resp.status_code})",
                status_code=resp.status_code,
            ) from exc

        if resp.status_code >= 400:
            raise MemShellPartyError(
                f"HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        if isinstance(data, dict) and data.get("error"):
            raise MemShellPartyError(
                f"API response reported an error (HTTP {resp.status_code})",
                status_code=resp.status_code,
            )
        return data

    def get_config(self) -> dict:
        """
        GET /api/config

        返回 ``{ server: { shellTool: [shellType, ...] } }``，用于选择合法组合。
        """
        resp = self._request("GET", "/api/config")
        return self._parse_response(resp)

    def get_packers_tree(self) -> list:
        """
        GET /api/config/packers/tree

        返回 ``[{ name, children }, ...]`` packer 树；叶子或父名可作为 ``packer``。
        """
        resp = self._request("GET", "/api/config/packers/tree")
        return self._parse_response(resp)

    def get_command_configs(self) -> dict:
        """
        GET /api/config/command/configs

        返回 Command 工具可用的 ``encryptors`` / ``implementationClasses``。
        """
        resp = self._request("GET", "/api/config/command/configs")
        return self._parse_response(resp)

    def generate(self, body: dict | None = None, **kwargs: Any) -> dict:
        """
        POST /api/memshell/generate — 生成内存马并打包。

        参数与 :func:`build_generate_body` 相同（snake_case → 官方 camelCase）。
        可传完整 ``body``；与 kwargs 同时存在时 body 深度覆盖。
        返回含 ``packResult`` / ``memShellResult`` 的完整响应；不做缓存。
        """
        req_body = build_generate_body(body, **kwargs)
        resp = self._request(
            "POST",
            "/api/memshell/generate",
            json=req_body,
            headers={"Content-Type": "application/json", "Accept": "*/*"},
        )
        return self._parse_response(resp)


__all__ = [
    "DEFAULT_BASE_URL",
    "JRE_RELEASE_TO_CLASS",
    "KNOWN_SERVERS",
    "KNOWN_SHELL_TOOLS",
    "KNOWN_SHELL_TYPES",
    "MemShellParty",
    "MemShellPartyError",
    "build_generate_body",
    "canonicalize_server",
    "canonicalize_shell_tool",
    "canonicalize_shell_type",
    "extract_generate_meta",
    "memshell_config",
    "resolve_jre_class_version",
    "resolve_shell_credentials",
]
