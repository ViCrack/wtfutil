"""
MemShellParty HTTP API 客户端：生成内存马 / 查询配置。

默认服务：https://party.mem.mk（可通过构造参数、环境变量或 wtfconfig.ini [memshell] 覆盖）。
本模块不做结果缓存；频繁调用时请由调用方自行缓存。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from configobj import ConfigObj

from ._base import get_resource
from .httputil import RequestsSession, requests_session

DEFAULT_BASE_URL = "https://party.mem.mk"

memshell_config = {
    "BASE_URL": DEFAULT_BASE_URL,
}

_config_loaded = False

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


class MemShellPartyError(Exception):
    """MemShellParty API 调用失败。"""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)


def _load_memshell_config() -> None:
    """延迟加载 [memshell] 与环境变量 MEMSHELL_BASE_URL。"""
    global _config_loaded
    if _config_loaded:
        return

    config_path = get_resource("wtfconfig.ini")
    if config_path and Path(config_path).exists():
        cfg = ConfigObj(config_path, encoding="UTF-8")
        if "memshell" in cfg:
            for key, value in cfg["memshell"].items():
                memshell_config[key.upper()] = str(value)

    if os.getenv("MEMSHELL_BASE_URL"):
        memshell_config["BASE_URL"] = os.getenv("MEMSHELL_BASE_URL")

    _config_loaded = True


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

    专用参数（behinder_pass / godzilla_pass 等）优先于通用 ``password`` / ``key``。
    - Behinder → behinderPass
    - Godzilla → godzillaPass；key → godzillaKey
    - AntSword → antSwordPass
    其它工具：通用 password 不写入；key 仅在显式传入时写入 godzillaKey（一般无意义）。
    """
    tool = (shell_tool or "").strip()
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
    target_jre_version: int | str = 50,
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
    也可传通用 ``password`` / ``key``，按 shellTool 自动映射（见 :func:`resolve_shell_credentials`）。
    若同时传入 ``body``，则在 kwargs 组装结果上深度合并覆盖。
    ``by_pass_java_module`` 为 None 时：targetJreVersion >= 53 自动 True。
    shellTool=Command 且未指定时，encryptor 默认 RAW，implementationClass 默认 RuntimeExec。
    """
    jre = int(target_jre_version)
    if by_pass_java_module is None:
        by_pass_java_module = jre >= 53

    creds = resolve_shell_credentials(
        shell_tool,
        password=password,
        key=key,
        godzilla_pass=godzilla_pass,
        godzilla_key=godzilla_key,
        behinder_pass=behinder_pass,
        ant_sword_pass=ant_sword_pass,
    )
    godzilla_pass = creds["godzilla_pass"]
    godzilla_key = creds["godzilla_key"]
    behinder_pass = creds["behinder_pass"]
    ant_sword_pass = creds["ant_sword_pass"]

    # Command 工具显式带上服务端同款默认，避免空串语义依赖后端 fromString 回退
    if shell_tool == "Command":
        if not encryptor:
            encryptor = "RAW"
        if not implementation_class:
            implementation_class = "RuntimeExec"

    built = {
        "shellConfig": {
            **_DEFAULT_SHELL_CONFIG,
            "server": server,
            "serverVersion": server_version,
            "shellTool": shell_tool,
            "shellType": shell_type,
            "targetJreVersion": jre,
            "debug": debug,
            "byPassJavaModule": by_pass_java_module,
            "shrink": shrink,
            "probe": probe,
            "lambdaSuffix": lambda_suffix,
        },
        "shellToolConfig": {
            **_DEFAULT_SHELL_TOOL_CONFIG,
            "shellClassName": shell_class_name,
            "godzillaPass": godzilla_pass,
            "godzillaKey": godzilla_key,
            "commandParamName": command_param_name,
            "commandTemplate": command_template,
            "behinderPass": behinder_pass,
            "antSwordPass": ant_sword_pass,
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

    # body 覆盖后若变为 Command，同样补默认；若 body 改了 shellTool，再按最终 tool 用已写入字段即可
    if built.get("shellConfig", {}).get("shellTool") == "Command":
        stc = built.setdefault("shellToolConfig", {})
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
    mem = result.get("memShellResult") or {}
    injector_cfg = mem.get("injectorConfig") or {}
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


class MemShellParty:
    """
    MemShellParty HTTP 客户端。

    不做内置缓存；CLI 每次进程独立，脚本侧如需复用相同配置的结果请自行缓存。
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 60,
        session: RequestsSession | None = None,
    ) -> None:
        """
        :param base_url: 服务根地址，默认 https://party.mem.mk
        :param timeout: 请求超时（秒）
        :param session: 可选复用的 requests session；未传则内部创建并在 close 时关闭
        """
        _load_memshell_config()
        self.base_url = (base_url or memshell_config.get("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._owns_session = session is None
        self.req = session or requests_session(timeout=timeout)

    def close(self) -> None:
        """关闭内部创建的 session（外部传入的 session 不关闭）。"""
        if self._owns_session:
            self.req.close()

    def __enter__(self) -> MemShellParty:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _parse_response(self, resp: Any) -> Any:
        """解析 JSON；HTTP 错误或 body.error 时抛 MemShellPartyError。"""
        try:
            data = resp.json()
        except Exception as exc:
            raise MemShellPartyError(
                f"invalid JSON response (HTTP {resp.status_code}): {resp.text[:200]}",
                status_code=resp.status_code,
                body=resp.text,
            ) from exc

        if resp.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else None
            raise MemShellPartyError(
                err or f"HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=data,
            )
        if isinstance(data, dict) and data.get("error"):
            raise MemShellPartyError(str(data["error"]), status_code=resp.status_code, body=data)
        return data

    def get_config(self) -> dict:
        """
        GET /api/config

        返回 ``{ server: { shellTool: [shellType, ...] } }``，用于选择合法组合。
        """
        resp = self.req.get(self._url("/api/config"), timeout=self.timeout)
        return self._parse_response(resp)

    def get_packers_tree(self) -> list:
        """
        GET /api/config/packers/tree

        返回 ``[{ name, children }, ...]`` packer 树；叶子或父名可作为 ``packer``。
        """
        resp = self.req.get(self._url("/api/config/packers/tree"), timeout=self.timeout)
        return self._parse_response(resp)

    def get_command_configs(self) -> dict:
        """
        GET /api/config/command/configs

        返回 Command 工具可用的 ``encryptors`` / ``implementationClasses``。
        """
        resp = self.req.get(self._url("/api/config/command/configs"), timeout=self.timeout)
        return self._parse_response(resp)

    def generate(self, body: dict | None = None, **kwargs: Any) -> dict:
        """
        POST /api/memshell/generate — 生成内存马并打包。

        参数与 :func:`build_generate_body` 相同（snake_case → 官方 camelCase）。
        可传完整 ``body``；与 kwargs 同时存在时 body 深度覆盖。
        返回含 ``packResult`` / ``memShellResult`` 的完整响应；不做缓存。
        """
        req_body = build_generate_body(body, **kwargs)
        resp = self.req.post(
            self._url("/api/memshell/generate"),
            json=req_body,
            headers={"Content-Type": "application/json", "Accept": "*/*"},
            timeout=self.timeout,
        )
        return self._parse_response(resp)


__all__ = [
    "DEFAULT_BASE_URL",
    "MemShellParty",
    "MemShellPartyError",
    "build_generate_body",
    "extract_generate_meta",
    "memshell_config",
    "resolve_shell_credentials",
]
