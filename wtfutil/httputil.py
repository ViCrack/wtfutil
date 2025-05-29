import functools
import ipaddress
import json
import os
import random
import socket
import ssl
import threading
import time
import re
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from socket import gethostbyname
from typing import Callable, List, Generator, Tuple, Optional
from urllib.parse import urljoin
from urllib.parse import urlparse

import faker
from fake_useragent import UserAgent
import requests
import tldextract
import urllib3
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import JSONDecodeError
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from requests.utils import to_native_string
from requests_cache import CachedSession
from requests_toolbelt.utils import dump
from rich.progress import Progress

from .strutil import *

_http_context = threading.local()


def get_redirect_target(self, resp):
    """hook requests.Session.get_redirect_target method"""
    if resp.is_redirect:
        location = resp.headers['location']
        location = location.encode('latin1')
        encoding = resp.encoding if resp.encoding else 'utf-8'
        return to_native_string(location, encoding)
    return None


def patch_redirect():
    requests.Session.get_redirect_target = get_redirect_target


def remove_ssl_verify():
    ssl._create_default_https_context = ssl._create_unverified_context


def patch_getproxies():
    # 高版本python已经修复了这个问题
    # https://bugs.python.org/issue42627
    # https://www.cnblogs.com/davyyy/p/14388623.html
    if os.name == 'nt':
        import urllib.request
        old_getproxies_registry = urllib.request.getproxies_registry

        def hook():
            proxies = old_getproxies_registry()
            if 'https' in proxies:
                proxies['https'] = proxies['https'].replace('https://', 'http://')
            return proxies

        urllib.request.getproxies_registry = hook


urllib3.disable_warnings()
remove_ssl_verify()
patch_redirect()
patch_getproxies()


class EnhancedResponse(Response):
    def json(self, **kwargs):
        try:
            return super().json(**kwargs)
        except JSONDecodeError as e:
            # 如果开了debug，那么http数据库都会打印，就不需要重复了
            if not self._debug:
                print("-" * 50)
                print(f"Request URL: {self.url}")
                print(f"Response status code: {self.status_code}")
                print(f"JSONDecodeError: {e}")
                print(f"Response text: {self.text}")
                print("-" * 50)
            raise


