"""translateutil 响应解析和会话生命周期测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from wtfutil.translateutil import BaiduTranslateApi, BaiduTranslateError


def _call_translate_without_rate_limit(
    client: BaiduTranslateApi,
    query: str,
) -> str:
    wrapped_function = BaiduTranslateApi.translate
    while hasattr(wrapped_function, "__wrapped__"):
        wrapped_function = wrapped_function.__wrapped__
    return wrapped_function(client, query)


class TestBaiduTranslateApi(unittest.TestCase):
    def test_success_response(self) -> None:
        response = mock.Mock()
        response.json.return_value = {
            "trans_result": [{"src": "你好", "dst": "hello"}]
        }
        session = mock.Mock()
        session.post.return_value = response
        client = BaiduTranslateApi("appid", "appkey", session=session)

        self.assertEqual(
            _call_translate_without_rate_limit(client, "你好"),
            "hello",
        )
        response.raise_for_status.assert_called_once_with()

    def test_request_uses_configured_timeout_and_expected_signature(self) -> None:
        response = mock.Mock()
        response.json.return_value = {"trans_result": [{"dst": "hello"}]}
        session = mock.Mock()
        session.post.return_value = response
        client = BaiduTranslateApi(
            "appid",
            "appkey",
            from_lang="auto",
            to_lang="en",
            timeout=12,
            session=session,
        )

        with mock.patch("wtfutil.translateutil.random.randint", return_value=32768):
            translated_text = _call_translate_without_rate_limit(client, "你好")

        self.assertEqual(translated_text, "hello")
        request_kwargs = session.post.call_args.kwargs
        self.assertEqual(request_kwargs["timeout"], 12)
        self.assertEqual(
            request_kwargs["data"],
            {
                "appid": "appid",
                "q": "你好",
                "from": "auto",
                "to": "en",
                "salt": 32768,
                "sign": "6db7e85c14a86ee99d2099af67b8312e",
            },
        )

    def test_api_error_uses_domain_exception(self) -> None:
        response = mock.Mock()
        response.json.return_value = {
            "error_code": "54003",
            "error_msg": "Invalid Access Limit",
        }
        session = mock.Mock()
        session.post.return_value = response
        client = BaiduTranslateApi("appid", "appkey", session=session)

        with self.assertRaisesRegex(BaiduTranslateError, "54003"):
            _call_translate_without_rate_limit(client, "你好")

    def test_invalid_json_uses_domain_exception(self) -> None:
        response = mock.Mock()
        response.json.side_effect = ValueError("invalid JSON")
        session = mock.Mock()
        session.post.return_value = response
        client = BaiduTranslateApi("appid", "appkey", session=session)

        with self.assertRaisesRegex(BaiduTranslateError, "无法解析"):
            _call_translate_without_rate_limit(client, "你好")

    def test_external_session_is_not_closed(self) -> None:
        session = mock.Mock()
        client = BaiduTranslateApi("appid", "appkey", session=session)
        client.close()
        session.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
