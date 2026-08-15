"""
MemShellParty HTTP API 客户端：生成内存马 / 探测马 / 查询配置。

默认服务：https://party.mem.mk（可通过构造参数、环境变量或 wtfconfig.ini [memshell] 覆盖）。
本模块不做结果缓存；频繁调用时请由调用方自行缓存。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from requests import Response, Session
from requests.exceptions import RequestException
from urllib3.util import Retry

from .configutil import ensure_section
from .httputil import EnhancedResponse, requests_session

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

KNOWN_PROBE_METHODS = (
    "ResponseBody",
    "DNSLog",
    "Sleep",
)
KNOWN_PROBE_CONTENTS = (
    "Server",
    "JDK",
    "Command",
    "Bytecode",
    "ScriptEngine",
    "Filter",
    "BasicInfo",
    "OS",
)


def _enum_member_name(value: str) -> str:
    split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", split)
    return split.upper()


def _str_enum(name: str, values: tuple[str, ...]) -> type[Enum]:
    return Enum(name, {_enum_member_name(item): item for item in values}, type=str)


Server = _str_enum("Server", KNOWN_SERVERS)
ShellTool = _str_enum("ShellTool", KNOWN_SHELL_TOOLS)
ShellType = _str_enum("ShellType", KNOWN_SHELL_TYPES)
ProbeMethod = _str_enum("ProbeMethod", KNOWN_PROBE_METHODS)
ProbeContent = _str_enum("ProbeContent", KNOWN_PROBE_CONTENTS)


def _casefold_lookup(names: tuple[str, ...]) -> dict[str, str]:
    return {n.casefold(): n for n in names}


_SERVER_LOOKUP = _casefold_lookup(KNOWN_SERVERS)
_SHELL_TOOL_LOOKUP = _casefold_lookup(KNOWN_SHELL_TOOLS)
_SHELL_TYPE_LOOKUP = _casefold_lookup(KNOWN_SHELL_TYPES)
_PROBE_METHOD_LOOKUP = _casefold_lookup(KNOWN_PROBE_METHODS)
_PROBE_CONTENT_LOOKUP = _casefold_lookup(KNOWN_PROBE_CONTENTS)


def _build_connect_retry(connect_retries: int, retry_backoff: float) -> Retry:
    """Build a connection-only retry policy across supported urllib3 versions."""
    retry_arguments = {
        "total": connect_retries,
        "connect": connect_retries,
        "read": 0,
        "status": 0,
        "redirect": 0,
        "backoff_factor": retry_backoff,
    }
    retry_methods = frozenset({"GET", "POST"})

    try:
        return Retry(
            **retry_arguments,
            other=0,
            allowed_methods=retry_methods,
        )
    except TypeError:
        # urllib3 1.25 calls this option method_whitelist and has no ``other``.
        return Retry(
            **retry_arguments,
            method_whitelist=retry_methods,
        )


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
        version_value = int(value)
    except (TypeError, ValueError):
        invalid_version = True
    else:
        invalid_version = False
    if invalid_version:
        raise ValueError("invalid jre / target_jre_version")
    if version_value in JRE_RELEASE_TO_CLASS:
        return JRE_RELEASE_TO_CLASS[version_value]
    if 1 <= version_value < 45:
        return version_value + 44
    return version_value


def canonicalize_server(value: str | Server) -> str:
    """将 server 归一为官方大小写；未知名称原样返回。"""
    if isinstance(value, Enum):
        value = value.value
    if value is None or value == "":
        return value
    return _SERVER_LOOKUP.get(str(value).casefold(), value)


def canonicalize_shell_tool(value: str | ShellTool) -> str:
    """将 shell_tool 归一为官方大小写；未知名称原样返回。"""
    if isinstance(value, Enum):
        value = value.value
    if value is None or value == "":
        return value
    return _SHELL_TOOL_LOOKUP.get(str(value).casefold(), value)


def canonicalize_shell_type(value: str | ShellType) -> str:
    """将 shell_type 归一为官方大小写；未知名称原样返回。"""
    if isinstance(value, Enum):
        value = value.value
    if value is None or value == "":
        return value
    return _SHELL_TYPE_LOOKUP.get(str(value).casefold(), value)


def canonicalize_probe_method(value: str | ProbeMethod) -> str:
    """将探测方法归一为官方大小写；未知名称 strip 后原样返回。"""
    if isinstance(value, Enum):
        value = value.value
    text = ("" if value is None else str(value)).strip()
    return _PROBE_METHOD_LOOKUP.get(text.casefold(), text)


def canonicalize_probe_content(value: str | ProbeContent) -> str:
    """将探测内容归一为官方大小写；未知名称 strip 后原样返回。"""
    if isinstance(value, Enum):
        value = value.value
    text = ("" if value is None else str(value)).strip()
    return _PROBE_CONTENT_LOOKUP.get(text.casefold(), text)


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
    server: str | Server = "Tomcat",
    server_version: str = "unknown",
    shell_tool: str | ShellTool = "Behinder",
    shell_type: str | ShellType = "Listener",
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


_PAYLOAD_FIELD_NAMES = frozenset(
    {
        "packResult",
        "allPackResults",
        "shellBytesBase64Str",
        "shellClassBytes",
        "helperClassBytes",
        "shellClassBase64",
        "injectorClassBytes",
    }
)


def _is_payload_field(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    if key in _PAYLOAD_FIELD_NAMES:
        return True
    return key.endswith(("Bytes", "Base64", "Base64Str"))


def _redact_payload_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _redact_payload_fields(v)
            for k, v in value.items()
            if not _is_payload_field(k)
        }
    if isinstance(value, list):
        return [_redact_payload_fields(item) for item in value]
    return value


def _as_config_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return _redact_payload_fields(value)
    return {}


@dataclass
class MemShellGenerateResult:
    """``generate`` 的结构化结果；属性为 snake_case，避免猜 JSON 字段名。"""

    pack_result: Any = None
    all_pack_results: Any = None
    shell_class_name: Any = None
    injector_class_name: Any = None
    shell_size: Any = None
    injector_size: Any = None
    shell_config: dict[str, Any] = field(default_factory=dict)
    shell_tool_config: dict[str, Any] = field(default_factory=dict)
    injector_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packResult": self.pack_result,
            "allPackResults": self.all_pack_results,
            "memShellResult": {
                "shellClassName": self.shell_class_name,
                "injectorClassName": self.injector_class_name,
                "shellSize": self.shell_size,
                "injectorSize": self.injector_size,
                "shellConfig": self.shell_config,
                "shellToolConfig": self.shell_tool_config,
                "injectorConfig": self.injector_config,
            },
        }


def extract_generate_meta(
    result: dict | MemShellGenerateResult, *, output: str | None = None
) -> dict:
    """
    从 generate 响应提取紧凑元信息（类名、连接参数、尺寸等），不含大段 packResult。

    配置对象会递归去掉载荷类字段。供 CLI ``-o`` 模式向 stdout 打印。
    """
    if isinstance(result, MemShellGenerateResult):
        return extract_generate_meta(result.to_dict(), output=output)
    if not isinstance(result, dict):
        raise TypeError("result must be a dictionary or MemShellGenerateResult")
    mem = result.get("memShellResult", {})
    if not isinstance(mem, dict):
        raise TypeError("result.memShellResult must be an object")
    injector_cfg = mem.get("injectorConfig", {})
    if not isinstance(injector_cfg, dict):
        raise TypeError("result.memShellResult.injectorConfig must be an object")
    meta = {
        "shellClassName": mem.get("shellClassName"),
        "injectorClassName": mem.get("injectorClassName"),
        "shellSize": mem.get("shellSize"),
        "injectorSize": mem.get("injectorSize"),
        "shellConfig": _as_config_dict(mem.get("shellConfig")),
        "shellToolConfig": _as_config_dict(mem.get("shellToolConfig")),
        "injectorConfig": _redact_payload_fields(injector_cfg),
        "hasPackResult": bool(result.get("packResult")),
        "hasAllPackResults": bool(result.get("allPackResults")),
    }
    if output is not None:
        meta["output"] = output
    return meta


def build_probe_body(
    body: dict | None = None,
    *,
    method: str | ProbeMethod = "ResponseBody",
    content: str | ProbeContent = "Command",
    packer: str = "DefaultBase64",
    jre: int | str | None = None,
    target_jre_version: int | str | None = None,
    debug: bool = False,
    by_pass_java_module: bool | None = None,
    shrink: bool = True,
    lambda_suffix: bool = False,
    static_initialize: bool = True,
    shell_class_name: str = "",
    host: str = "",
    seconds: int | None = 5,
    sleep_server: str | Server = "Tomcat",
    server: str | Server = "Tomcat",
    req_param_name: str = "",
    command_template: str = "",
) -> dict:
    """
    组装官方 POST /api/probe/generate 请求体（camelCase 字段）。

    ``method`` / ``content`` / ``server`` / ``sleep_server`` 可传枚举或字符串；
    已知集合内**不区分大小写**（如 ``dnslog`` → ``DNSLog``，``tomcat`` → ``Tomcat``）；
    未知名称 strip 后原样上传。
    不校验 method 与 content 的前端合法组合，非法组合由服务端返回 HTTP 错误。
    目标字节码版本请优先传 ``jre``（Java 发行版：6/8/9/11/17/21/22）；
    ``target_jre_version`` 仍可用（发行版或 class 主版本均可，见 :func:`resolve_jre_class_version`）。
    二者同时传入时以 ``jre`` 为准。默认 JRE 6。
    若同时传入 ``body``，则在 kwargs 组装结果上深度合并覆盖。
    ``body`` 内的 ``targetJreVersion`` 按官方语义原样使用（不会再做发行版换算）；发行版请用 kwargs ``jre``。
    ``by_pass_java_module`` 为 None 时：解析后的 class 版本对应 Java 9+（≥53）自动 True。
    ``probeContentConfig`` 只放入有值的字段：空字符串与 ``seconds is None`` 省略。
    """
    if body is not None and not isinstance(body, dict):
        raise TypeError("body must be a dictionary or None")
    if jre is not None:
        class_ver = resolve_jre_class_version(jre)
    elif target_jre_version is not None:
        class_ver = resolve_jre_class_version(target_jre_version)
    else:
        class_ver = JRE_RELEASE_TO_CLASS[6]
    if by_pass_java_module is None:
        by_pass_java_module = class_ver >= JRE_RELEASE_TO_CLASS[9]
    if seconds is not None:
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            raise TypeError("seconds must be an integer or None")
    content_cfg: dict[str, Any] = {}
    for key, value in (
        ("host", host),
        ("sleepServer", sleep_server),
        ("server", server),
        ("reqParamName", req_param_name),
        ("commandTemplate", command_template),
    ):
        if value:
            content_cfg[key] = value
    if seconds is not None:
        content_cfg["seconds"] = seconds
    built = {
        "probeConfig": {
            "probeMethod": canonicalize_probe_method(method),
            "probeContent": canonicalize_probe_content(content),
            "shellClassName": shell_class_name,
            "targetJreVersion": class_ver,
            "debug": debug,
            "byPassJavaModule": by_pass_java_module,
            "shrink": shrink,
            "staticInitialize": static_initialize,
            "lambdaSuffix": lambda_suffix,
        },
        "probeContentConfig": content_cfg,
        "packer": packer,
    }
    if body:
        built = _deep_merge(built, body)
    pc = built.get("probeConfig")
    if not isinstance(pc, dict):
        raise TypeError("body.probeConfig must be an object")
    pcc = built.get("probeContentConfig")
    if not isinstance(pcc, dict):
        raise TypeError("body.probeContentConfig must be an object")
    if "probeMethod" in pc:
        pc["probeMethod"] = canonicalize_probe_method(pc["probeMethod"])
    if "probeContent" in pc:
        pc["probeContent"] = canonicalize_probe_content(pc["probeContent"])
    if pcc.get("server"):
        pcc["server"] = canonicalize_server(pcc["server"])
    if pcc.get("sleepServer"):
        pcc["sleepServer"] = canonicalize_server(pcc["sleepServer"])
    built["probeContentConfig"] = {
        k: v for k, v in pcc.items() if v not in ("", None)
    }
    return built


_PROBE_CONFIG_KEYS = (
    "probeMethod",
    "probeContent",
    "shellClassName",
    "targetJreVersion",
    "debug",
    "byPassJavaModule",
    "shrink",
    "staticInitialize",
    "lambdaSuffix",
)
_PROBE_CONTENT_CONFIG_KEYS = (
    "host",
    "seconds",
    "sleepServer",
    "server",
    "reqParamName",
    "commandTemplate",
)


@dataclass
class ProbeGenerateResult:
    """``generate_probe`` 的结构化结果；属性为 snake_case，避免猜 JSON 字段名。"""

    pack_result: Any = None
    all_pack_results: Any = None
    shell_class_name: Any = None
    shell_size: Any = None
    probe_config: dict[str, Any] = field(default_factory=dict)
    probe_content_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packResult": self.pack_result,
            "allPackResults": self.all_pack_results,
            "probeShellResult": {
                "shellClassName": self.shell_class_name,
                "shellSize": self.shell_size,
                "probeConfig": self.probe_config,
                "probeContentConfig": self.probe_content_config,
            },
        }


def extract_probe_meta(
    result: dict | ProbeGenerateResult, *, output: str | None = None
) -> dict:
    """
    从 generate_probe 响应提取紧凑元信息（类名、尺寸、探测配置），不含 packResult。

    ``probeConfig`` / ``probeContentConfig`` 只保留字段白名单，并递归去掉载荷类字段。
    供 CLI ``-o`` 模式向 stdout 打印，便于 AI/脚本解析。
    """
    if isinstance(result, ProbeGenerateResult):
        return extract_probe_meta(result.to_dict(), output=output)
    if not isinstance(result, dict):
        raise TypeError("result must be a dictionary or ProbeGenerateResult")
    probe = result.get("probeShellResult", {})
    if not isinstance(probe, dict):
        raise TypeError("result.probeShellResult must be an object")
    probe_cfg = probe.get("probeConfig", {})
    if not isinstance(probe_cfg, dict):
        raise TypeError("result.probeShellResult.probeConfig must be an object")
    content_cfg = probe.get("probeContentConfig", {})
    if not isinstance(content_cfg, dict):
        raise TypeError("result.probeShellResult.probeContentConfig must be an object")
    meta = {
        "shellClassName": probe.get("shellClassName"),
        "shellSize": probe.get("shellSize"),
        "probeConfig": _redact_payload_fields(
            {k: probe_cfg[k] for k in _PROBE_CONFIG_KEYS if k in probe_cfg}
        ),
        "probeContentConfig": _redact_payload_fields(
            {k: content_cfg[k] for k in _PROBE_CONTENT_CONFIG_KEYS if k in content_cfg}
        ),
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
        "/api/probe/generate",
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
        except (TypeError, ValueError):
            invalid_retry_backoff = True
        else:
            invalid_retry_backoff = False
        if invalid_retry_backoff:
            raise TypeError("retry_backoff must be a finite non-negative number")
        if retry_backoff_value < 0 or not math.isfinite(retry_backoff_value):
            raise ValueError("retry_backoff must be a finite non-negative number")

        _load_memshell_config()
        self.base_url = (base_url or memshell_config.get("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.connect_retries = connect_retries
        self.retry_backoff = retry_backoff_value
        self._owns_session = session is None
        if session is None:
            retry = _build_connect_retry(connect_retries, retry_backoff_value)
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
            request_error_message = (
                f"{method.upper()} {_safe_request_url(self.base_url, path)} "
                f"request failed{retry_note}: "
                f"{type(exc).__name__}: {_safe_transport_error(exc)}"
            )
        raise MemShellPartyError(request_error_message)

    def _parse_response(self, resp: Any) -> Any:
        """解析 JSON。API 的 ``error`` 字符串会带进异常；不附带响应体或载荷。"""
        try:
            if isinstance(resp, EnhancedResponse):
                data = Response.json(resp)
            else:
                data = resp.json()
        except Exception:
            response_status_code = resp.status_code
            response_is_invalid_json = True
        else:
            response_status_code = resp.status_code
            response_is_invalid_json = False

        if response_is_invalid_json:
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {response_status_code})",
                status_code=response_status_code,
            ) from None

        error_text = ""
        if isinstance(data, dict):
            raw_error = data.get("error")
            if isinstance(raw_error, str):
                error_text = raw_error.strip()
                if len(error_text) > 500:
                    error_text = error_text[:500] + "..."
        if error_text:
            raise MemShellPartyError(
                f"{error_text} (HTTP {response_status_code})",
                status_code=response_status_code,
            )
        if response_status_code >= 400:
            raise MemShellPartyError(
                f"HTTP {response_status_code}",
                status_code=response_status_code,
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

    def generate(self, body: dict | None = None, **kwargs: Any) -> MemShellGenerateResult:
        """
        POST /api/memshell/generate — 生成内存马并打包。

        参数与 :func:`build_generate_body` 相同（snake_case → 官方 camelCase）。
        ``server`` / ``shell_tool`` / ``shell_type`` 可传枚举或字符串（已知名称不区分大小写）。
        可传完整 ``body``；与 kwargs 同时存在时 body 深度覆盖。
        返回 :class:`MemShellGenerateResult`；不做缓存。
        """
        req_body = build_generate_body(body, **kwargs)
        resp = self._request(
            "POST",
            "/api/memshell/generate",
            json=req_body,
            headers={"Content-Type": "application/json", "Accept": "*/*"},
        )
        data = self._parse_response(resp)
        if not isinstance(data, dict):
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {resp.status_code})",
                status_code=resp.status_code,
            )
        try:
            meta = extract_generate_meta(data)
        except TypeError:
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {resp.status_code})",
                status_code=resp.status_code,
            ) from None
        return MemShellGenerateResult(
            pack_result=data.get("packResult"),
            all_pack_results=data.get("allPackResults"),
            shell_class_name=meta["shellClassName"],
            injector_class_name=meta["injectorClassName"],
            shell_size=meta["shellSize"],
            injector_size=meta["injectorSize"],
            shell_config=meta["shellConfig"],
            shell_tool_config=meta["shellToolConfig"],
            injector_config=meta["injectorConfig"],
        )

    def generate_probe(self, body: dict | None = None, **kwargs: Any) -> ProbeGenerateResult:
        """
        POST /api/probe/generate — 生成探测马并打包。

        与 ``generate(probe=True)`` 不是同一件事：后者只是内存马生成里的回显探测开关，
        本方法走独立的探测马接口。
        参数与 :func:`build_probe_body` 相同（snake_case → 官方 camelCase）。
        ``method`` / ``content`` / ``server`` / ``sleep_server`` 可传枚举或字符串（已知名称不区分大小写）。
        可传完整 ``body``；与 kwargs 同时存在时 body 深度覆盖。
        返回 :class:`ProbeGenerateResult`；不做缓存。
        """
        req_body = build_probe_body(body, **kwargs)
        resp = self._request(
            "POST",
            "/api/probe/generate",
            json=req_body,
            headers={"Content-Type": "application/json", "Accept": "*/*"},
        )
        data = self._parse_response(resp)
        if not isinstance(data, dict):
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {resp.status_code})",
                status_code=resp.status_code,
            )
        try:
            meta = extract_probe_meta(data)
        except TypeError:
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {resp.status_code})",
                status_code=resp.status_code,
            ) from None
        return ProbeGenerateResult(
            pack_result=data.get("packResult"),
            all_pack_results=data.get("allPackResults"),
            shell_class_name=meta["shellClassName"],
            shell_size=meta["shellSize"],
            probe_config=meta["probeConfig"],
            probe_content_config=meta["probeContentConfig"],
        )


__all__ = [
    "DEFAULT_BASE_URL",
    "JRE_RELEASE_TO_CLASS",
    "KNOWN_SERVERS",
    "KNOWN_SHELL_TOOLS",
    "KNOWN_SHELL_TYPES",
    "MemShellGenerateResult",
    "MemShellParty",
    "MemShellPartyError",
    "ProbeContent",
    "ProbeGenerateResult",
    "ProbeMethod",
    "Server",
    "ShellTool",
    "ShellType",
    "build_generate_body",
    "build_probe_body",
    "canonicalize_server",
    "canonicalize_shell_tool",
    "canonicalize_shell_type",
    "extract_generate_meta",
    "extract_probe_meta",
    "memshell_config",
    "resolve_jre_class_version",
    "resolve_shell_credentials",
]