class RequestsSession(requests.Session):
    """
    增强的 requests.Session 类，支持在请求准备和发送前通过 hook 修改请求参数。

    Attributes:
        _debug (bool): 是否启用调试模式，打印请求和响应的详细信息
        _rate_limit (int | None): 每秒最大请求数，例如 10 表示 10 次/秒
        _last_request_time (float): 上次请求的时间戳，用于速率限制
        pre_request_hooks (List[Callable]): 在 prepare_request 阶段执行的 hook 列表
        pre_send_hooks (List[Callable]): 在 send 阶段执行的 hook 列表
    """

    def __init__(self, debug: bool = False, rate_limit: int | None = None):
        super().__init__()
        self._debug = debug
        if rate_limit is not None and rate_limit <= 0:
            raise ValueError("rate_limit must be a positive number")
        self._rate_limit = rate_limit  # 每秒请求限制（例如 10 表示 10 次/秒）
        self._last_request_time = 0
        self.pre_request_hooks: List[Callable[[requests.Request], None]] = []
        self.pre_send_hooks: List[Callable[[requests.PreparedRequest, dict], None]] = []

    def pre_request(self, func: Callable):
        """装饰器，用于注册 pre_request_hook
        # 使用示例
        session = RequestsSession()

        @session.pre_request
        def add_custom_header(request, *args, **kwargs):
            request.headers['X-Custom'] = 'Value'
        """

        self.pre_request_hooks.append(func)
        return func

    def pre_send(self, func: Callable):
        """装饰器，用于注册 pre_send_hook"""
        self.pre_send_hooks.append(func)
        return func

    def prepare_request(self, request: requests.Request) -> requests.PreparedRequest:
        """
        准备请求对象，应用 pre_request_hooks。

        Args:
            request (requests.Request): 未准备的请求对象
            *args: 传递给 hook 的额外位置参数
            **kwargs: 传递给 hook 的额外关键字参数

        Returns:
            requests.PreparedRequest: 已准备好的请求对象
        """
        parsed_url = urlparse(request.url)
        if 'Referer' not in request.headers and 'Referer' not in self.headers:
            request.headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        if 'Origin' not in request.headers and 'Origin' not in self.headers:
            request.headers['Origin'] = f"{parsed_url.scheme}://{parsed_url.netloc}"

        for hook in self.pre_request_hooks:
            hook(request)
        return super().prepare_request(request)

    def send(self, request: requests.PreparedRequest, **kwargs) -> requests.Response:
        """
        发送准备好的请求，应用 pre_send_hook。

        Args:
            request (requests.PreparedRequest): 已准备好的请求对象
            **kwargs: 传递给请求的额外参数（如 proxies、timeout 等）

        Returns:
            requests.Response: 服务器返回的响应对象
        """
        for hook in self.pre_send_hooks:
            # 这里需要传递的是dict，而不能解包
            hook(request, kwargs)
        return super().send(request, **kwargs)

    def request(self, method: str, url: str, *args, **kwargs) -> requests.Response:
        """
        执行 HTTP 请求，支持速率限制和调试输出。

        Args:
            method (str): HTTP 方法（如 GET、POST）
            url (str): 请求的目标 URL
            *args: 传递给父类 request 方法的位置参数
            **kwargs: 传递给父类 request 方法的关键字参数

        Returns:
            requests.Response: 服务器返回的响应对象
        """
        # 速率限制
        if self._rate_limit:
            elapsed = time.time() - self._last_request_time
            if elapsed < 1.0 / self._rate_limit:
                time.sleep(1.0 / self._rate_limit - elapsed)
            self._last_request_time = time.time()
        # 调用父类的 request 方法
        response = super().request(method, url, *args, **kwargs)
        # 如果 debug 启用，使用 requests-toolbelt 的 dump 打印数据包
        if self._debug:
            print("HTTP Request and Response Packet:")
            dumped_data = dump.dump_all(response, request_prefix=b"> ", response_prefix=b"< ")
            print(dumped_data.decode('utf-8'))
            print("-" * 50)  # 分隔符
        # 将 response 的类替换，增加json的打印调试
        response.__class__ = EnhancedResponse
        response._debug = self._debug
        return response


class BaseUrlSession(RequestsSession):
    """A Session with a URL that all requests will use as a base.
    .. note::
        The base URL that you provide and the path you provide are **very**
        important.
    Let's look at another *similar* example
    .. code-block:: python
        >>> from requests_toolbelt import sessions
        >>> s = sessions.BaseUrlSession(
        ...     base_url='https://example.com/resource/')
        >>> r = s.get('/sub-resource/', params={'foo': 'bar'})
        >>> print(r.request.url)
        https://example.com/sub-resource/?foo=bar
    The key difference here is that we called ``get`` with ``/sub-resource/``,
    i.e., there was a leading ``/``. This changes how we create the URL
    because we rely on :mod:`urllib.parse.urljoin`.
    To override how we generate the URL, sub-class this method and override the
    ``create_url`` method.
    Based on implementation from
    https://github.com/kennethreitz/requests/issues/2554#issuecomment-109341010

    作者一直没在requests上加这个功能, urljoin容易有缺陷
    https://stackoverflow.com/questions/42601812/python-requests-url-base-in-session
    """

    base_url = None

    def __init__(self, base_url=None, debug=False, rate_limit=None):
        if base_url:
            self.base_url = base_url
        super().__init__(debug=debug, rate_limit=rate_limit)

    def request(self, method, url, *args, **kwargs):
        """Send the request after generating the complete URL."""
        url = self.create_url(url)
        return super().request(
            method, url, *args, **kwargs
        )

    def prepare_request(self, request, *args, **kwargs):
        """Prepare the request after generating the complete URL."""
        request.url = self.create_url(request.url)
        return super().prepare_request(
            request, *args, **kwargs
        )

    def create_url(self, url):
        """Create the URL based off this partial path."""
        return urljoin(self.base_url.rstrip("/") + "/", url.lstrip("/"))


