"""DayDayMap SDK: anonymous aggregate counts and API searches with rotating keys."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import ssl
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Condition, Lock
from typing import Iterable, Iterator
from urllib.parse import quote, unquote, urljoin, urlsplit
from xml.etree import ElementTree

import requests
import urllib3
from requests.exceptions import ConnectTimeout, RequestException
from requests.utils import get_environ_proxies, select_proxy

from .httputil import requests_session

DEFAULT_BASE_URL = 'https://www.daydaymap.com'
API_LIMIT = 10000
_IDENTITY_FIELDS = ('ip', 'port', 'domain', 'protocol', 'url')
_MESSAGES = {
    'no_keys': 'API 查询需要 Key，请提供 daydaymap_keys.txt、指定 Key 文件或环境变量。',
    'quota_exhausted': '所有可用 Key 的积分均已不足。',
    'keys_unavailable': '所有 Key 均不可用，请检查凭证、权限及积分。',
    'invalid_key': 'API Key 无效。',
    'permission_denied': '当前 Key 的会员权限不足。',
    'invalid_query': '查询语法或请求参数无效。',
    'result_limit': '已达到单查询前 10000 条结果窗口。',
    'rate_limited': '请求被限流，有限重试后仍未恢复。',
    'server_error': '服务端数据获取失败。',
    'network_error': '网络请求失败；未自动重复可能已经扣费的请求。',
    'http_error': '服务端返回异常 HTTP 状态。',
    'invalid_response': '服务端响应格式无效。',
    'aggregate_unavailable': '免费聚合未提供可用资产计数。',
    'incomplete_page': '返回页未覆盖预期范围，已保留结果并停止，避免跳页遗漏。',
    'key_file': '无法读取 Key 文件。',
    'icon_file': '无法读取图标文件。',
    'icon_download': '图标下载失败，请检查地址、代理及网络。',
    'invalid_icon': '图标为空、不是支持的图片格式或超过 2 MiB。',
    'certificate_fetch': 'HTTPS 证书获取失败，请检查地址、端口、代理及网络。',
    'proxy_dependency': 'SOCKS 代理需要安装 wtfutil[socks]。',
}


_MAX_ICON_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 5
_PROXY_SCHEMES = ('http', 'https', 'socks5', 'socks5h')


class SourceError(RuntimeError):
    """Reason-only transport error; raw URLs, response bodies and exceptions stay private."""


def _url(value, *, certificate=False, proxy=False):
    message = '代理 URL 格式无效。' if proxy else '请提供有效的 HTTPS URL。' if certificate else '请提供有效的 HTTP(S) URL。'
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(message)
    try:
        parsed = urlsplit(value)
        schemes = _PROXY_SCHEMES if proxy else ('https',) if certificate else ('http', 'https')
        if parsed.scheme not in schemes or not parsed.hostname or parsed.port == 0:
            raise ValueError
        parsed.hostname.encode('idna')
        if proxy:
            if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                raise ValueError
        elif parsed.username is not None or parsed.password is not None:
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError(message) from None
    return parsed


def validate_proxy(proxy):
    if proxy is not None:
        _url(proxy, proxy=True)
    return proxy


def _proxy_for(url, proxy):
    # Explicit proxies override NO_PROXY, matching the SDK's trust_env=False behavior.
    selected = proxy if proxy is not None else select_proxy(url=url, proxies=get_environ_proxies(url))
    return validate_proxy(selected)


def _looks_like_image(data):
    if len(data) < 6:
        return False
    if data.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'BM')):
        return True
    if data.startswith(b'\0\0\1\0') and int.from_bytes(data[4:6], 'little') > 0:
        return True
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return True
    if b'<!doctype' in data.lower() or b'<!entity' in data.lower():
        return False
    try:
        root = ElementTree.fromstring(data)
        return root.tag in ('svg', '{http://www.w3.org/2000/svg}svg')
    except (ElementTree.ParseError, LookupError, ValueError):
        return False


def _download_icon(url, *, proxy, timeout):
    _url(url)
    validate_proxy(proxy)
    try:
        with requests.Session() as session:
            # Resolve proxies explicitly for each redirect, without inheriting .netrc auth.
            session.trust_env = False
            for redirect in range(_MAX_REDIRECTS + 1):
                selected = _proxy_for(url, proxy)
                proxies = {'http': selected, 'https': selected} if selected else {}
                # Keep Requests' CA-bundle environment behavior when no explicit proxy is used.
                verify = (os.environ.get('REQUESTS_CA_BUNDLE') or
                          os.environ.get('CURL_CA_BUNDLE') or True) if proxy is None else True
                with session.get(url, proxies=proxies, timeout=timeout, verify=verify,
                                 stream=True, allow_redirects=False) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get('Location')
                        if not location or redirect == _MAX_REDIRECTS:
                            raise SourceError('icon_download')
                        url = urljoin(url, location)
                        _url(url)
                        continue
                    if response.status_code != 200:
                        raise SourceError('icon_download')
                    body = bytearray()
                    for chunk in response.iter_content(chunk_size=65536):
                        if len(body) + len(chunk) > _MAX_ICON_BYTES:
                            raise SourceError('invalid_icon')
                        body.extend(chunk)
                    return bytes(body)
    except requests.exceptions.InvalidSchema:
        raise SourceError('proxy_dependency') from None
    except (requests.RequestException, OSError):
        raise SourceError('icon_download') from None
    raise SourceError('icon_download')


def icon_md5(path=None, *, url=None, timeout=30, proxy=None):
    if (path is None) == (url is None):
        raise ValueError('图标文件和 URL 必须且只能指定一个。')
    validate_proxy(proxy)
    if path is not None:
        try:
            with Path(path).expanduser().open('rb') as stream:
                data = stream.read(_MAX_ICON_BYTES + 1)
        except OSError:
            raise SourceError('icon_file') from None
    else:
        data = _download_icon(url, timeout=timeout, proxy=proxy)
    if not data or len(data) > _MAX_ICON_BYTES or not _looks_like_image(data):
        raise SourceError('invalid_icon')
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def _certificate_manager(proxy, timeout):
    # This connection samples a certificate, including expired/self-signed certificates.
    # It never authenticates to DayDayMap and does not alter any global SSL context.
    options = dict(timeout=timeout, retries=False, cert_reqs=ssl.CERT_NONE)
    if not proxy:
        return urllib3.PoolManager(**options)
    parsed = _url(proxy, proxy=True)
    if parsed.scheme.startswith('socks'):
        try:
            from urllib3.contrib.socks import SOCKSProxyManager
        except ImportError:
            raise SourceError('proxy_dependency') from None
        return SOCKSProxyManager(proxy, **options)
    headers = {}
    if parsed.username is not None:
        credentials = unquote(parsed.username) + ':' + unquote(parsed.password or '')
        headers = urllib3.make_headers(proxy_basic_auth=credentials)
    return urllib3.ProxyManager(proxy, proxy_headers=headers, **options)


def certificate_md5(url, *, timeout=30, proxy=None):
    parsed = _url(url, certificate=True)
    selected = _proxy_for(url, proxy)
    # Only connect to the requested TLS origin, regardless of its path or HTTP redirects.
    hostname = parsed.hostname.encode('idna').decode('ascii')
    host = f'[{hostname}]' if ':' in hostname else hostname
    origin = f'https://{host}:{parsed.port or 443}'
    manager = None
    connection = None
    try:
        manager = _certificate_manager(selected, timeout)
        pool = manager.connection_from_url(origin)
        # urllib3 does not expose handshake-only sampling. Keep its two pool hooks here,
        # tested with real direct/CONNECT/SOCKS connections, rather than reimplement TLS.
        connection = pool._get_conn(timeout=timeout)
        if pool.proxy is not None:
            pool._prepare_proxy(connection)
        else:
            connection.connect()
        der = connection.sock.getpeercert(binary_form=True)
        if not der:
            raise SourceError('certificate_fetch')
        return hashlib.md5(der, usedforsecurity=False).hexdigest()
    except (OSError, urllib3.exceptions.HTTPError, ValueError, UnicodeError):
        raise SourceError('certificate_fetch') from None
    finally:
        if connection is not None:
            connection.close()
        if manager is not None:
            manager.clear()


class DayDayMapError(RuntimeError):
    """Sanitized failure with stable reason/code/status fields, never a raw payload."""

    def __init__(self, reason: str, *, code: int | None = None, status_code: int | None = None):
        self.reason = reason
        self.code = code
        self.status_code = status_code
        super().__init__(_MESSAGES.get(reason, 'DayDayMap 请求失败。'))

    def to_dict(self):
        return {'error': self.reason, 'message': str(self), 'code': self.code, 'status_code': self.status_code}


@dataclass(frozen=True)
class DayDayMapCount:
    query: str
    total: int
    estimated: bool
    source: str
    ip_count: int | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class DayDayMapSearchSummary:
    query: str
    total: int | None = None
    estimated: bool = True
    returned: int = 0
    fetched: int = 0
    queries: int = 0
    truncated: bool = False
    limit_reached: bool = False
    reason: str = 'running'
    keys_remaining: int = 0

    def to_dict(self):
        return asdict(self)


def _clean_keys(keys):
    if isinstance(keys, str):
        keys = [keys]
    cleaned = []
    for key in keys:
        if not isinstance(key, str):
            raise ValueError('Key 必须为字符串。')
        key = key.strip()
        if not key or key.startswith('#'):
            continue
        if not key.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in key):
            raise ValueError('Key 格式错误；每行必须只有一个无空白的 Key。')
        cleaned.append(key)
    return list(dict.fromkeys(cleaned))


def find_key_file() -> Path | None:
    """Find the first daydaymap_keys.txt in cwd, cwd/resource, then the user home."""
    work = Path.cwd()
    for path in (work / 'daydaymap_keys.txt', work / 'resource' / 'daydaymap_keys.txt'):
        if path.is_file():
            return path
    path = Path.home() / 'daydaymap_keys.txt'
    return path if path.is_file() else None


def load_keys(path: str | Path | None = None) -> list[str]:
    """Read an explicit or discovered UTF-8 key file; absent defaults return []."""
    try:
        if path is None:
            path = find_key_file()
            if path is None:
                return []
        text = Path(path).expanduser().read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        raise DayDayMapError('key_file') from None
    return _clean_keys(text.splitlines())


def _positive_number(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} 必须是有限数值。')
    if value < 0 or (not zero and value == 0):
        raise ValueError(f'{name} 超出允许范围。')
    return value


def _integer(value, name, minimum, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{name} 超出允许的整数范围。')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} 超出允许的整数范围。')
    return value


def _query(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('查询语句不能为空。')
    return value.strip()


def build_query(query: str, *, is_china: bool = False, is_domain: bool = False) -> str:
    """Wrap a raw query and append mandatory honeypot and optional scope filters."""
    query = _query(query)
    if not isinstance(is_china, bool) or not isinstance(is_domain, bool):
        raise ValueError('is_china 和 is_domain 必须为 bool。')
    clauses = [f'({query})', 'ip.tag!="蜜罐"']
    if is_china:
        clauses.extend(('ip.country="CN"', 'ip.province!="香港"', 'ip.province!="澳门"',
                        'ip.province!="台湾"', 'ip.city!="香港"', 'ip.city!="澳门"'))
    if is_domain:
        clauses.append('is_domain="true"')
    return ' && '.join(clauses)


def query_from_icon(path: str | Path | None = None, *, url: str | None = None,
                    timeout: float = 30, proxy: str | None = None) -> str:
    """Return a web.icon MD5 clause from exactly one file or direct image URL."""
    _positive_number(timeout, 'timeout')
    try:
        digest = icon_md5(path, url=url, timeout=timeout, proxy=proxy)
    except SourceError as exc:
        raise DayDayMapError(str(exc)) from None
    return f'web.icon="{digest}"'


def query_from_certificate(url: str, *, timeout: float = 30, proxy: str | None = None) -> str:
    """Sample the HTTPS leaf certificate (SNI/proxy aware), returning its DER MD5 clause."""
    _positive_number(timeout, 'timeout')
    try:
        digest = certificate_md5(url, timeout=timeout, proxy=proxy)
    except SourceError as exc:
        raise DayDayMapError(str(exc)) from None
    return f'cert.md5="{digest}"'


def _fields(value):
    if value is None:
        return ()
    if isinstance(value, str):
        value = value.split(',')
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or any(c.isspace() for c in item.strip()):
            raise ValueError('fields 必须是逗号分隔的字段名或字符串序列。')
        result.append(item.strip())
    return tuple(dict.fromkeys(result))


class _KeyPool:
    """Exclusive round-robin leases; an empty idle queue need not mean exhaustion."""

    def __init__(self, keys):
        self._idle = deque(dict.fromkeys(keys))
        self._leased: set[str] = set()
        self._condition = Condition()

    @property
    def size(self):
        with self._condition:
            return len(self._idle) + len(self._leased)

    def acquire(self):
        with self._condition:
            while not self._idle and self._leased:
                self._condition.wait()
            if not self._idle:
                return None
            key = self._idle.popleft()
            self._leased.add(key)
            return key

    def release(self, key):
        with self._condition:
            if key in self._leased:
                self._leased.remove(key)
                self._idle.append(key)
            self._condition.notify_all()

    def discard(self, key):
        with self._condition:
            self._leased.discard(key)
            if key in self._idle:
                self._idle.remove(key)
            self._condition.notify_all()


def _nonnegative_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


def _bucket_count(item):
    if not isinstance(item, dict):
        return None
    return _nonnegative_int(item.get('count', item.get('value')))


def _aggregate_total(data):
    """Return only a labelled estimate. Missing/empty buckets are not zero."""
    icon = data.get('icon')
    dimensions = [data.get(name) for name in ('port', 'service', 'chart_country_list', 'china_province_list')]
    dimensions.append(icon.get('list') if isinstance(icon, dict) else None)
    sums = []
    for items in dimensions:
        if not isinstance(items, list) or not items:
            continue
        counts = [_bucket_count(item) for item in items]
        if all(count is not None for count in counts):
            sums.append(sum(counts))
    return max(sums) if sums else None


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _split_queries(query, data, limit, cap=10000):
    """Select one useful dimension, bounding requests and avoiding cross-dimension overlap."""
    dimensions = []
    province = data.get('china_province_list') or []
    if not province:
        province = [r for p in data.get('position_list', []) if isinstance(p, dict)
                    for r in (p.get('region_list') or [])]
    definitions = [('ip.province', province), ('ip.port', data.get('port')),
                   ('protocol.service', data.get('service'))]
    for field, items in definitions:
        if field == 'ip.province' and re.search(r'\bip\.(?:city|province|region)\s*=', query):
            continue
        if re.search(r'(?<![\w.])' + re.escape(field) + r'\s*=', query):
            continue
        buckets = {}
        for item in items if isinstance(items, list) else []:
            count = _bucket_count(item)
            if count is None or count == 0:
                continue
            name = str(item.get('name', '')).strip()
            if not name or name in ('其他', '其它', 'other', 'Other'):
                continue
            if field == 'ip.port' and (not name.isascii() or not name.isdigit() or not 0 <= int(name) <= 65535):
                continue
            buckets[f'{field}={_quote(name)}'] = count
        if len(buckets) >= 2:
            dimensions.append(buckets)
    icon = data.get('icon')
    if isinstance(icon, dict) and isinstance(icon.get('list'), list):
        buckets = {}
        for item in icon['list']:
            count = _bucket_count(item)
            syntax = item.get('icon_syntax') if isinstance(item, dict) else None
            if count and isinstance(syntax, str) and syntax.strip():
                buckets[syntax.strip()] = count
        if len(buckets) >= 2:
            dimensions.append(buckets)
    if not dimensions:
        return []
    # Rank by the work actually permitted, rather than the sum of every bucket.
    def ranked(buckets):
        return sorted(buckets.items(), key=lambda pair: (-min(pair[1], cap), pair[1] >= cap, pair[0]))[:limit]
    best = max(dimensions, key=lambda buckets: sum(min(count, cap) for _, count in ranked(buckets)))
    return [f'({query}) && ({syntax})' for syntax, _ in ranked(best)]


def _asset_identity(row):
    if row.get('ip') and row.get('port') is not None:
        return (str(row['ip']).lower(), str(row['port']), str(row.get('domain') or '').lower(),
                str(row.get('protocol') or '').lower())
    if row.get('url'):
        return ('url', str(row['url']))
    return ('record', json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':')))


class DayDayMapClient:
    """Owns two separate sessions; caller-supplied sessions are never closed.

    A client is intended for sequential calls (last_summary describes its last
    search). Its internal key leases are synchronized. External sessions control
    their own transport retry policy and must not enable hidden POST retries.
    """

    def __init__(self, keys: Iterable[str] = (), *, session=None, web_session=None,
                 timeout: float = 30, interval: float = 0.5, max_retries: int = 2,
                 retry_backoff: float = 1, proxy: str | None = None):
        _positive_number(timeout, 'timeout')
        _positive_number(interval, 'interval', zero=True)
        _positive_number(retry_backoff, 'retry_backoff', zero=True)
        _integer(max_retries, 'max_retries', 0, 20)
        validate_proxy(proxy)
        if session is not None and session is web_session:
            raise ValueError('API 与匿名聚合必须使用不同的 session。')
        self._keys = _KeyPool(_clean_keys(keys))
        self._had_keys = self._keys.size > 0
        self._disabled_codes: list[int] = []
        self.timeout = timeout
        self.interval = interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._owned_session = session is None
        self._owned_web = web_session is None
        options = dict(timeout=timeout, proxies=proxy or False, verify=True, max_retries=0,
                       user_agent='Mozilla/5.0 (compatible; wtfutil-DayDayMap/1.0)')
        self._session = session if session is not None else requests_session(**options)
        try:
            self._web_session = web_session if web_session is not None else requests_session(**options)
        except Exception:
            if self._owned_session:
                self._session.close()
            raise
        self._request_lock = Lock()
        self._last_request: float | None = None
        self.last_summary: DayDayMapSearchSummary | None = None
        self._closed = False

    @classmethod
    def from_key_file(cls, path: str | Path | None = None, **kwargs):
        return cls(load_keys(path), **kwargs)

    @property
    def available_keys(self):
        return self._keys.size

    def close(self):
        if not self._closed:
            if self._owned_session:
                self._session.close()
            if self._owned_web:
                self._web_session.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _retry_delay(self, response, attempt):
        delay = self.retry_backoff * (2 ** attempt)
        raw = response.headers.get('Retry-After') if response is not None else None
        if raw:
            try:
                delay = max(delay, float(raw))
            except (ValueError, TypeError):
                try:
                    when = parsedate_to_datetime(raw)
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    delay = max(delay, (when - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError, OverflowError):
                    pass
        # Long Retry-After is respected by stopping, not by sending an early retry.
        if not math.isfinite(delay) or delay > 60:
            raise DayDayMapError('rate_limited')
        if delay > 0:
            time.sleep(delay)

    def _post(self, session, path, payload, headers):
        if self._closed:
            raise ValueError('客户端已经关闭。')
        for attempt in range(self.max_retries + 1):
            response = None
            transient = None
            try:
                with self._request_lock:
                    if self._last_request is not None:
                        delay = self.interval - (time.monotonic() - self._last_request)
                        if delay > 0:
                            time.sleep(delay)
                    self._last_request = time.monotonic()
                    response = session.post(DEFAULT_BASE_URL + path, headers=headers, json=payload,
                                            timeout=self.timeout, allow_redirects=False)
            except ConnectTimeout:
                transient = 'network_error'
            except RequestException:
                raise DayDayMapError('network_error') from None
            if response is not None:
                if response.status_code == 429:
                    transient = 'rate_limited'
                elif not 200 <= response.status_code < 300:
                    raise DayDayMapError('http_error', status_code=response.status_code)
                else:
                    try:
                        envelope = response.json()
                    except (ValueError, RequestException):
                        raise DayDayMapError('invalid_response') from None
                    if not isinstance(envelope, dict):
                        raise DayDayMapError('invalid_response')
                    code = _nonnegative_int(envelope.get('code'))
                    if code == 2006:
                        transient = 'server_error'
                    elif code == 429:
                        transient = 'rate_limited'
                    elif code != 200:
                        reason = {2001: 'invalid_key', 2002: 'invalid_query', 470: 'invalid_query',
                                  2003: 'permission_denied', 2004: 'quota_exhausted', 2005: 'result_limit'}.get(code)
                        raise DayDayMapError(reason or 'invalid_response', code=code)
                    else:
                        data = envelope.get('data')
                        if not isinstance(data, dict):
                            raise DayDayMapError('invalid_response')
                        return data
            if attempt == self.max_retries:
                raise DayDayMapError(transient or 'network_error') from None
            self._retry_delay(response, attempt)
        raise DayDayMapError('network_error')  # defensive; retry loop always exits above

    def _aggregate(self, query):
        keyword = base64.b64encode(query.encode('utf-8')).decode('ascii')
        payload = {'page': 1, 'page_size': 10, 'keyword': keyword, 'scan_time': [],
                   'asset_tag': '', 'asset_type': '', 'data_filter': []}
        headers = {'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json',
                   'language': 'zh-cn', 'Origin': DEFAULT_BASE_URL,
                   'Referer': DEFAULT_BASE_URL + '/searchResult?keyword=' + quote(keyword, safe='')}
        return self._post(self._web_session, '/api/v1/raymap/search/aggregate/query', payload, headers)

    def _api(self, query, page_number, page_size, fields=(), exclude_fields=()):
        payload = {'page': page_number, 'page_size': page_size,
                   'keyword': base64.b64encode(query.encode('utf-8')).decode('ascii')}
        if fields:
            payload['fields'] = ','.join(fields)
        elif exclude_fields:
            payload['exclude_fields'] = ','.join(exclude_fields)
        while True:
            key = self._keys.acquire()
            if key is None:
                reason = 'no_keys' if not self._had_keys else 'keys_unavailable'
                if self._disabled_codes and all(code == 2004 for code in self._disabled_codes):
                    reason = 'quota_exhausted'
                raise DayDayMapError(reason)
            try:
                return self._post(self._session, '/api/v1/raymap/search/all', payload,
                                  {'api-key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
            except DayDayMapError as exc:
                if exc.code not in (2001, 2003, 2004):
                    raise
                self._disabled_codes.append(exc.code)
                self._keys.discard(key)
            finally:
                self._keys.release(key)

    def count(self, query: str, *, is_china: bool = False,
              is_domain: bool = False) -> DayDayMapCount:
        query = build_query(query, is_china=is_china, is_domain=is_domain)
        data = None
        try:
            data = self._aggregate(query)
        except DayDayMapError as exc:
            if exc.reason in ('invalid_query', 'rate_limited'):
                raise
        if data is not None:
            total = _aggregate_total(data)
            if total is not None:
                return DayDayMapCount(query, total, True, 'aggregate', _nonnegative_int(data.get('ip_num')))
        if not self.available_keys:
            raise DayDayMapError('aggregate_unavailable')
        data = self._api(query, 1, 1, ('ip',))
        total = _nonnegative_int(data.get('total'))
        if total is None:
            raise DayDayMapError('invalid_response')
        return DayDayMapCount(query, total, False, 'api')

    def search(self, query: str, *, fields=None, exclude_fields=None, page_size: int = 500,
               limit: int = 10000, max_effort: bool = False, max_effort_depth: int = 10,
               is_china: bool = False, is_domain: bool = False, on_count=None) -> Iterator[dict]:
        """Stream rows; last_summary remains available even after partial failure.

        A fixed page width is used throughout each child query. It is reduced
        before the first page when the local limit is smaller. Short non-final
        pages are reported as incomplete rather than silently skipping offsets.
        """
        query = build_query(query, is_china=is_china, is_domain=is_domain)
        if on_count is not None and not callable(on_count):
            raise ValueError('on_count 必须可调用。')
        _integer(page_size, 'page_size', 1, 10000)
        _integer(limit, 'limit', 0)
        _integer(max_effort_depth, 'max_effort_depth', 1, 1000)
        selected, excluded = _fields(fields), _fields(exclude_fields)
        if selected:
            excluded = ()
        requested = selected
        wire_excluded = excluded
        if max_effort:
            if selected:
                requested = tuple(dict.fromkeys((*selected, *_IDENTITY_FIELDS)))
            elif excluded:
                wire_excluded = tuple(name for name in excluded if name not in _IDENTITY_FIELDS)
        summary = DayDayMapSearchSummary(query, keys_remaining=self.available_keys)
        self.last_summary = summary
        seen = set()
        used_split = False
        data = None
        try:
            try:
                data = self._aggregate(query)
            except DayDayMapError as exc:
                if exc.reason in ('invalid_query', 'rate_limited'):
                    raise
            if data is not None:
                summary.total = _aggregate_total(data)
            if on_count is not None and summary.total is not None:
                on_count(DayDayMapCount(query, summary.total, True, 'aggregate',
                                        _nonnegative_int(data.get('ip_num'))))
            planned = []
            if max_effort and summary.total is not None and summary.total > API_LIMIT:
                planned = _split_queries(query, data, max_effort_depth, API_LIMIT)
            used_split = bool(planned)
            pending = list(planned) if planned else [query]
            if used_split:
                summary.truncated = True
            while pending:
                child = pending.pop(0)
                summary.queries += 1
                remaining = limit - summary.returned if limit else API_LIMIT
                if remaining <= 0:
                    break
                # Never vary page_size halfway through a query: page offsets depend on it.
                width = min(page_size, remaining, API_LIMIT)
                offset = 0
                capped = False
                for page_number in range(1, (API_LIMIT + width - 1) // width + 1):
                    try:
                        body = self._api(child, page_number, width, requested, wire_excluded)
                    except DayDayMapError as exc:
                        if exc.reason != 'result_limit':
                            raise
                        summary.truncated = True
                        summary.reason = 'result_limit'
                        capped = True
                        break
                    total = _nonnegative_int(body.get('total'))
                    items = body.get('list')
                    if total is None or not isinstance(items, list) or len(items) > width or any(not isinstance(x, dict) for x in items):
                        raise DayDayMapError('invalid_response')
                    if child == query:
                        if on_count is not None and summary.total is None:
                            on_count(DayDayMapCount(query, total, False, 'api'))
                        summary.total = total
                        summary.estimated = False
                    summary.fetched += len(items)
                    usable = items[:max(0, API_LIMIT - offset)]
                    for item in usable:
                        if max_effort:
                            identity = _asset_identity(item)
                            if identity in seen:
                                continue
                            seen.add(identity)
                        projected = {name: item[name] for name in selected if name in item} if selected else {
                            name: value for name, value in item.items() if name not in excluded}
                        summary.returned += 1
                        yield projected
                        if limit and summary.returned >= limit:
                            # Hitting a requested output count isn't truncation if it was the actual final row.
                            complete = not used_split and offset + len(items) >= total and summary.returned >= total
                            summary.limit_reached = not complete
                            summary.truncated = summary.truncated or not complete
                            summary.reason = 'best_effort' if used_split else ('limit' if not complete else 'complete')
                            return
                    offset += len(items)
                    if offset >= total:
                        break
                    if offset >= API_LIMIT:
                        summary.truncated = True
                        summary.reason = 'result_limit'
                        capped = True
                        break
                    if len(items) < width:
                        raise DayDayMapError('incomplete_page')
                if capped and max_effort and child == query and not used_split:
                    if data is None:
                        try:
                            data = self._aggregate(query)
                        except DayDayMapError as exc:
                            if exc.reason in ('invalid_query', 'rate_limited'):
                                raise
                    planned = _split_queries(query, data, max_effort_depth, API_LIMIT) if data else []
                    if planned:
                        used_split = True
                        pending.extend(planned)
            if used_split:
                summary.reason = 'best_effort'
                summary.truncated = True
            elif summary.reason == 'running':
                summary.reason = 'complete'
        except DayDayMapError as exc:
            summary.reason = exc.reason
            summary.truncated = True
            raise
        except (KeyboardInterrupt, GeneratorExit):
            summary.reason = 'interrupted'
            summary.truncated = True
            raise
        finally:
            summary.keys_remaining = self.available_keys


__all__ = ['DEFAULT_BASE_URL', 'DayDayMapClient', 'DayDayMapError', 'DayDayMapCount',
           'DayDayMapSearchSummary', 'find_key_file', 'load_keys', 'build_query',
           'query_from_icon', 'query_from_certificate']
