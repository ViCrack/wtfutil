"""notifyutil 不产生通知请求的纯配置与格式处理测试。"""

from __future__ import annotations

import unittest

from wtfutil import notifyutil


class TestNotifyConfiguration(unittest.TestCase):
    def test_false_text_disables_boolean_flags(self) -> None:
        self.assertFalse(notifyutil._config_flag_enabled("false"))
        self.assertFalse(notifyutil._config_flag_enabled("0"))
        self.assertTrue(notifyutil._config_flag_enabled("yes"))

    def test_custom_content_accepts_content_only_placeholder(self) -> None:
        formatted_url, formatted_body = notifyutil.format_notify_content(
            "https://example.test/hook",
            "message: $content",
            "title",
            "body",
        )
        self.assertEqual(formatted_url, "https://example.test/hook")
        self.assertEqual(formatted_body, "message: body")


if __name__ == "__main__":
    unittest.main()
