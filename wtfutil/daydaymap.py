"""Flat DayDayMap CLI. stdout is data; stderr is progress and sanitized errors."""
from __future__ import annotations

import argparse
import ctypes
import errno
import io
import json
import math
import os
import queue
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import ExitStack
from itertools import chain
from pathlib import Path

from .fileutil import read_lines
from .daydaymaputil import (
    DayDayMapClient, DayDayMapError, _fields, find_key_file, load_keys,
    query_from_certificate, query_from_icon,
)

__all__ = ['main']


def _int_range(minimum, maximum=None):
    def parse(text):
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError('必须为整数。') from None
        if value < minimum or (maximum is not None and value > maximum):
            raise argparse.ArgumentTypeError('数值超出允许范围。')
        return value
    return parse


def _float_range(allow_zero=False):
    def parse(text):
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError('必须为有限数值。') from None
        if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
            raise argparse.ArgumentTypeError('数值超出允许范围。')
        return value
    return parse


def _field_list(text):
    try:
        return _fields(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


_EPILOG = """常见查询语法示例（查询值需用英文双引号，不区分大小写）：
  IP 与网络:
    ip="1.1.1.1"                   单一 IPv4/IPv6 地址
    ip="1.1.1.0/24"                CIDR 网段（或范围 "1.1.1.0-1.1.1.255"）
    port="80" 或 ip.port="80"      端口（支持 >、>=、<、<= 比较）
    service="http"                 服务协议（如 http, ssh, mysql）
    is_ipv6="true"                 IPv6 资产（false 为 IPv4）
  Web 与域名:
    domain="example.com"           域名及子域名
    domain.root="example.com"      主域名相关子域名
    title="后台管理"                网页标题包含
    header="Server: Apache"        响应头包含
    body="管理系统"                正文内容包含
    status_code="200"              HTTP 状态码
    icon="MD5" 或 web.icon="MD5"   网站图标 MD5
    is_domain="true"               域名资产（同 CLI --is-domain）
    is_web="true"                  Web 资产
  应用与组件:
    app="Nginx"                    应用名称（如 Tomcat, Spring 等）
    product="OpenSSL"              组件名称
    os="Linux"                     操作系统
  证书与归属:
    cert.subject.cn="example.com"  证书使用者通用名 (CN)
    cert.issuer.cn="Let's Encrypt" 证书颁发者通用名
    icp="京ICP备..."               ICP 备案号包含
    icp.name="企业名称"            ICP 备案单位名称
    org.name="盛邦安全"            资产归属组织/企业名称
    asn="AS15169"                  自治域编号
  地域与标签:
    ip.country="CN"                国家代码或名称（如 CN, 中国）
    ip.province="浙江"             省份
    ip.city="杭州"                 城市
    ip.tag="CDN"                   特色标签（如 CDN, 蜜罐, 云厂商）
  逻辑运算与组合:
    && (与), || (或), != (非), () 分组
    示例: app="Apache" && port="8080"
    示例: (title="登录" || title="admin") && ip.country="CN"
    示例: domain="example.com" && port!="80"

输入与提示:
  无显式输入且 stdin 非终端时自动逐行读取；如需查询字面量 search/count，请使用 -q。"""


def _parser():
    parser = argparse.ArgumentParser(
        prog='daydaymap', description='默认搜索，--count 计数；免费聚合优先，强制排除平台已标记蜜罐、涉黄、涉赌。',
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument('query_pos', nargs='?', metavar='QUERY', help='原始查询语句或模板输入值')
    parser.add_argument('-q', '--query', action='append', default=[], help='查询语句，可重复')
    parser.add_argument('--count', action='store_true', help='只计数：免费聚合优先，失败且有 Key 时可回退 API（可能扣积分）')
    parser.add_argument('--jobs', type=_int_range(1, 10), metavar='N',
                        help='并发计数线程数 1..10（默认 4；仅 --count 模式，输出仍按输入顺序）')
    parser.add_argument('--query-file', action='append', default=[], metavar='FILE', help='UTF-8 文件，一行一条；- 读取 stdin，可重复')
    parser.add_argument('--template', help='如 domain="{}"；{} 必须位于双引号内，输入值自动转义')
    parser.add_argument('--key-file', action='append', default=[], metavar='FILE',
                        help='一行一个 Key，可重复；默认按 get_resource 查找 daydaymap_keys.txt：当前目录、上级 resource/、用户目录')
    parser.add_argument('--no-key-cache', action='store_true',
                        help='禁用当日已耗尽 Key 缓存（默认 ~/.daydaymap_exhausted_keys.json，按天失效）')
    parser.add_argument('-o', '--output', metavar='FILE', help='追加写入 UTF-8 文件，并跳过已有行；默认或 - 为 stdout')
    parser.add_argument('--timeout', type=_float_range(), default=30, help='单请求超时秒数（默认 30）')
    parser.add_argument('--interval', type=_float_range(True), default=0.5, help='请求间隔秒数（默认 0.5）')
    parser.add_argument('--max-retries', type=_int_range(0, 20), default=2, help='连接超时/429/2006 额外重试次数（默认 2）')
    parser.add_argument('--proxy', help='HTTP(S)/SOCKS 代理；SOCKS 需要 wtfutil[socks]')
    parser.add_argument('--quiet', action='store_true', default=None, help='隐藏搜索计数预检和摘要；仅搜索模式有效')
    parser.add_argument('--is-china', action='store_true', help='限中国大陆，排除港澳台（默认不限制地域）')
    parser.add_argument('--is-domain', action='store_true', help='添加 is_domain="true"（默认不限制）')
    icon = parser.add_mutually_exclusive_group()
    icon.add_argument('--icon-file', metavar='FILE', help='本地图标，原始字节 MD5；最大 2 MiB')
    icon.add_argument('--icon-url', metavar='URL', help='HTTP(S) 图标直链，原始字节 MD5；最大 2 MiB')
    parser.add_argument('--cert-url', metavar='URL', help='HTTPS 网站，提取叶子证书 DER MD5；支持自定义端口')
    parser.add_argument('--fields', type=_field_list, help='逗号分隔的返回字段，优先于 exclude-fields')
    parser.add_argument('--exclude-fields', type=_field_list, help='逗号分隔的排除字段')
    parser.add_argument('--page-size', type=_int_range(1, 500),
                        help='分页大小 1..500（默认 100；大于 100 时单次按 100 发送；积分不足时同一 Key 降到 50、10）')
    parser.add_argument('--page', type=_int_range(1),
                        help='只取指定页，不再翻页；--max-effort 时忽略')
    parser.add_argument('-l', '--limit', type=_int_range(0), help='每条输入的输出上限（默认 10000；0 无本地上限）')
    parser.add_argument('--max-effort', action='store_true', default=None,
                        help='超过结果窗口时尝试聚合拆分，不保证完整覆盖；忽略 --page 与 --page-size（起步 100 条，仍受 -l 收缩）')
    parser.add_argument('--max-effort-depth', type=_int_range(1, 1000), help='最多拆分子查询数（默认 10，不是递归深度）')
    parser.add_argument('--format', choices=('jsonl', 'url'), help='搜索输出格式（默认 jsonl）')
    return parser


def _validate_mode(args):
    if args.query_pos in ('count', 'search'):
        raise ValueError('QUERY 不能是单独的 search/count；计数请使用 --count，查询同名字面量请使用 -q。')
    search_only = ('fields', 'exclude_fields', 'page_size', 'page', 'limit', 'max_effort',
                   'max_effort_depth', 'format', 'quiet')
    if args.count:
        invalid = [name for name in search_only if getattr(args, name) is not None]
        if invalid:
            raise ValueError('--count 不能与搜索专用参数同时使用：' + ', '.join(invalid))
        args.jobs = 4 if args.jobs is None else args.jobs
    else:
        if args.jobs is not None:
            raise ValueError('--jobs 仅 --count 计数模式有效。')
        if args.max_effort_depth is not None and not args.max_effort:
            raise ValueError('--max-effort-depth 需要同时启用 --max-effort。')
        args.limit = 10000 if args.limit is None else args.limit
        if args.max_effort:
            # --max-effort 自行控制分页：忽略 --page 与 --page-size。
            args.page = None
            args.page_size = 500
        else:
            args.page_size = 100 if args.page_size is None else args.page_size
            if args.limit and args.page_size > args.limit:
                args.page_size = args.limit
        args.max_effort = bool(args.max_effort)
        args.quiet = bool(args.quiet)
        args.max_effort_depth = 10 if args.max_effort_depth is None else args.max_effort_depth
        args.format = 'jsonl' if args.format is None else args.format


def _validate_template(template):
    if template is None:
        return
    quoted = escaped = False
    placeholders = 0
    index = 0
    while index < len(template):
        char = template[index]
        if char in '{}':
            if char != '{' or template[index:index + 2] != '{}' or not quoted or escaped:
                raise ValueError('模板只允许双引号内的未转义 {} 占位符。')
            placeholders += 1
            index += 2
            continue
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '"':
            quoted = not quoted
        index += 1
    if not placeholders or quoted or escaped:
        raise ValueError('模板必须包含 {} 占位符，且双引号必须闭合。')


def _line_values(stream):
    for index, line in enumerate(stream):
        value = (line.lstrip('\ufeff') if index == 0 else line).strip()
        if value and not value.startswith('#'):
            yield value


def _queries(args, streams):
    seen = set()
    values = ([args.query_pos] if args.query_pos is not None else []) + args.query
    for value in chain(values, *(_line_values(stream) for stream in streams)):
        value = value.strip()
        if args.template is not None:
            value = args.template.replace('{}', value.replace('\\', '\\\\').replace('"', '\\"'))
        if value not in seen:
            seen.add(value)
            yield value


def _key_files(args):
    if args.key_file:
        return args.key_file
    path = os.getenv('DAYDAYMAP_KEY_FILE', '').strip()
    if path:
        return [path]
    if os.getenv('DAYDAYMAP_API_KEY', '').strip():
        return []
    path = find_key_file()
    return [path] if path is not None else []


def _existing_key_files():
    """Return every daydaymap_keys.txt that exists, including empty files."""
    cwd = Path.cwd()
    candidates = [cwd / 'daydaymap_keys.txt']
    current = cwd
    while True:
        candidates.append(current / 'resource' / 'daydaymap_keys.txt')
        parent = current.parent
        if parent == current:
            break
        current = parent
    candidates.append(Path.home() / 'daydaymap_keys.txt')
    found = []
    for path in candidates:
        try:
            if path.is_file():
                resolved = str(path.resolve())
                if resolved not in found:
                    found.append(resolved)
        except OSError:
            continue
    return found


def _keys(paths):
    if paths:
        return list(dict.fromkeys(key for path in paths for key in load_keys(path)))
    value = os.getenv('DAYDAYMAP_API_KEY', '').strip()
    return [value] if value else []


def _protect_inputs(output, inputs):
    if not output or output == '-':
        return
    destination = Path(output).expanduser().resolve()
    for path in inputs:
        source = Path(path).expanduser().resolve()
        if destination == source or (destination.exists() and destination.samefile(source)):
            raise ValueError('输出文件不能覆盖 Key、查询或图标输入文件。')


def _protect_stdin(output, streams):
    if not output or output == '-' or not any(stream is sys.stdin for stream in streams):
        return
    destination = Path(output).expanduser()
    if not destination.exists():
        return
    try:
        source = os.fstat(sys.stdin.fileno())
    except (OSError, ValueError, AttributeError):
        return  # StringIO and other in-memory inputs have no filesystem identity.
    if os.path.samestat(destination.stat(), source):
        raise ValueError('输出文件不能覆盖重定向到 stdin 的输入文件。')


def _json(data, stream):
    print(json.dumps(data, ensure_ascii=False, separators=(',', ':')), file=stream, flush=True)


class _OutputClosed(Exception):
    """Only stdout consumer closure is a successful early stop."""


def _closed_stdout(exc, stream):
    if stream is not sys.stdout:
        return False
    if isinstance(exc, BrokenPipeError):
        return True
    if os.name == 'nt' and exc.errno == errno.EINVAL:
        # The Windows CRT can map ERROR_BROKEN_PIPE to EINVAL. Verify the actual
        # pipe state so other invalid-argument/file errors remain failures.
        import msvcrt
        try:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            write = kernel.WriteFile
            write.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                              ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
            write.restype = ctypes.c_int
            handle = msvcrt.get_osfhandle(stream.fileno())
            written = ctypes.c_ulong()
            # A zero-byte write probes a write-only pipe without sending data.
            return not write(handle, None, 0, ctypes.byref(written), None) and ctypes.get_last_error() in (109, 232, 233)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return False


def _output_line(data, *, url=False):
    if url:
        return _url(data)
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def _emit(data, stream, *, url=False, seen=None, needs_break=None):
    try:
        line = _output_line(data, url=url)
        if seen is not None:
            if line in seen:
                return
            seen.add(line)
        if needs_break is not None and needs_break[0]:
            stream.write('\n')
            needs_break[0] = False
        print(line, file=stream, flush=True)
    except OSError as exc:
        if _closed_stdout(exc, stream):
            raise _OutputClosed from None
        raise


def _silence_closed_stdout():
    # Prevent a second BrokenPipeError when CPython flushes at process shutdown.
    try:
        fd = sys.stdout.fileno()
        if isinstance(fd, int):
            with open(os.devnull, 'w') as sink:
                os.dup2(sink.fileno(), fd)
    except (OSError, ValueError, AttributeError):
        pass


def _url(asset):
    result = asset.get('url')
    if result:
        if not isinstance(result, str) or '\n' in result or '\r' in result:
            raise DayDayMapError('invalid_response')
        return result
    host = str(asset.get('domain') or asset.get('ip') or '')
    if not host or any(c.isspace() for c in host):
        raise DayDayMapError('invalid_response')
    if ':' in host and not host.startswith('['):
        host = f'[{host}]'
    service = str(asset.get('service') or 'http').lower()
    scheme = {'ssl': 'https', 'https-alt': 'https', 'http-alt': 'http', 'http-proxy': 'http'}.get(service, service)
    port = asset.get('port')
    suffix = '' if port is None or port == '' or (scheme, str(port)) in (('http', '80'), ('https', '443')) else f':{port}'
    return f'{scheme}://{host}{suffix}'


def _search_kwargs(args):
    fields = args.fields
    excluded = args.exclude_fields
    if args.format == 'url':
        required = ('url', 'ip', 'domain', 'port', 'service')
        if fields:
            fields = tuple(dict.fromkeys((*fields, *required)))
        elif excluded:
            excluded = tuple(name for name in excluded if name not in required)
    return dict(fields=fields, exclude_fields=excluded, page_size=args.page_size, page=args.page,
                limit=args.limit, max_effort=args.max_effort, max_effort_depth=args.max_effort_depth)


def _count_all(client, queries, filters, jobs, emit):
    """并发计数：工作线程只查询，主线程按输入顺序输出，读取最多提前 jobs 条。"""
    if jobs <= 1:
        for query in queries:
            emit(client.count(query, **filters).to_dict())
        return
    work = queue.Queue(maxsize=jobs * 2)
    done_sentinel = object()

    def reader():
        try:
            for query in queries:
                work.put(query)
        except BaseException as exc:
            work.put(exc)
        else:
            work.put(done_sentinel)

    threading.Thread(target=reader, daemon=True).start()
    pending = {}
    results = {}
    next_index = next_emit = 0
    reading = True
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        while True:
            while reading and len(pending) < jobs:
                try:
                    item = work.get(timeout=0.05)
                except queue.Empty:
                    break
                if item is done_sentinel:
                    reading = False
                elif isinstance(item, BaseException):
                    raise item
                else:
                    pending[executor.submit(client.count, item, **filters)] = next_index
                    next_index += 1
            if not pending:
                if not reading:
                    break
                continue
            finished, _ = wait(tuple(pending), timeout=0.05, return_when=FIRST_COMPLETED)
            for future in finished:
                results[pending.pop(future)] = future.result().to_dict()
            while next_emit in results:
                emit(results.pop(next_emit))
                next_emit += 1


def _exit_code(exc):
    if exc.reason in ('no_keys', 'invalid_query'):
        return 2
    if exc.reason in ('quota_exhausted', 'keys_unavailable'):
        return 3
    if exc.reason in ('incomplete_page', 'result_limit'):
        return 4
    return 1


def main(argv: list[str] | None = None) -> int:
    # Pipes/files use UTF-8 on Windows too; leave terminal encoding to Python.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper) and not stream.isatty():
            stream.reconfigure(encoding='utf-8')
    args = _parser().parse_args(argv)
    try:
        _validate_mode(args)
        _validate_template(args.template)
        values = ([args.query_pos] if args.query_pos is not None else []) + args.query
        if any(not value.strip() for value in values):
            raise ValueError('查询语句不能为空。')
        key_files = _key_files(args)
        keys = _keys(key_files)
        if not keys and (not args.count or key_files):
            raise DayDayMapError('no_keys')
        inputs = [path for path in args.query_file if path != '-'] + key_files
        if args.icon_file is not None:
            inputs.append(args.icon_file)
        _protect_inputs(args.output, inputs)
        with ExitStack() as stack:
            # Open every named input before appending output, but never read it all.
            streams = [sys.stdin if path == '-' else stack.enter_context(
                Path(path).expanduser().open(encoding='utf-8-sig')) for path in dict.fromkeys(args.query_file)]
            has_source = any(value is not None for value in (args.icon_file, args.icon_url, args.cert_url))
            if not values and not streams and not has_source and not sys.stdin.isatty():
                streams.append(sys.stdin)
            _protect_stdin(args.output, streams)
            queries = _queries(args, streams)
            first = next(queries, None)
            if first is None and (not has_source or values or streams or args.template is not None):
                raise ValueError('请提供 QUERY、-q、--query-file、管道或图标/证书来源。')
            client = stack.enter_context(DayDayMapClient(keys, timeout=args.timeout, interval=args.interval,
                                                        max_retries=args.max_retries, proxy=args.proxy,
                                                        key_cache=False if args.no_key_cache else None))
            sources = []
            if args.icon_file is not None or args.icon_url is not None:
                sources.append(query_from_icon(args.icon_file, url=args.icon_url, timeout=args.timeout, proxy=args.proxy))
            if args.cert_url is not None:
                sources.append(query_from_certificate(args.cert_url, timeout=args.timeout, proxy=args.proxy))
            seen = None
            needs_break = None
            if args.output and args.output != '-':
                destination = Path(args.output).expanduser()
                seen = set(read_lines(destination, not_exists_ok=True))
                needs_break = [False]
                if destination.is_file() and destination.stat().st_size:
                    with destination.open('rb') as existing:
                        existing.seek(-1, os.SEEK_END)
                        needs_break[0] = existing.read(1) not in b'\r\n'
                stream = stack.enter_context(destination.open('a', encoding='utf-8', newline='\n'))
            else:
                stream = sys.stdout
            status = 0
            filters = dict(is_china=args.is_china, is_domain=args.is_domain)
            on_count = None if args.quiet else lambda result: _json({'type': 'count', **result.to_dict()}, sys.stderr)

            def combine(query):
                if not sources:
                    return query
                clauses = ([query] if query is not None else []) + sources
                return ' && '.join(f'({clause})' for clause in clauses)

            if args.count:
                _count_all(client, (combine(q) for q in chain([first], queries)), filters, args.jobs,
                           lambda data: _emit(data, stream, seen=seen, needs_break=needs_break))
                return status
            for query in chain([first], queries):
                query = combine(query)
                iterator = client.search(query, **_search_kwargs(args), **filters, on_count=on_count)
                broken = False
                try:
                    for asset in iterator:
                        _emit(asset, stream, url=args.format == 'url', seen=seen, needs_break=needs_break)
                except _OutputClosed:
                    broken = True
                    raise
                finally:
                    iterator.close()
                    if client.last_summary is not None and not args.quiet and not broken:
                        _json({'type': 'summary', **client.last_summary.to_dict()}, sys.stderr)
                if client.last_summary.truncated:
                    status = 4
            return status
    except _OutputClosed:
        _silence_closed_stdout()
        return 0
    except DayDayMapError as exc:
        payload = exc.to_dict()
        payload['key_files'] = _existing_key_files()
        _json(payload, sys.stderr)
        return _exit_code(exc)
    except (OSError, UnicodeError):
        _json({'error': 'io_error', 'message': '文件读取、编码或输出失败，请检查路径与权限。'}, sys.stderr)
        return 1
    except ValueError as exc:
        _json({'error': 'invalid_argument', 'message': str(exc)}, sys.stderr)
        return 2
    except KeyboardInterrupt:
        _json({'error': 'interrupted', 'message': '查询已中断，已写入的结果已保留。'}, sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
