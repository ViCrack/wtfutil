"""notifyutil 不产生通知请求的纯配置与格式处理测试。"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from wtfutil import notifyutil


class _FakeWebSocket:
    def __init__(self, queue) -> None:
        self.queue = list(queue)
        self.sent = []
        self.closed = False
        self.close_timeout = None

    def send(self, data) -> None:
        self.sent.append(json.loads(data))

    def recv(self):
        if not self.queue:
            raise notifyutil.websocket.WebSocketTimeoutException("timed out")
        return json.dumps(self.queue.pop(0), ensure_ascii=False)

    def settimeout(self, _timeout) -> None:
        return None

    def close(self, status=1000, reason=b"", timeout=3) -> None:
        self.closed = True
        self.close_timeout = timeout


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


class TestCmccNewmsg(unittest.TestCase):
    def setUp(self) -> None:
        for name, value in (
            ("_CMCC_AUTH_TIMEOUT", 1.0),
            ("_CMCC_INBOUND_WAIT", 0.0),
            ("_CMCC_ACK_WAIT", 1.0),
            ("_CMCC_CLOSE_TIMEOUT", 0.5),
        ):
            patcher = patch.object(notifyutil, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = ""
        notifyutil.push_config["CMCC_NEWMSG_TO"] = ""
        notifyutil.push_config["CMCC_NEWMSG_WS_URL"] = ""
        notifyutil._cmcc_last_to = ""
        notifyutil._cmcc_last_key = ""
        notifyutil._rebuild_notify_functions()

    def _send(self, fake: _FakeWebSocket):
        return patch.object(notifyutil.websocket, "create_connection", return_value=fake)

    def test_missing_key_raises(self) -> None:
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = ""
        with self.assertLogs("wtfutil.notifyutil", level="ERROR"):
            with self.assertRaises(ValueError):
                notifyutil.cmcc_newmsg("标题", "正文")

    def test_invalid_key_prefix_raises(self) -> None:
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "not-a-key"
        with self.assertLogs("wtfutil.notifyutil", level="ERROR"):
            with self.assertRaises(ValueError):
                notifyutil.cmcc_newmsg("标题", "正文")

    def test_channel_enabled_when_key_set(self) -> None:
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        notifyutil._rebuild_notify_functions()
        self.assertIn(notifyutil.cmcc_newmsg, notifyutil.notify_function)

    def test_invalid_key_does_not_enable_channel(self) -> None:
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "not-a-key"
        notifyutil._rebuild_notify_functions()
        self.assertNotIn(notifyutil.cmcc_newmsg, notifyutil.notify_function)

    def test_send_uses_inbound_from(self) -> None:
        fake = _FakeWebSocket([
            {"type": "connected", "message": "ok"},
            {"type": "text_message", "content": "hi", "from": "peer-from"},
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        notifyutil.push_config["CMCC_NEWMSG_TO"] = ""
        with self._send(fake) as mocked:
            notifyutil.cmcc_newmsg("", "hello")
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.args[0], notifyutil._CMCC_WS_URL)
        self.assertIn("X-API-Key: ak_example-key", mocked.call_args.kwargs["header"])
        sent = [item for item in fake.sent if item.get("type") == "send"][0]
        self.assertEqual(sent["to"], "peer-from")
        self.assertEqual(sent["content"], "hello")
        self.assertEqual(sent["apiKey"], "ak_example-key")
        self.assertEqual(notifyutil._cmcc_last_to, "peer-from")
        self.assertEqual(notifyutil._cmcc_last_key, "ak_example-key")
        self.assertTrue(fake.closed)
        self.assertEqual(fake.close_timeout, 0.5)

    def test_configured_to_beats_inbound(self) -> None:
        fake = _FakeWebSocket([
            {"type": "text_message", "content": "hi", "from": "peer-from"},
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        notifyutil.push_config["CMCC_NEWMSG_TO"] = "configured-to"
        with self._send(fake):
            notifyutil.cmcc_newmsg("告警", "磁盘满了")
        sent = [item for item in fake.sent if item.get("type") == "send"][0]
        self.assertEqual(sent["to"], "configured-to")
        self.assertEqual(sent["content"], "告警\n\n磁盘满了")

    def test_uses_cached_to_without_inbound(self) -> None:
        fake = _FakeWebSocket([
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        notifyutil._cmcc_last_to = "cached-peer"
        notifyutil._cmcc_last_key = "ak_example-key"
        with self._send(fake):
            notifyutil.cmcc_newmsg("", "hello")
        sent = [item for item in fake.sent if item.get("type") == "send"][0]
        self.assertEqual(sent["to"], "cached-peer")

    def test_cache_ignored_when_key_changes(self) -> None:
        fake = _FakeWebSocket([
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        notifyutil._cmcc_last_to = "cached-peer"
        notifyutil._cmcc_last_key = "ak_other-key"
        with self._send(fake):
            notifyutil.cmcc_newmsg("", "hello")
        sent = [item for item in fake.sent if item.get("type") == "send"][0]
        self.assertEqual(sent["to"], "ak_example-key")

    def test_falls_back_to_api_key(self) -> None:
        fake = _FakeWebSocket([
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        with self._send(fake):
            notifyutil.cmcc_newmsg("", "hello")
        sent = [item for item in fake.sent if item.get("type") == "send"][0]
        self.assertEqual(sent["to"], "ak_example-key")

    def test_ignores_phone_field(self) -> None:
        fake = _FakeWebSocket([
            {"type": "text_message", "content": "hi", "phone": "13800138000"},
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        with self._send(fake):
            notifyutil.cmcc_newmsg("", "hello")
        sent = [item for item in fake.sent if item.get("type") == "send"][0]
        self.assertEqual(sent["to"], "ak_example-key")
        self.assertEqual(notifyutil._cmcc_last_to, "")

    def test_custom_ws_url_and_auth_frame(self) -> None:
        fake = _FakeWebSocket([
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "send_ok"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "app_example-key"
        notifyutil.push_config["CMCC_NEWMSG_TO"] = "peer-from"
        notifyutil.push_config["CMCC_NEWMSG_WS_URL"] = "wss://example.test/ws"
        with self._send(fake) as mocked:
            notifyutil.cmcc_newmsg("", "hello")
        self.assertEqual(mocked.call_args.args[0], "wss://example.test/ws")
        self.assertEqual(fake.sent[0]["type"], "auth")
        self.assertEqual(fake.sent[0]["apiKey"], "app_example-key")
        self.assertEqual(fake.sent[0]["version"], "2.0")

    def test_auth_failed_raises(self) -> None:
        fake = _FakeWebSocket([{"type": "auth_failed", "message": "denied"}])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        with self._send(fake):
            with self.assertRaises(RuntimeError):
                notifyutil.cmcc_newmsg("标题", "正文")
        self.assertTrue(fake.closed)

    def test_send_error_ack_raises(self) -> None:
        fake = _FakeWebSocket([
            {"type": "auth_ok", "message": "认证成功"},
            {"type": "error", "message": "bad to"},
        ])
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = "ak_example-key"
        notifyutil.push_config["CMCC_NEWMSG_TO"] = "peer-from"
        with self._send(fake):
            with self.assertRaises(RuntimeError):
                notifyutil.cmcc_newmsg("标题", "正文")
        self.assertTrue(fake.closed)


class TestCmccNewmsgLive(unittest.TestCase):
    def tearDown(self) -> None:
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = ""
        notifyutil.push_config["CMCC_NEWMSG_TO"] = ""
        notifyutil.push_config["CMCC_NEWMSG_WS_URL"] = ""
        notifyutil._cmcc_last_to = ""
        notifyutil._cmcc_last_key = ""
        notifyutil._rebuild_notify_functions()

    @unittest.skipUnless(
        os.getenv("CMCC_NEWMSG_RUN_LIVE") == "1",
        "set CMCC_NEWMSG_RUN_LIVE=1 and CMCC_NEWMSG_KEY to hit China Mobile MaaP",
    )
    def test_live_send_skipped_by_default(self) -> None:
        key = os.getenv("CMCC_NEWMSG_KEY", "").strip()
        if not notifyutil._cmcc_key_enabled(key):
            self.skipTest("CMCC_NEWMSG_KEY with ak_/app_ prefix required for live send")
        notifyutil.push_config["CMCC_NEWMSG_KEY"] = key
        notifyutil.push_config["CMCC_NEWMSG_TO"] = os.getenv("CMCC_NEWMSG_TO", "").strip()
        notifyutil.push_config["CMCC_NEWMSG_WS_URL"] = os.getenv("CMCC_NEWMSG_WS_URL", "").strip()
        notifyutil.cmcc_newmsg("wtfutil live", "ignore")


if __name__ == "__main__":
    unittest.main()
