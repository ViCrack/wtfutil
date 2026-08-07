"""百度翻译 API 客户端。"""

import random

from ratelimit import limits, sleep_and_retry
from requests import Session

from .httputil import requests_session
from .strutil import str_md5


class BaiduTranslateError(RuntimeError):
    """百度翻译接口返回错误或无效响应时抛出。"""


class BaiduTranslateApi:
    """使用百度通用翻译 API 翻译文本。"""

    def __init__(
        self,
        appid: str,
        appkey: str,
        from_lang: str = "zh",
        to_lang: str = "en",
        *,
        timeout: float = 30,
        session: Session | None = None,
    ) -> None:
        self.appid = appid
        self.appkey = appkey
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.timeout = timeout
        self.req = session or requests_session(timeout=timeout)
        self._owns_session = session is None

    @sleep_and_retry
    @limits(calls=1, period=1)
    def translate(
        self,
        query: str,
        from_lang: str | None = None,
        to_lang: str | None = None,
    ) -> str:
        from_lang = from_lang or self.from_lang
        to_lang = to_lang or self.to_lang

        salt = random.randint(32768, 65536)
        sign = str_md5(self.appid + query + str(salt) + self.appkey)

        data = {
            "appid": self.appid,
            "q": query,
            "from": from_lang,
            "to": to_lang,
            "salt": salt,
            "sign": sign,
        }
        response = self.req.post(
            "https://api.fanyi.baidu.com/api/trans/vip/translate",
            data=data,
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError as exc:
            raise BaiduTranslateError(
                "百度翻译接口返回了无法解析的 JSON"
            ) from exc

        if not isinstance(result, dict):
            raise BaiduTranslateError("百度翻译接口返回了无效 JSON 结构")
        if result.get("error_code"):
            error_code = result.get("error_code")
            error_message = result.get("error_msg") or "未知错误"
            raise BaiduTranslateError(
                f"百度翻译失败：{error_code} {error_message}"
            )

        translations = result.get("trans_result")
        if not isinstance(translations, list) or not translations:
            raise BaiduTranslateError("百度翻译接口未返回翻译结果")
        first_translation = translations[0]
        if not isinstance(first_translation, dict):
            raise BaiduTranslateError("百度翻译结果结构无效")
        translated_text = first_translation.get("dst")
        if not isinstance(translated_text, str):
            raise BaiduTranslateError("百度翻译结果缺少 dst 字段")
        return translated_text

    def close(self) -> None:
        """关闭客户端自行创建的 HTTP 会话。"""
        if self._owns_session:
            self.req.close()

    def __enter__(self) -> "BaiduTranslateApi":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


__all__ = [
    "BaiduTranslateApi",
    "BaiduTranslateError",
]