class CustomSslContextHttpAdapter(HTTPAdapter):
    # https://github.com/urllib3/urllib3/issues/2653
    # openssl 3.0 bug --> (Caused by SSLError(SSLError(1, '[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled (_ssl.c:1006)')))
    """"Transport adapter" that allows us to use a custom ssl context object with the requests."""

    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = create_urllib3_context()
        ctx.load_default_certs()
        ctx.check_hostname = False  # ValueError: Cannot set verify_mode to CERT_NONE when check_hostname is enabled
        ctx.options |= 0x4  # ssl.OP_LEGACY_SERVER_CONNECT
        self.poolmanager = urllib3.PoolManager(ssl_context=ctx)


@dataclass
class ChunkedConfig:
    """
    分块传输的配置类，用于设置 chunked 传输的参数。

    Attributes:
        chunk_size_range: 分块大小范围 (min, max)，单位为字节。
        delay_range: 分块间的延迟范围 (min, max)，单位为秒，None 表示无延迟。
        comment_length_range: 注释长度范围 (min, max)，None 表示不加注释。
        keywords: 拦截关键词列表，强制分拆，None 表示无。

    Raises:
        ValueError: 如果配置参数不合法（例如 min > max 或负值）。
    """
    chunk_size_range: Optional[Tuple[int, int]] = None
    delay_range: Optional[Tuple[float, float]] = None
    comment_length_range: Optional[Tuple[int, int]] = None
    keywords: Optional[List[bytes]] = None

    def __post_init__(self):
        """验证配置参数的合法性并初始化默认值"""
        # 设置默认值
        if self.chunk_size_range is None:
            self.chunk_size_range = (3, 10)
        if self.keywords is None:
            self.keywords = [s.lower().encode() for s in [
                # 文件类型
                'asp', 'jsp', 'php', 'aspx',
                # SQL Injection
                'select', 'union', 'insert', 'update', 'delete', 'drop', 'truncate',
                'from', 'where', 'having', 'order', 'group',
                'sleep', 'benchmark', 'information_schema', 'database',
                # 文件操作
                'load_file', 'outfile', 'filename', 'dumpfile', 'form-data', 'name', 'position', 'upload', 'content',
                # XSS / 特殊标签
                'script', 'iframe', 'img', 'onerror', 'onload',
                'eval', 'assert', 'system', 'exec', 'java', 'runtime'
            ]]

        # 验证 chunk_size_range
        if not (isinstance(self.chunk_size_range, tuple) and len(self.chunk_size_range) == 2):
            raise ValueError("chunk_size_range must be a tuple of (min, max)")
        min_size, max_size = self.chunk_size_range
        if not (isinstance(min_size, int) and isinstance(max_size, int)):
            raise ValueError("chunk_size_range values must be integers")
        if min_size <= 0 or max_size <= 0:
            raise ValueError("chunk_size_range values must be positive")
        if min_size > max_size:
            raise ValueError("chunk_size_range min must not exceed max")

        # 验证 delay_range
        if self.delay_range is not None:
            if not (isinstance(self.delay_range, tuple) and len(self.delay_range) == 2):
                raise ValueError("delay_range must be a tuple of (min, max) or None")
            min_delay, max_delay = self.delay_range
            if not (isinstance(min_delay, (int, float)) and isinstance(max_delay, (int, float))):
                raise ValueError("delay_range values must be numbers")
            if min_delay < 0 or max_delay < 0:
                raise ValueError("delay_range values must be non-negative")
            if min_delay > max_delay:
                raise ValueError("delay_range min must not exceed max")

        # 验证 comment_length_range
        if self.comment_length_range is not None:
            if not (isinstance(self.comment_length_range, tuple) and len(self.comment_length_range) == 2):
                raise ValueError("comment_length_range must be a tuple of (min, max) or None")
            min_len, max_len = self.comment_length_range
            if not (isinstance(min_len, int) and isinstance(max_len, int)):
                raise ValueError("comment_length_range values must be integers")
            if min_len < 0 or max_len < 0:
                raise ValueError("comment_length_range values must be non-negative")
            if min_len > max_len:
                raise ValueError("comment_length_range min must not exceed max")

    @classmethod
    def default(cls) -> 'ChunkedConfig':
        """返回默认的分块配置"""
        return cls(
            chunk_size_range=(3, 10),
            delay_range=None,
            comment_length_range=None,
            keywords=None
        )

    @classmethod
    def aggressive(cls) -> 'ChunkedConfig':
        """返回更激进的分块配置（小块、短延迟、随机注释）"""
        return cls(
            chunk_size_range=(3, 10),
            delay_range=(0.1, 0.8),
            comment_length_range=(0, 50),
            keywords=None
        )


