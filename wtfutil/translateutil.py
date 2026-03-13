"""
翻译api
"""

import random

from ratelimit import limits, sleep_and_retry

from . import util


class BaiduTranslateApi:

    def __init__(self, appid: str, appkey: str, from_lang: str = 'zh', to_lang: str = 'en') -> None:
        self.appid = appid
        self.appkey = appkey
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.req = util.requests_session()

    @limits(calls=1, period=1)  # 每秒钟最多只能调用 1 次
    @sleep_and_retry  # 如果超过调用限制，则等待剩余时间后重试
    def translate(
        self,
        query: str,
        from_lang: str | None = None,
        to_lang: str | None = None,
    ) -> str:
        from_lang = from_lang or self.from_lang
        to_lang = to_lang or self.to_lang

        salt = random.randint(32768, 65536)
        sign = util.str_md5(self.appid + query + str(salt) + self.appkey)

        data = {'appid': self.appid, 'q': query, 'from': from_lang, 'to': to_lang, 'salt': salt, 'sign': sign}
        result = self.req.post('http://api.fanyi.baidu.com/api/trans/vip/translate', data=data).json()
        return result['trans_result'][0]['dst']


__all__ = [
    'BaiduTranslateApi'
]
