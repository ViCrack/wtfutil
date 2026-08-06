#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memshell - MemShellParty 内存马生成 CLI（AI / 脚本友好）

用法示例：
    memshell config
    memshell packers
    memshell generate -o payload.txt
    memshell generate --help
    memshell install-skill --project
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from importlib import resources
from pathlib import Path

from .memshellutil import (
    MemShellParty,
    MemShellPartyError,
    extract_generate_meta,
)

try:
    from requests.exceptions import RequestException
except ImportError:  # pragma: no cover
    RequestException = OSError  # type: ignore[misc, assignment]

_GENERATE_EPILOG = """
常用参数（server / shell-tool / shell-type 在已知名称内不区分大小写）：

  --server / --shell-tool / --shell-type   中间件、工具、挂载类型（默认 Tomcat / Behinder / Listener）
  --jre                                   目标 Java 发行版本：6/8/9/11/17/21（默认 6；JDK9+ 用 ≥9）
  --password / --key                      通用密码；哥斯拉再加 --key
  --header-name / --header-value          入口特征请求头（默认名 User-Agent）
  --packer / --url-pattern                打包格式与挂载路径
  -o/--output                             仅写 packResult；stdout 打印 meta JSON

其它（可选）：
  --by-pass-java-module / --no-by-pass-java-module / --no-shrink / --no-static-initialize
  --server-version / --debug / --probe / --lambda-suffix
  --shell-class-name / --injector-class-name
  --command-param-name / --command-template / --encryptor / --implementation-class
  --shell-class-base64 / --body / --body-only / --base-url

示例：
  memshell generate -o payload.txt
  memshell generate --password mypass --header-value secret -o out.txt
  memshell generate --shell-tool godzilla --password p --key k -o out.txt
  memshell generate --server tomcat --shell-type filter --jre 9 -o out.txt
  memshell generate --help
"""


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _client_from_args(args: argparse.Namespace) -> MemShellParty:
    return MemShellParty(base_url=getattr(args, "base_url", None), timeout=getattr(args, "timeout", 60))


def _cmd_config(args: argparse.Namespace) -> int:
    """打印 GET /api/config。"""
    client = _client_from_args(args)
    try:
        _print_json(client.get_config())
    finally:
        client.close()
    return 0


def _cmd_packers(args: argparse.Namespace) -> int:
    """打印 GET /api/config/packers/tree。"""
    client = _client_from_args(args)
    try:
        _print_json(client.get_packers_tree())
    finally:
        client.close()
    return 0


def _cmd_command_configs(args: argparse.Namespace) -> int:
    """打印 GET /api/config/command/configs。"""
    client = _client_from_args(args)
    try:
        _print_json(client.get_command_configs())
    finally:
        client.close()
    return 0


def _load_body_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("--body must be a JSON object")
    return data


