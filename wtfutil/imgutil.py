"""
随机图片/头像拉取（多源回退）
"""

import logging
import os
import random
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

from configobj import ConfigObj
from requests import Response

from .httputil import RequestsSession, requests_session

logger = logging.getLogger(__name__)

_MIN_IMAGE_BYTES = 256

_APIHZ_URL = "https://cn.apihz.cn/api/img/apihzimgtx.php"

# 直接返回图片或 302 跳转到图片（requests 自动跟随重定向）
_DIRECT_AVATAR_SOURCES: List[Tuple[str, str]] = [
    ("loliapi", "https://www.loliapi.com/acg/pp/"),
    ("dmoe", "https://www.dmoe.cc/random.php"),
    ("xjh", "https://img.xjh.me/random_img.php?return=302&ctype=acg"),
    ("btstu", "https://api.btstu.cn/sjbz/api.php?lx=dongman"),
    ("horosama", "https://api.horosama.com/random.php?type=mobile"),
]

img_config = {
    "APIHZ_IMG_ID": "",
    "APIHZ_IMG_KEY": "",
    "APIHZ_IMGTYPE": "5",
    "APIHZ_IMG_TYPE": "1",
}

_config_loaded = False


def _load_img_config() -> None:
    global _config_loaded
    if _config_loaded:
        return
    from . import util

    config_path = util.get_resource("wtfconfig.ini")
    if config_path and Path(config_path).exists():
        cfg = ConfigObj(config_path, encoding="UTF-8")
        if "img" in cfg:
            for key, value in cfg["img"].items():
                img_config[key.upper()] = str(value)

    for k in list(img_config):
        if os.getenv(k):
            img_config[k] = os.getenv(k)
    _config_loaded = True


class ImageFetchError(Exception):
    """所有图片源均拉取失败时抛出。"""

    def __init__(self, errors: List[Tuple[str, Exception]]) -> None:
        self.errors = errors
        detail = "; ".join(f"{name}: {exc}" for name, exc in errors)
        super().__init__(f"all image providers failed: {detail}")


def _validate_image_bytes(resp: Response) -> bytes:
    if resp.status_code != 200:
        raise ValueError(f"HTTP {resp.status_code}")
    data = resp.content
    if len(data) < _MIN_IMAGE_BYTES:
        raise ValueError(f"response too small ({len(data)} bytes)")
    return data


def _fetch_direct(session: RequestsSession, url: str) -> bytes:
    return _validate_image_bytes(session.get(url, allow_redirects=True))


def _direct_fetcher(url: str) -> Callable[[RequestsSession], bytes]:
    def _fetch(session: RequestsSession) -> bytes:
        return _fetch_direct(session, url)

    return _fetch


def _fetch_apihz(session: RequestsSession) -> bytes:
    img_id = img_config.get("APIHZ_IMG_ID", "").strip()
    img_key = img_config.get("APIHZ_IMG_KEY", "").strip()
    if not img_id or not img_key:
        raise ValueError("APIHZ_IMG_ID or APIHZ_IMG_KEY not configured")

    params = {
        "id": img_id,
        "key": img_key,
        "imgtype": img_config.get("APIHZ_IMGTYPE", "5"),
        "type": img_config.get("APIHZ_IMG_TYPE", "1"),
    }
    resp = session.get(_APIHZ_URL, params=params)
    if resp.status_code != 200:
        raise ValueError(f"apihz API HTTP {resp.status_code}")
    body = resp.json()
    if body.get("code") != 200:
        raise ValueError(f"apihz API code={body.get('code')}")
    img_url = body.get("msg")
    if not img_url:
        raise ValueError("apihz API missing msg url")
    return _fetch_direct(session, img_url)


def _avatar_providers() -> List[Tuple[str, Callable[[RequestsSession], bytes]]]:
    _load_img_config()
    providers: List[Tuple[str, Callable[[RequestsSession], bytes]]] = [
        (name, _direct_fetcher(url)) for name, url in _DIRECT_AVATAR_SOURCES
    ]
    if img_config.get("APIHZ_IMG_ID", "").strip() and img_config.get("APIHZ_IMG_KEY", "").strip():
        providers.append(("apihz", _fetch_apihz))
    return providers


def fetch_random_bytes(
    fetchers: Iterable[Callable[[RequestsSession], bytes]],
    session: RequestsSession | None = None,
    timeout: float = 30,
    shuffle: bool = True,
) -> bytes:
    """
    按顺序尝试多个 fetcher，返回第一个成功的图片字节。

    Args:
        fetchers: 接收 session、返回 bytes 的可调用对象序列。
        session: 可选，自定义 requests session。
        timeout: 未传 session 时用于创建 session 的超时（秒）。
        shuffle: 是否在尝试前随机打乱 fetcher 顺序。
    """
    fetcher_list = list(fetchers)
    if not fetcher_list:
        raise ImageFetchError([])

    if shuffle:
        random.shuffle(fetcher_list)

    owns_session = session is None
    if owns_session:
        session = requests_session(timeout=timeout)

    errors: List[Tuple[str, Exception]] = []
    try:
        for i, fetcher in enumerate(fetcher_list):
            name = getattr(fetcher, "__name__", f"fetcher_{i}")
            try:
                return fetcher(session)
            except Exception as exc:
                logger.debug("image fetcher %s failed: %s", name, exc)
                errors.append((name, exc))
    finally:
        if owns_session and session is not None:
            session.close()

    raise ImageFetchError(errors)


def random_avatar_bytes(
    session: RequestsSession | None = None,
    timeout: float = 30,
) -> bytes:
    """
    从内置头像源中随机打乱顺序依次尝试，返回第一张有效图片的原始字节。

    内置直链/302 源：loliapi、dmoe、xjh、btstu、horosama；
    若配置了 APIHZ_IMG_ID / APIHZ_IMG_KEY 则另含 apihz（JSON 取 URL 再下载）。
    配置见 wtfconfig.ini [img] 段或同名环境变量。
    """
    providers = _avatar_providers()
    if not providers:
        raise ImageFetchError([("config", ValueError("no avatar providers available"))])

    random.shuffle(providers)
    owns_session = session is None
    if owns_session:
        session = requests_session(timeout=timeout)

    errors: List[Tuple[str, Exception]] = []
    try:
        for name, fetcher in providers:
            try:
                return fetcher(session)
            except Exception as exc:
                logger.debug("avatar provider %s failed: %s", name, exc)
                errors.append((name, exc))
    finally:
        if owns_session and session is not None:
            session.close()

    raise ImageFetchError(errors)


__all__ = [
    "img_config",
    "ImageFetchError",
    "fetch_random_bytes",
    "random_avatar_bytes",
]