# 保存原始 request 与 send 方法
_original_request = urllib3.connection.HTTPConnection.request
_original_send = urllib3.connection.HTTPConnection.send


def custom_urllib3_request(self, method, url, body=None, headers=None, **kwargs):
    """
    如果 headers 中包含 Transfer-Encoding: chunked，则在 self 上设置 _custom_chunked 标志
    """
    if headers and headers.get("Transfer-Encoding", "").lower() == "chunked":
        self._custom_chunked = True
    else:
        self._custom_chunked = False
    return _original_request(self, method, url, body, headers, **kwargs)


def custom_urllib3_send(self, data: bytes):
    """
    钩住 send 方法，如果当前连接处于 _custom_chunked 模式，就
    对数据进行解析，并在发送前插入注释。
    这里假定数据格式为： b"<hex_length>\r\n<chunk>\r\n"
    """
    if getattr(self, "_custom_chunked", False) and data != b"0\r\n\r\n":
        chunked_config: Optional[ChunkedConfig] = getattr(_http_context, "chunked_config", None)
        if chunked_config and chunked_config.comment_length_range:

            # 匹配 chunked 数据格式
            pattern = re.compile(br'^([0-9A-Fa-f]+)\r\n(.*)\r\n$', re.DOTALL)
            match = pattern.match(data)
            if match:
                header = match.group(1)  # 十六进制长度部分
                chunk_body = match.group(2)  # 数据部分
                try:
                    expected_length = int(header, 16)
                except ValueError:
                    return _original_send(self, data)
                if 0 < expected_length == len(chunk_body):
                    length = random.randint(*chunked_config.comment_length_range)
                    data = header + b';' + rand_base(length).encode() + b"\r\n" + chunk_body + b"\r\n"

    return _original_send(self, data)


# 替换 urllib3.connection.HTTPConnection 的 request 和 send
urllib3.connection.HTTPConnection.request = custom_urllib3_request
urllib3.connection.HTTPConnection.send = custom_urllib3_send


class ChunkedAdapter(HTTPAdapter):
    """智能分块传输适配器（默认不启用延迟和注释）
    https://gv7.me/articles/2021/java-deserialized-data-bypasses-waf-through-sleep-chunked/

    # 使用默认配置
    session = requests_session(chunked=True)

    # 使用激进配置
    session = requests_session(chunked=ChunkedConfig.aggressive())

    # 自定义配置，包括自定义关键词
    custom_config = ChunkedConfig(
        chunk_size_range=(5, 15),
        delay_range=(0.2, 1.0),
        comment_length_range=(10, 100),
    )
    session = requests_session(chunked=custom_config)
    """

    def __init__(self, chunked_config: ChunkedConfig = None, debug=False, **kwargs):
        # 默认配置：不启用延迟和注释
        self.chunked_config = chunked_config or ChunkedConfig.default()
        self.debug = debug
        super().__init__(**kwargs)

    def _chunk_generator(self, data: bytes) -> Generator[bytes, None, None]:
        """核心分块生成逻辑"""
        buffer = BytesIO(data)

        min_size, max_size = self.chunked_config.chunk_size_range
        while True:
            remaining = buffer.getbuffer().nbytes - buffer.tell()
            if remaining <= 0:
                break

            max_size = min(max_size, remaining)
            if min_size > max_size:
                chunk_size = remaining
            else:
                chunk_size = random.randint(min_size, max_size)

            chunk = buffer.read(chunk_size)
            if not chunk:
                break

            lower_chunk = chunk.lower()
            split_points = set()

            for keyword in self.chunked_config.keywords:
                search_pos = 0
                while True:
                    found = lower_chunk.find(keyword, search_pos)
                    if found == -1:
                        break
                    # 拆分位置：关键词中间随机一点
                    if len(keyword) > 2:
                        split_point = found + random.randint(1, len(keyword) - 1)
                        if 0 < split_point < len(chunk):  # 防止溢出
                            split_points.add(split_point)
                    search_pos = found + 1

            if split_points:
                # 按照位置升序拆分
                split_points = sorted(split_points)
                prev = 0
                for point in split_points:
                    if point > prev:
                        part = chunk[prev:point]
                        yield part
                        prev = point
                # 最后剩余部分
                if prev < len(chunk):
                    part = chunk[prev:]
                    yield part
            else:
                # 没有敏感词，正常发送
                yield chunk

            if self.chunked_config.delay_range:
                delay_time = random.uniform(*self.chunked_config.delay_range)
                if self.debug:
                    print(f"[DEBUG] 分块传输延迟：{delay_time}")
                time.sleep(delay_time)

    def send(self, request, **kwargs):
        """处理分块传输请求"""
        if request.body and not isinstance(request.body, Generator):
            # 数据预处理
            data = request.body.encode() if isinstance(request.body, str) else bytes(request.body)
            request.body = self._chunk_generator(data)

            # 自动设置请求头
            if 'Transfer-Encoding' not in request.headers:
                request.headers['Transfer-Encoding'] = 'chunked'
            if 'Content-Length' in request.headers:
                del request.headers['Content-Length']

            _http_context.chunked_config = self.chunked_config

        result = super().send(request, **kwargs)
        del _http_context.chunked_config
        return result


