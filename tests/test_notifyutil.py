"""notifyutil 配置开关、并发和格式处理测试。"""

from __future__ import annotations

import threading
import unittest
from unittest import mock

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


class TestNotificationDispatch(unittest.TestCase):
    def tearDown(self) -> None:
        notifyutil._close_thread_request_session()

    def test_each_thread_owns_and_closes_its_session(self) -> None:
        created_sessions: list[mock.Mock] = []

        def create_session(**kwargs):
            session = mock.Mock()
            created_sessions.append(session)
            return session

        thread_sessions: list[object] = []

        def channel(title: str, content: str) -> None:
            thread_sessions.append(notifyutil._get_req())

        with mock.patch.object(
            notifyutil,
            "requests_session",
            side_effect=create_session,
        ):
            threads = [
                threading.Thread(
                    target=notifyutil._dispatch_notification,
                    args=(channel, "title", "content"),
                )
                for _ in range(2)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(len(created_sessions), 2)
        self.assertIsNot(thread_sessions[0], thread_sessions[1])
        for session in created_sessions:
            session.close.assert_called_once_with()

    def test_hitokoto_session_is_closed_on_main_thread(self) -> None:
        session = mock.Mock()
        session.get.return_value.json.return_value = {
            "hitokoto": "hello",
            "from": "test",
        }

        with (
            mock.patch.object(
                notifyutil,
                "requests_session",
                return_value=session,
            ),
            mock.patch.object(
                notifyutil,
                "_ensure_push_config",
                return_value=False,
            ),
            mock.patch.object(notifyutil, "notify_function", []),
            mock.patch.dict(
                notifyutil.push_config,
                {"HITOKOTO": True},
                clear=False,
            ),
        ):
            notifyutil.send("title", "content")

        session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
