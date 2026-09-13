"""httputil 安全默认值和分块适配器回归测试。"""

from __future__ import annotations

import functools
import io
import ssl
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import requests
import urllib3

from wtfutil import httputil


class TestRequestsSession(unittest.TestCase):
    def test_import_tls_side_effect_is_verified_in_isolated_process(self) -> None:
        project_directory = Path(__file__).resolve().parents[1]
        script = (
            "import ssl; "
            "import wtfutil.httputil; "
            "assert ssl._create_default_https_context is ssl._create_unverified_context"
        )
        completed_process = subprocess.run(
            [sys.executable, "-c", script],
            cwd=project_directory,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(
            completed_process.returncode,
            0,
            completed_process.stderr,
        )

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

    def test_json_decode_error_includes_preview_without_printing(self) -> None:
        session_options = (
            {},
            {"use_cache": {"backend": "memory"}},
        )
        for options in session_options:
            with self.subTest(options=options):
                with httputil.requests_session(user_agent="test-agent", **options) as session:
                    response = requests.Response()
                    response.status_code = 502
                    response.url = "https://example.test/api"
                    response._content = b"<html>not-json</html>"
                    response.encoding = "utf-8"
                    for hook in session.hooks.get("response", []):
                        hook(response)

                    self.assertIs(type(response), requests.Response)
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with (
                        mock.patch("sys.stdout", stdout),
                        mock.patch("sys.stderr", stderr),
                        self.assertRaises(requests.exceptions.JSONDecodeError) as ctx,
                    ):
                        response.json()

                    message = str(ctx.exception)
                    self.assertIn("https://example.test/api", message)
                    self.assertIn("502", message)
                    self.assertIn("<html>not-json</html>", message)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertEqual(stderr.getvalue(), "")

    def test_default_timeout_is_applied_and_can_be_overridden(self) -> None:
        captured: dict[str, object] = {}

        def fake_request(self, method, url, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            response = requests.Response()
            response.status_code = 200
            response._content = b""
            return response

        session_options = (
            {},
            {"base_url": "https://example.test"},
        )
        for options in session_options:
            with self.subTest(options=options):
                with httputil.requests_session(
                    user_agent="test-agent",
                    timeout=7,
                    **options,
                ) as session:
                    self.assertNotIsInstance(session.request, functools.partial)
                    with mock.patch("requests.sessions.Session.request", fake_request):
                        session.request("GET", "https://example.test/")
                        self.assertEqual(captured["timeout"], 7)
                        session.request("GET", "https://example.test/", timeout=3)
                        self.assertEqual(captured["timeout"], 3)

        with httputil.requests_session(
            user_agent="test-agent",
            timeout=7,
            use_cache={"backend": "memory"},
        ) as cached_session:
            self.assertNotIsInstance(cached_session.request, functools.partial)

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

    def test_fixed_user_agent_does_not_initialize_generator(self) -> None:
        with (
            mock.patch.object(httputil, "UserAgent") as user_agent_factory,
            httputil.requests_session(user_agent="fixed-agent") as session,
        ):
            self.assertEqual(session.headers["User-Agent"], "fixed-agent")

        user_agent_factory.assert_not_called()

    def test_cache_rejects_enhancements_it_cannot_apply(self) -> None:
        incompatible_options = (
            {"base_url": "https://example.test"},
            {"debug": True},
            {"rate_limit": 1},
        )
        for incompatible_option in incompatible_options:
            with self.subTest(incompatible_option=incompatible_option), self.assertRaises(ValueError):
                httputil.requests_session(
                    use_cache=True,
                    user_agent="test-agent",
                    **incompatible_option,
                )

    def test_proxy_manager_receives_legacy_tls_context(self) -> None:
        adapter = httputil.CustomSslContextHttpAdapter()
        with mock.patch.object(
            httputil.HTTPAdapter,
            "proxy_manager_for",
            return_value=mock.sentinel.proxy_manager,
        ) as parent_proxy_manager:
            result = adapter.proxy_manager_for("http://127.0.0.1:8080")

        self.assertIs(result, mock.sentinel.proxy_manager)
        ssl_context = parent_proxy_manager.call_args.kwargs["ssl_context"]
        self.assertIsInstance(ssl_context, ssl.SSLContext)
        self.assertFalse(ssl_context.check_hostname)
        self.assertTrue(
            ssl_context.options
            & getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
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
        ), self.assertRaises(requests.RequestException):
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

    def test_text_body_that_looks_like_json_remains_text(self) -> None:
        session = mock.MagicMock()
        session.request.return_value = requests.Response()
        session_context = mock.MagicMock()
        session_context.__enter__.return_value = session
        raw_request = (
            "POST /api HTTP/1.1\r\n"
            "Host: example.test\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "123"
        )

        with mock.patch.object(httputil, "requests_session", return_value=session_context):
            httputil.httpraw(raw_request)

        request_kwargs = session.request.call_args.kwargs
        self.assertEqual(request_kwargs["data"], "123")
        self.assertIsNone(request_kwargs["json"])

    def test_delete_body_is_preserved(self) -> None:
        session = mock.MagicMock()
        session.request.return_value = requests.Response()
        session_context = mock.MagicMock()
        session_context.__enter__.return_value = session
        raw_request = "DELETE /item HTTP/1.1\r\nHost: example.test\r\n\r\npayload"

        with mock.patch.object(httputil, "requests_session", return_value=session_context):
            httputil.httpraw(raw_request)

        self.assertEqual(session.request.call_args.kwargs["data"], "payload")


class TestHttpDebug(unittest.TestCase):
    def _debug_session(self):
        return httputil.requests_session(debug=True, user_agent="test-agent")

    def test_debug_prints_request_before_successful_response(self) -> None:
        response = requests.Response()
        response.status_code = 200
        response.reason = "OK"
        response.headers["Content-Type"] = "text/plain"
        response._content = b"hello"
        response.url = "https://example.test/ping"

        class FakeAdapter(httputil.HTTPAdapter):
            def send(self, request, **kwargs):
                response.request = request
                return response

        with self._debug_session() as session:
            session.mount("https://", FakeAdapter())
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                session.post("https://example.test/ping", data="payload=1")

        text = stdout.getvalue()
        self.assertIn("HTTP Request:", text)
        self.assertIn("HTTP Response:", text)
        self.assertLess(text.index("HTTP Request:"), text.index("HTTP Response:"))
        self.assertIn("POST /ping HTTP/1.1", text)
        self.assertIn("payload=1", text)
        self.assertIn("hello", text)
        self.assertNotIn("HTTP Request failed:", text)

    def test_debug_prints_request_when_send_fails(self) -> None:
        class FakeAdapter(httputil.HTTPAdapter):
            def send(self, request, **kwargs):
                raise requests.ConnectionError("simulated-offline", request=request)

        with self._debug_session() as session:
            session.mount("https://", FakeAdapter())
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                with self.assertRaises(requests.ConnectionError):
                    session.post("https://example.test/ping", data="payload=1")

        text = stdout.getvalue()
        self.assertIn("HTTP Request:", text)
        self.assertIn("POST /ping HTTP/1.1", text)
        self.assertIn("payload=1", text)
        self.assertIn("HTTP Request failed: ConnectionError", text)
        self.assertIn("simulated-offline", text)
        self.assertNotIn("HTTP Response:", text)

    def test_debug_prints_response_when_exception_has_one(self) -> None:
        failed = requests.Response()
        failed.status_code = 502
        failed.reason = "Bad Gateway"
        failed._content = b"upstream-down"

        class FakeAdapter(httputil.HTTPAdapter):
            def send(self, request, **kwargs):
                failed.request = request
                exc = requests.exceptions.ChunkedEncodingError("truncated")
                exc.response = failed
                raise exc

        with self._debug_session() as session:
            session.mount("https://", FakeAdapter())
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                with self.assertRaises(requests.exceptions.ChunkedEncodingError):
                    session.get("https://example.test/ping")

        text = stdout.getvalue()
        self.assertIn("HTTP Request:", text)
        self.assertIn("HTTP Request failed: ChunkedEncodingError", text)
        self.assertIn("HTTP Response:", text)
        self.assertIn("502", text)
        self.assertIn("upstream-down", text)

    def test_debug_off_prints_nothing_on_failure(self) -> None:
        class FakeAdapter(httputil.HTTPAdapter):
            def send(self, request, **kwargs):
                raise requests.ConnectionError("simulated-offline", request=request)

        with httputil.requests_session(user_agent="test-agent") as session:
            session.mount("https://", FakeAdapter())
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                with self.assertRaises(requests.ConnectionError):
                    session.get("https://example.test/ping")

        self.assertEqual(stdout.getvalue(), "")


class TestUrlHelpers(unittest.TestCase):
    def test_url2ip_accepts_bare_hostname_and_explicit_port(self) -> None:
        with mock.patch.object(httputil, "gethostbyname", return_value="203.0.113.10") as resolver:
            self.assertEqual(httputil.url2ip("example.com"), "203.0.113.10")
            self.assertEqual(
                httputil.url2ip("example.com:8080", with_port=True),
                ("203.0.113.10", 8080),
            )

        self.assertEqual(resolver.call_args_list, [mock.call("example.com"), mock.call("example.com")])

    def test_get_base_url_rejects_text_without_scheme_and_host(self) -> None:
        self.assertIsNone(httputil.get_base_url("not a url"))
        self.assertEqual(
            httputil.get_base_url("https://example.test/path?q=1#fragment"),
            "https://example.test",
        )

    def test_query_and_fragment_references_replace_existing_components(self) -> None:
        base_url = "https://example.test/path?old=1#old"
        self.assertEqual(
            httputil.build_absolute_url(base_url, "?new=2"),
            "https://example.test/path?new=2",
        )
        self.assertEqual(
            httputil.build_absolute_url(base_url, "#new"),
            "https://example.test/path?old=1#new",
        )


if __name__ == "__main__":
    unittest.main()
