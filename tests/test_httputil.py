"""httputil 安全默认值和分块适配器回归测试。"""

from __future__ import annotations

import ssl
import unittest
from types import SimpleNamespace
from unittest import mock

import requests
import urllib3

from wtfutil import httputil


class TestRequestsSession(unittest.TestCase):
    def test_import_disables_global_tls_verification(self) -> None:
        self.assertIs(
            ssl._create_default_https_context,
            ssl._create_unverified_context,
        )

    def test_tls_verification_is_disabled_by_default(self) -> None:
        with httputil.requests_session(user_agent="test-agent") as session:
            self.assertIs(session.verify, False)

        with httputil.requests_session(
            user_agent="test-agent",
            verify=True,
        ) as verified_session:
            self.assertIs(verified_session.verify, True)

    def test_chunked_session_does_not_patch_global_connections(self) -> None:
        original_request = urllib3.connection.HTTPConnection.request
        original_send = urllib3.connection.HTTPConnection.send

        with httputil.requests_session(
            chunked=True,
            user_agent="test-agent",
        ) as session:
            adapter = session.get_adapter("http://")
            self.assertIsInstance(adapter, httputil.ChunkedAdapter)

        self.assertIs(urllib3.connection.HTTPConnection.request, original_request)
        self.assertIs(urllib3.connection.HTTPConnection.send, original_send)

    def test_chunked_https_pool_keeps_legacy_tls_context(self) -> None:
        with httputil.requests_session(
            chunked=True,
            user_agent="test-agent",
        ) as session:
            adapter = session.get_adapter("https://")
            pool_class = adapter.poolmanager.pool_classes_by_scheme["https"]

            self.assertTrue(
                issubclass(
                    pool_class.ConnectionCls,
                    httputil._LegacyTlsConnectionMixin,
                )
            )
            self.assertEqual(
                pool_class.ConnectionCls.__mro__[1],
                httputil._ChunkedConnectionMixin,
            )


class TestChunkedAdapter(unittest.TestCase):
    def test_pool_configuration_preserves_proxy_pool_inheritance(self) -> None:
        class ProxyConnection(urllib3.connection.HTTPConnection):
            pass

        class ProxyConnectionPool(
            urllib3.connectionpool.HTTPConnectionPool
        ):
            ConnectionCls = ProxyConnection

        pool_manager = SimpleNamespace(
            pool_classes_by_scheme={"http": ProxyConnectionPool}
        )

        httputil.ChunkedAdapter._configure_pool_classes(pool_manager)

        chunked_pool_class = pool_manager.pool_classes_by_scheme["http"]
        self.assertTrue(issubclass(chunked_pool_class, ProxyConnectionPool))
        self.assertTrue(
            issubclass(chunked_pool_class.ConnectionCls, ProxyConnection)
        )
        self.assertTrue(
            issubclass(
                chunked_pool_class.ConnectionCls,
                httputil._ChunkedConnectionMixin,
            )
        )

    def test_real_socks_proxy_pool_keeps_socks_connection_classes(self) -> None:
        try:
            from urllib3.contrib.socks import (
                SOCKSConnection,
                SOCKSHTTPSConnection,
            )
        except ImportError:
            self.skipTest("安装 PySocks 后运行 SOCKS 回归测试")

        adapter = httputil.ChunkedAdapter()
        proxy_manager = adapter.proxy_manager_for(
            "socks5h://127.0.0.1:1080"
        )

        http_pool = proxy_manager.pool_classes_by_scheme["http"]
        https_pool = proxy_manager.pool_classes_by_scheme["https"]
        self.assertTrue(issubclass(http_pool.ConnectionCls, SOCKSConnection))
        self.assertTrue(
            issubclass(http_pool.ConnectionCls, httputil._ChunkedConnectionMixin)
        )
        self.assertTrue(
            issubclass(https_pool.ConnectionCls, SOCKSHTTPSConnection)
        )
        self.assertTrue(
            issubclass(
                https_pool.ConnectionCls,
                httputil._LegacyTlsConnectionMixin,
            )
        )
        adapter.close()

    def test_empty_body_does_not_delete_missing_context(self) -> None:
        adapter = httputil.ChunkedAdapter()
        request = requests.Request("GET", "http://example.test").prepare()

        with mock.patch.object(
            requests.adapters.HTTPAdapter,
            "send",
            return_value=requests.Response(),
        ):
            adapter.send(request)

    def test_context_is_cleaned_when_send_fails(self) -> None:
        adapter = httputil.ChunkedAdapter()
        request = requests.Request(
            "POST",
            "http://example.test",
            data=b"payload",
        ).prepare()

        with mock.patch.object(
            requests.adapters.HTTPAdapter,
            "send",
            side_effect=requests.RequestException("boom"),
        ):
            with self.assertRaises(requests.RequestException):
                adapter.send(request)

        self.assertFalse(hasattr(httputil._http_context, "chunked_config"))


class TestHttpRaw(unittest.TestCase):
    def test_json_body_is_not_encoded_twice(self) -> None:
        session = mock.MagicMock()
        session.request.return_value = requests.Response()
        session_context = mock.MagicMock()
        session_context.__enter__.return_value = session

        raw_request = (
            "POST /api HTTP/1.1\r\n"
            "Host: example.test\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            '{"message": " value "}'
        )
        with mock.patch.object(
            httputil,
            "requests_session",
            return_value=session_context,
        ):
            httputil.httpraw(raw_request)

        request_kwargs = session.request.call_args.kwargs
        self.assertEqual(request_kwargs["json"], {"message": " value "})
        self.assertIsNone(request_kwargs["data"])

    def test_internal_url_supports_ipv6(self) -> None:
        self.assertTrue(httputil.is_internal_url("http://[::1]/status"))


if __name__ == "__main__":
    unittest.main()