def requests_session(
        proxies: dict[str, str] | int | None = False,
        timeout: float | None = None,
        debug: bool = False,
        base_url: str | None = None,
        user_agent: str | None = None,
        use_cache: bool | dict[str, any] | None = None,
        fake_ip: bool = False,
        rate_limit: int | None = None,
        chunked: bool | ChunkedConfig = False,
        max_retries: int = requests.adapters.DEFAULT_RETRIES,
        pool_connections: int = requests.adapters.DEFAULT_POOLSIZE,
        pool_maxsize: int = requests.adapters.DEFAULT_POOLSIZE
) -> RequestsSession:
    """
    创建并返回一个增强的 requests session。

    Args:
        proxies: 代理设置，可以是字典、端口号或 None。默认 False。
        max_retries: 最大重试次数。默认 1。
        timeout: 请求超时时间（秒）。默认 None。
        debug: 是否启用调试模式。默认 False。
        base_url: 基础 URL，用于 BaseUrlSession。默认 None。
        user_agent: 自定义 User-Agent。默认 None（使用 fake_useragent 生成）。
        use_cache: 是否启用缓存，或缓存配置字典。默认 None。
        fake_ip: 是否添加伪造的 X-Forwarded-For IP。默认 False。
        rate_limit: 每秒最大请求数。默认 None。
        chunked: 是否启用分块传输，可以是 bool 或 ChunkedConfig 对象。
                 如果为 True，使用默认配置；如果为 ChunkedConfig，使用自定义配置。
        pool_connections: 连接池最大连接数。默认 10。
        pool_maxsize: 连接池最大连接数。默认 10。

    Returns:
        一个根据配置生成的 session 对象（CachedSession, BaseUrlSession 或 RequestsSession）。

    Raises:
        TypeError: 如果 proxies 类型无效。
    """
    if use_cache:
        if use_cache:
            session = CachedSession()
        else:
            session = CachedSession(**use_cache)
    elif base_url:
        session = BaseUrlSession(base_url, debug=debug, rate_limit=rate_limit)
    else:
        session = RequestsSession(debug=debug, rate_limit=rate_limit)

    ua = UserAgent()
    session.headers.update({
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'User-Agent': user_agent or ua.random,
    })
    if fake_ip:
        if isinstance(fake_ip, bool):
            fake = faker.Faker('zh_CN')
            fake_ip = fake.ipv4()
        session.headers.update({
            'X-Forwarded-For': fake_ip,
        })
    session.verify = False
    session.mount('http://', HTTPAdapter(max_retries=max_retries, pool_connections=pool_connections, pool_maxsize=pool_maxsize))
    session.mount('https://', CustomSslContextHttpAdapter(max_retries=max_retries, pool_connections=pool_connections, pool_maxsize=pool_maxsize))

    if chunked:
        if isinstance(chunked, bool) and chunked:
            chunked_config = ChunkedConfig.default()
        elif isinstance(chunked, ChunkedConfig):
            chunked_config = chunked
        else:
            raise TypeError("chunked must be bool or ChunkedConfig")

        adapter = ChunkedAdapter(chunked_config=chunked_config, debug=debug, max_retries=max_retries, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

    if timeout is not None:
        session.request = functools.partial(session.request, timeout=timeout)

    if proxies:
        if isinstance(proxies, dict):
            session.proxies = proxies
        elif isinstance(proxies, str):
            session.proxies = {"http":proxies, "https": proxies}
        elif isinstance(proxies, int):
            session.proxies = {"http": "http://127.0.0.1:" + str(proxies), "https": "http://127.0.0.1:" + str(proxies)}
        else:
            raise TypeError('proxies must be dict or string or int')

        session.trust_env = False

    return session


ORIGIN_CIPHERS = 'ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+HIGH:DH+HIGH:ECDH+3DES:DH+3DES:RSA+AESGCM:RSA+AES:RSA+HIGH:RSA+3DES'


class DESAdapter(HTTPAdapter):
    """
    https://blog.csdn.net/god_zzZ/article/details/123010576
    反爬虫检测TLS指纹
    https://ja3er.com/json
    """

    def __init__(self, *args, **kwargs):
        # 在请求中重新启用 3DES 支持的 TransportAdapter
        CIPHERS = ORIGIN_CIPHERS.split(":")
        random.shuffle(CIPHERS)
        # print("1:", CIPHERS)
        CIPHERS = ":".join(CIPHERS)
        # print("2:", CIPHERS)
        self.COPHERS = CIPHERS + ":!aNULL:!eNULL:!MD5"
        super(DESAdapter, self).__init__(*args, **kwargs)

    # 在一般情况下，当我们实现一个子类的时候，__init__的第一行应该是super().__init__(*args, **kwargs)，
    # 但是由于init_poolmanager和proxy_manager_for是复写了父类的两个方法，
    # 这两个方法是在执行super().__init__(*args, **kwargs)的时候就执行的。
    # 所以，我们随机设置 Cipher Suits 的时候，需要放在super().__init__(*args, **kwargs)的前面。
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=self.COPHERS)
        kwargs["ssl_context"] = context
        return super(DESAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=self.COPHERS)
        kwargs["ssl_context"] = context