def _cmd_generate(args: argparse.Namespace) -> int:
    """调用 generate；-o 时只写 packResult，stdout 输出 meta。"""
    if args.body_only and not args.body:
        raise ValueError("--body-only requires --body FILE")

    body_override = _load_body_file(args.body) if args.body else None

    kwargs = {
        "server": args.server,
        "server_version": args.server_version,
        "shell_tool": args.shell_tool,
        "shell_type": args.shell_type,
        "debug": args.debug,
        "by_pass_java_module": args.by_pass_java_module,
        "shrink": not args.no_shrink,
        "probe": args.probe,
        "lambda_suffix": args.lambda_suffix,
        "packer": args.packer,
        "url_pattern": args.url_pattern,
        "static_initialize": not args.no_static_initialize,
        "shell_class_name": args.shell_class_name,
        "password": args.password,
        "key": args.key,
        "godzilla_pass": args.godzilla_pass,
        "godzilla_key": args.godzilla_key,
        "behinder_pass": args.behinder_pass,
        "ant_sword_pass": args.ant_sword_pass,
        "command_param_name": args.command_param_name,
        "command_template": args.command_template,
        "encryptor": args.encryptor,
        "implementation_class": args.implementation_class,
        "header_name": args.header_name,
        "header_value": args.header_value,
        "shell_class_base64": args.shell_class_base64,
        "injector_class_name": args.injector_class_name,
    }
    if getattr(args, "jre", None) is not None:
        kwargs["jre"] = args.jre
    elif getattr(args, "target_jre_version", None) is not None:
        kwargs["target_jre_version"] = args.target_jre_version

    if body_override is not None and args.body_only:
        gen_kwargs: dict = {}
    else:
        gen_kwargs = kwargs

    client = _client_from_args(args)
    try:
        result = client.generate(body_override, **gen_kwargs)

        if args.output:
            pack = result.get("packResult")
            all_packs = result.get("allPackResults")
            if pack:
                Path(args.output).write_text(str(pack), encoding="utf-8")
            elif all_packs:
                Path(args.output).write_text(
                    json.dumps(all_packs, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                raise MemShellPartyError("response has no packResult / allPackResults")
            meta = extract_generate_meta(result, output=str(Path(args.output).resolve()))
            _print_json(meta)
        else:
            _print_json(result)
    finally:
        client.close()
    return 0


def _install_skill_files(dest: Path) -> None:
    """从源码树或 importlib.resources 拷贝 skill 文件到 dest（仅 SKILL.md 等文档）。"""
    dest.mkdir(parents=True, exist_ok=True)
    skip_names = {"__init__.py", "__pycache__"}
    local = Path(__file__).resolve().parent / "skills" / "memshell"
    if (local / "SKILL.md").exists():
        for item in local.iterdir():
            if item.name in skip_names or item.name.startswith("."):
                continue
            target = dest / item.name
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(
                    item,
                    target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
                )
            else:
                shutil.copy2(item, target)
        return

    pkg = resources.files("wtfutil.skills.memshell")
    skill_md = pkg.joinpath("SKILL.md")
    if not skill_md.is_file():
        raise FileNotFoundError("bundled skill not found: wtfutil/skills/memshell/SKILL.md")
    (dest / "SKILL.md").write_text(skill_md.read_text(encoding="utf-8"), encoding="utf-8")


def _cmd_install_skill(args: argparse.Namespace) -> int:
    """安装 Agent Skill 到 ~/.agents/skills 或 ./.agents/skills。"""
    if not args.global_ and not args.project:
        print("error: specify --global and/or --project", file=sys.stderr)
        return 2

    installed: list[str] = []

    if args.global_:
        dest = Path.home() / ".agents" / "skills" / "memshell"
        _install_skill_files(dest)
        installed.append(str(dest.resolve()))

    if args.project:
        dest = Path.cwd() / ".agents" / "skills" / "memshell"
        _install_skill_files(dest)
        installed.append(str(dest.resolve()))

    _print_json({"installed": installed})
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=None,
        help="MemShellParty 服务根地址（默认 https://party.mem.mk，或 MEMSHELL_BASE_URL）",
    )
    parser.add_argument("--timeout", type=float, default=60, help="HTTP 超时秒数（默认 60）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="memshell",
        description="MemShellParty CLI：通过 HTTP API 生成 Java 内存马。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  memshell config\n"
            "  memshell generate -o payload.txt\n"
            "  memshell generate --help          # 查看全部参数说明\n"
            "  memshell install-skill --project\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_config = sub.add_parser("config", help="查询可用 server/shellTool/shellType 组合（GET /api/config）")
    _add_common(p_config)
    p_config.set_defaults(func=_cmd_config)

    p_packers = sub.add_parser("packers", help="查询 packer 树（GET /api/config/packers/tree）")
    _add_common(p_packers)
    p_packers.set_defaults(func=_cmd_packers)

    p_cmd = sub.add_parser(
        "command-configs",
        help="查询 Command 马 encryptor/implementationClass（GET /api/config/command/configs）",
    )
    _add_common(p_cmd)
    p_cmd.set_defaults(func=_cmd_command_configs)

    p_gen = sub.add_parser(
        "generate",
        help="生成内存马（POST /api/memshell/generate）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_GENERATE_EPILOG,
    )
    _add_common(p_gen)
    p_gen.add_argument(
        "-o",
        "--output",
        help="只把最终 packResult 写入该文件；stdout 输出连接信息 meta JSON（推荐）",
    )
    p_gen.add_argument("--body", help="官方 JSON 请求体文件；与下方 flag 深度合并（body 覆盖同名键）")
    p_gen.add_argument(
        "--body-only",
        action="store_true",
        help="忽略下方 CLI flag，仅用 --body 覆盖库默认值（必须同时给 --body）",
    )
    p_gen.add_argument(
        "--server",
        default="Tomcat",
        help="目标中间件/框架（不区分大小写）：Tomcat、Jetty、SpringWebMvc…（默认 Tomcat）",
    )
    p_gen.add_argument(
        "--server-version",
        default="unknown",
        help="服务版本；少数挂载类型因包名差异才需要指定（默认 unknown）",
    )
    p_gen.add_argument(
        "--shell-tool",
        default="Behinder",
        help="内存马工具（不区分大小写）：Behinder/Godzilla/Command/AntSword…（默认 Behinder）",
    )
    p_gen.add_argument(
        "--shell-type",
        default="Listener",
        help="挂载类型（不区分大小写）：Listener/Filter/Valve…（须与 server+tool 匹配，默认 Listener）",
    )
    p_gen.add_argument(
        "--jre",
        default=None,
        help="目标 Java/JRE 发行版本：6/8/9/11/17/21（推荐；默认 6）",
    )
    p_gen.add_argument(
        "--target-jre-version",
        default=None,
        help=argparse.SUPPRESS,
    )
    p_gen.add_argument(
        "--debug",
        action="store_true",
        help="开启调试：注入器打印注入信息，Shell 打印异常堆栈",
    )
    p_gen.add_argument(
        "--by-pass-java-module",
        dest="by_pass_java_module",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="绕过 JDK9+ 模块限制（Unsafe defineClass）；未指定时 JRE≥9 自动 True",
    )
    p_gen.add_argument(
        "--no-shrink",
        action="store_true",
        help="关闭缩小字节码（默认开启：ASM SKIP_DEBUG 去掉调试信息以缩短体积）",
    )
    p_gen.add_argument(
        "--probe",
        action="store_true",
        help="回显探测模式：把注入器放入回显马，便于非本地确认是否注入成功",
    )
    p_gen.add_argument(
        "--lambda-suffix",
        action="store_true",
        help="类名追加 $Proxy0$$Lambda$1 后缀，便于绕过部分主动扫描",
    )
    p_gen.add_argument(
        "--packer",
        default="DefaultBase64",
        help="打包格式（DefaultBase64、GzipBase64、ClassLoaderJSP、SpELScriptEngine、AgentJar…）",
    )
    p_gen.add_argument(
        "--url-pattern",
        default="/*",
        help="注入后匹配的 URL 路径（默认 /*；Servlet/Controller/WebSocket 等常需具体路径）",
    )
    p_gen.add_argument(
        "--no-static-initialize",
        action="store_true",
        help="关闭静态初始化（默认开启：静态块调构造，适配 Class.forName(..., true, ...)）",
    )
    p_gen.add_argument("--shell-class-name", default="", help="Shell 全限定类名（空则服务端随机）")
    p_gen.add_argument(
        "--password",
        dest="password",
        default="",
        help="通用连接密码：按 --shell-tool 自动映射到冰蝎/哥斯拉/蚁剑对应 *Pass",
    )
    p_gen.add_argument(
        "--key",
        default="",
        help="哥斯拉密钥 godzillaKey（建议与 Godzilla + --password 一起用）",
    )
    p_gen.add_argument("--godzilla-pass", default="", help=argparse.SUPPRESS)
    p_gen.add_argument("--godzilla-key", default="", help=argparse.SUPPRESS)
    p_gen.add_argument("--behinder-pass", default="", help=argparse.SUPPRESS)
    p_gen.add_argument("--ant-sword-pass", default="", help=argparse.SUPPRESS)
    p_gen.add_argument(
        "--command-param-name",
        default="",
        help="Command 马：接收命令的请求参数名或请求头名",
    )
    p_gen.add_argument(
        "--command-template",
        default="",
        help='Command 马：命令模板，用 {command} 占位，如 sh -c "{command}" 2>&1',
    )
    p_gen.add_argument(
        "--encryptor",
        default="",
        help="Command 马：命令参数加密 RAW|BASE64|DOUBLE_BASE64（默认 RAW）",
    )
    p_gen.add_argument(
        "--implementation-class",
        default="",
        help="Command 马：执行实现 RuntimeExec|ForkAndExec（默认 RuntimeExec）",
    )
    p_gen.add_argument(
        "--header-name",
        default="User-Agent",
        help="入口特征请求头名称（匹配后才进入内存马逻辑，默认 User-Agent）",
    )
    p_gen.add_argument(
        "--header-value",
        default="",
        help="入口特征请求头值（空则服务端随机；请求头需 contains 该值）",
    )
    p_gen.add_argument(
        "--shell-class-base64",
        default="",
        help="Custom 模式：自定义内存马 .class 的 Base64",
    )
    p_gen.add_argument(
        "--injector-class-name",
        default="",
        help="注入器全限定类名（空则服务端随机）",
    )
    p_gen.set_defaults(func=_cmd_generate)

    p_skill = sub.add_parser("install-skill", help="安装 Agent Skill 到 .agents/skills/memshell")
    p_skill.add_argument("--global", dest="global_", action="store_true", help="安装到 ~/.agents/skills/memshell")
    p_skill.add_argument("--project", action="store_true", help="安装到当前项目 ./.agents/skills/memshell")
    p_skill.set_defaults(func=_cmd_install_skill)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MemShellPartyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except RequestException as exc:
        print(f"error: request failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