def httpraw(raw: str, ssl: bool = False, **kwargs) -> requests.Response:
    """
    代码来源Pocsuite, 修复postData只发送一行的bug
    发送原始HTTP封包请求,如果你在参数中设置了例如headers参数，将会发送你设置的参数
    请求头需要用: 补上空格隔开

    :param raw:原始封包文本
    :param ssl:是否是HTTPS
    :param kwargs:支持对requests中的参数进行设置
    :return:requests.Response
    """
    raw = raw.strip()
    # Clear up unnecessary spaces
    raws = list(map(lambda x: x.strip(), raw.splitlines()))
    try:
        method, path, protocol = raws[0].split(" ")
    except Exception:
        raise ValueError("Invalid protocol format: first line must be 'METHOD PATH PROTOCOL'")
    post = None
    _json = None
    if method.upper() == "POST":
        index = 0
        for i in raws:
            index += 1
            if i.strip() == "":
                break
        if len(raws) == index:
            raise Exception("Invalid protocol format: no post data")
        tmp_headers = raws[1:index - 1]
        tmp_headers = extract_dict('\n'.join(tmp_headers), '\n', ": ")
        postData = '\r\n'.join(raws[index:])
        try:
            json.loads(postData)
            _json = postData
        except ValueError:
            post = postData
    else:
        tmp_headers = extract_dict('\n'.join(raws[1:]), '\n', ": ")
    netloc = "http" if not ssl else "https"
    host = tmp_headers.get("Host", None)
    if host is None:
        raise ValueError("Missing required 'Host' header in raw request")
    del tmp_headers["Host"]
    if 'Content-Length' in tmp_headers:
        del tmp_headers['Content-Length']
    url = "{0}://{1}".format(netloc, host + path)

    kwargs.setdefault('allow_redirects', True)
    kwargs.setdefault('data', post)
    kwargs.setdefault('headers', tmp_headers)
    kwargs.setdefault('json', _json)

    with requests_session() as session:
        return session.request(method=method, url=url, **kwargs)


requests.httpraw = httpraw


def is_private_ip(ip):
    """
    判断IP地址是否是内网IP，如果传入的不是有效IP则也会返回False
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except ValueError:
        return False


def is_internal_url(url):
    """
    判断URL是否是内网IP对应的URL
    """
    # 提取URL中的IP地址
    parsed_url = urlparse(url)
    netloc = parsed_url.netloc.split(':')[0]
    ip = netloc if netloc else parsed_url.hostname
    # 判断IP地址是否是内网IP
    return is_private_ip(ip)


def is_wildcard_dns(domain):
    """
    传入主域名
    判断域名是否有泛解析
    """
    import dns
    nonexistent_domain = rand_base(8) + '.' + domain
    try:
        answers = dns.resolver.resolve(nonexistent_domain, 'A')
        ip_list = [j for i in answers.response.answer for j in i.items]
        return True
    except Exception as e:
        return False


def is_valid_ip(ip: str) -> bool:
    """
    判断是否是有效的IP地址，支持IPv4Address、IPv6Address
    """
    try:
        ip_address = ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_wildcard_dns_batch(domain_list: iter, thread_num: int = 10, show_progress: bool = True) -> dict:
    """
    多线程批量判断域名是否泛解析
    传入域名或者URL列表、，支持解析成主域名
    """
    result = {}
    with ThreadPoolExecutor(max_workers=thread_num) as executor:

        future_map = {}
        for domain in domain_list:
            if domain.startswith(('http://', 'https://')):
                domain = urlparse(domain).hostname

            if is_valid_ip(domain):
                result[domain] = False
            else:
                main_domain = get_maindomain(domain)
                if main_domain not in result:
                    result[main_domain] = False
                    future_map[executor.submit(is_wildcard_dns, main_domain)] = main_domain

        if show_progress:
            with Progress() as progress:
                task_id = progress.add_task("[red]is_wildcard_dns_batch", total=len(future_map))
                for future in futures.as_completed(future_map):
                    result[future_map[future]] = future.result()
                    progress.update(task_id, advance=1)
        else:
            for future in futures.as_completed(future_map):
                result[future_map[future]] = future.result()

    return result


def get_maindomain(subdomain):
    # get the main domain from subdomain
    tld = tldextract.extract(subdomain)
    if tld.suffix != '':
        domain = f'{tld.domain}.{tld.suffix}'
    else:
        domain = tld.domain
    return domain


def url2ip(url, with_port=False):
    """
    works like turning 'http://baidu.com' => '180.149.132.47'
    """

    url_prased = urlparse(url)
    if url_prased.port:
        ret = gethostbyname(url_prased.hostname), url_prased.port
    elif not url_prased.port and url_prased.scheme == 'https':
        ret = gethostbyname(url_prased.hostname), 443
    else:
        ret = gethostbyname(url_prased.hostname), 80

    return ret if with_port else ret[0]


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def get_base_url(url: str) -> str | None:
    """
    从任意 URL 中提取 base URL（协议 + 域名）。
    
    参数:
        url (str): 输入的完整 URL 字符串
    
    返回:
        str | None: 提取出的 base URL（例如 https://example.com），若失败则返回 None
    
    异常:
        TypeError: 如果输入的 url 不是字符串类型
    """
    # 类型检查：确保输入是字符串
    if not isinstance(url, str):
        raise TypeError("URL 参数必须是字符串类型")

    try:
        # 解析 URL，分解为协议、域名、路径等部分
        parsed = urlparse(url)
        # 移除路径、查询参数和片段，仅保留协议和域名部分，然后重新生成 URL
        base_url = parsed._replace(path="", query="", fragment="").geturl()
        return base_url
    except Exception:
        # 如果 URL 无效或解析失败，返回 None（可根据需求改为抛出异常）
        return None


__all__ = [
    # --- 函数 ---
    'get_redirect_target',
    'patch_redirect',
    'remove_ssl_verify',
    'patch_getproxies',
    'is_private_ip',
    'is_internal_url',
    'is_wildcard_dns',
    'is_valid_ip',
    'is_wildcard_dns_batch',
    'get_maindomain',
    'url2ip',
    'is_port_in_use',
    'get_base_url',
    'httpraw',
    'requests_session',

    # --- 类 ---
    'EnhancedResponse',
    'RequestsSession',
    'BaseUrlSession',
    'CustomSslContextHttpAdapter',
    'ChunkedConfig',
    'ChunkedAdapter',
    'DESAdapter',
]
