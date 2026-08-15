"""memshellutil / memshell CLI 测试。

默认只运行 mock 单测。设置 ``MEMSHELL_RUN_LIVE=1`` 后才运行访问
``https://party.mem.mk`` 的联调用例。
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest import mock

from requests.exceptions import ConnectionError as RequestsConnectionError

from wtfutil.httputil import EnhancedResponse
from wtfutil.memshell import main as memshell_main
from wtfutil.memshellutil import (
    DEFAULT_BASE_URL,
    MemShellGenerateResult,
    MemShellParty,
    MemShellPartyError,
    ProbeContent,
    ProbeGenerateResult,
    ProbeMethod,
    Server,
    _build_connect_retry,
    build_generate_body,
    build_probe_body,
    extract_generate_meta,
    extract_probe_meta,
    resolve_shell_credentials,
)

_RUN_LIVE = os.getenv("MEMSHELL_RUN_LIVE", "").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _as_generate_result(data: dict) -> MemShellGenerateResult:
    meta = extract_generate_meta(data)
    return MemShellGenerateResult(
        pack_result=data.get("packResult"),
        all_pack_results=data.get("allPackResults"),
        shell_class_name=meta["shellClassName"],
        injector_class_name=meta["injectorClassName"],
        shell_size=meta["shellSize"],
        injector_size=meta["injectorSize"],
        shell_config=meta["shellConfig"],
        shell_tool_config=meta["shellToolConfig"],
        injector_config=meta["injectorConfig"],
    )


def _as_probe_result(data: dict) -> ProbeGenerateResult:
    meta = extract_probe_meta(data)
    return ProbeGenerateResult(
        pack_result=data.get("packResult"),
        all_pack_results=data.get("allPackResults"),
        shell_class_name=meta["shellClassName"],
        shell_size=meta["shellSize"],
        probe_config=meta["probeConfig"],
        probe_content_config=meta["probeContentConfig"],
    )


def _fake_resp(data, status_code: int = 200):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = json.dumps(data) if not isinstance(data, str) else data
    return resp


class TestResolveShellCredentials(unittest.TestCase):
    def test_pass_maps_behinder(self):
        c = resolve_shell_credentials("Behinder", password="example-pass")
        self.assertEqual(c["behinder_pass"], "example-pass")
        self.assertEqual(c["godzilla_pass"], "")
        self.assertEqual(c["ant_sword_pass"], "")

    def test_pass_maps_case_insensitive(self):
        c = resolve_shell_credentials("behinder", password="example-pass")
        self.assertEqual(c["behinder_pass"], "example-pass")
        c2 = resolve_shell_credentials("GODZILLA", password="example-pass", key="example-key")
        self.assertEqual(c2["godzilla_pass"], "example-pass")
        self.assertEqual(c2["godzilla_key"], "example-key")

    def test_pass_maps_godzilla_with_key(self):
        c = resolve_shell_credentials("Godzilla", password="example-pass", key="example-key")
        self.assertEqual(c["godzilla_pass"], "example-pass")
        self.assertEqual(c["godzilla_key"], "example-key")
        self.assertEqual(c["behinder_pass"], "")

    def test_pass_maps_antsword(self):
        c = resolve_shell_credentials("AntSword", password="example-pass")
        self.assertEqual(c["ant_sword_pass"], "example-pass")

    def test_specific_overrides_generic(self):
        c = resolve_shell_credentials(
            "Behinder",
            password="example-generic-pass",
            behinder_pass="example-specific-pass",
        )
        self.assertEqual(c["behinder_pass"], "example-specific-pass")

    def test_build_body_password_convenience(self):
        body = build_generate_body(shell_tool="Behinder", password="example-pass")
        self.assertEqual(body["shellToolConfig"]["behinderPass"], "example-pass")
        body2 = build_generate_body(shell_tool="Godzilla", password="example-pass", key="example-key")
        self.assertEqual(body2["shellToolConfig"]["godzillaPass"], "example-pass")
        self.assertEqual(body2["shellToolConfig"]["godzillaKey"], "example-key")


class TestBuildGenerateBody(unittest.TestCase):
    def test_defaults_behinder(self):
        body = build_generate_body()
        self.assertEqual(body["shellConfig"]["server"], "Tomcat")
        self.assertEqual(body["shellConfig"]["shellTool"], "Behinder")
        self.assertEqual(body["shellConfig"]["shellType"], "Listener")
        self.assertEqual(body["shellConfig"]["serverVersion"], "unknown")
        self.assertEqual(body["shellConfig"]["targetJreVersion"], 50)
        self.assertFalse(body["shellConfig"]["byPassJavaModule"])
        self.assertTrue(body["shellConfig"]["shrink"])
        self.assertEqual(body["packer"], "DefaultBase64")
        self.assertEqual(body["injectorConfig"]["urlPattern"], "/*")
        self.assertEqual(body["shellToolConfig"]["headerName"], "User-Agent")
        self.assertEqual(body["shellToolConfig"]["encryptor"], "")

    def test_bypass_auto_when_jre_ge_9(self):
        body = build_generate_body(jre=9)
        self.assertTrue(body["shellConfig"]["byPassJavaModule"])
        self.assertEqual(body["shellConfig"]["targetJreVersion"], 53)
        body2 = build_generate_body(jre=9, by_pass_java_module=False)
        self.assertFalse(body2["shellConfig"]["byPassJavaModule"])

    def test_jre_release_maps_to_class_major(self):
        self.assertEqual(build_generate_body(jre=6)["shellConfig"]["targetJreVersion"], 50)
        self.assertEqual(build_generate_body(jre=8)["shellConfig"]["targetJreVersion"], 52)
        self.assertEqual(build_generate_body(jre=11)["shellConfig"]["targetJreVersion"], 55)
        self.assertEqual(build_generate_body(jre=17)["shellConfig"]["targetJreVersion"], 61)
        self.assertEqual(build_generate_body(jre=21)["shellConfig"]["targetJreVersion"], 65)
        self.assertEqual(build_generate_body(jre=22)["shellConfig"]["targetJreVersion"], 66)

    def test_target_jre_version_accepts_release_or_class(self):
        self.assertEqual(
            build_generate_body(target_jre_version=8)["shellConfig"]["targetJreVersion"], 52
        )
        self.assertEqual(
            build_generate_body(target_jre_version=53)["shellConfig"]["targetJreVersion"], 53
        )

    def test_jre_wins_over_target_jre_version(self):
        body = build_generate_body(jre=17, target_jre_version=8)
        self.assertEqual(body["shellConfig"]["targetJreVersion"], 61)

    def test_case_insensitive_enums(self):
        body = build_generate_body(
            server="tomcat",
            shell_tool="GODZILLA",
            shell_type="filter",
            password="example-pass",
            key="example-key",
        )
        self.assertEqual(body["shellConfig"]["server"], "Tomcat")
        self.assertEqual(body["shellConfig"]["shellTool"], "Godzilla")
        self.assertEqual(body["shellConfig"]["shellType"], "Filter")
        self.assertEqual(body["shellToolConfig"]["godzillaPass"], "example-pass")
        self.assertEqual(body["shellToolConfig"]["godzillaKey"], "example-key")

    def test_case_insensitive_via_body(self):
        body = build_generate_body(
            body={"shellConfig": {"server": "jetty", "shellTool": "behinder", "shellType": "LISTENER"}},
        )
        self.assertEqual(body["shellConfig"]["server"], "Jetty")
        self.assertEqual(body["shellConfig"]["shellTool"], "Behinder")
        self.assertEqual(body["shellConfig"]["shellType"], "Listener")

    def test_unknown_enum_passthrough(self):
        body = build_generate_body(server="MyCustomServer")
        self.assertEqual(body["shellConfig"]["server"], "MyCustomServer")

    def test_password_remaps_when_body_changes_tool(self):
        body = build_generate_body(
            password="example-pass",
            key="example-key",
            body={"shellConfig": {"shellTool": "godzilla"}},
        )
        self.assertEqual(body["shellConfig"]["shellTool"], "Godzilla")
        self.assertEqual(body["shellToolConfig"]["godzillaPass"], "example-pass")
        self.assertEqual(body["shellToolConfig"]["godzillaKey"], "example-key")
        self.assertEqual(body["shellToolConfig"]["behinderPass"], "")

    def test_invalid_jre_raises_without_echoing_input(self):
        sensitive_jre = "example-sensitive-jre"
        with self.assertRaises(ValueError) as ctx:
            build_generate_body(jre=sensitive_jre)

        self.assertEqual(str(ctx.exception), "invalid jre / target_jre_version")
        traceback_text = "".join(traceback.format_exception(ctx.exception))
        self.assertNotIn("example-sensitive", traceback_text)

    def test_command_defaults(self):
        body = build_generate_body(shell_tool="Command")
        self.assertEqual(body["shellToolConfig"]["encryptor"], "RAW")
        self.assertEqual(body["shellToolConfig"]["implementationClass"], "RuntimeExec")

    def test_command_defaults_via_body_override(self):
        body = build_generate_body(body={"shellConfig": {"shellTool": "Command"}})
        self.assertEqual(body["shellConfig"]["shellTool"], "Command")
        self.assertEqual(body["shellToolConfig"]["encryptor"], "RAW")
        self.assertEqual(body["shellToolConfig"]["implementationClass"], "RuntimeExec")

    def test_command_explicit_encryptor_kept(self):
        body = build_generate_body(shell_tool="Command", encryptor="BASE64")
        self.assertEqual(body["shellToolConfig"]["encryptor"], "BASE64")

    def test_probe_and_lambda_suffix(self):
        body = build_generate_body(probe=True, lambda_suffix=True)
        self.assertTrue(body["shellConfig"]["probe"])
        self.assertTrue(body["shellConfig"]["lambdaSuffix"])

    def test_body_deep_merge_overrides(self):
        body = build_generate_body(
            {"shellConfig": {"shellTool": "Godzilla"}, "packer": "GzipBase64"},
            shell_tool="Behinder",
            packer="DefaultBase64",
        )
        self.assertEqual(body["shellConfig"]["shellTool"], "Godzilla")
        self.assertEqual(body["packer"], "GzipBase64")
        self.assertEqual(body["shellConfig"]["server"], "Tomcat")

    def test_body_rejects_non_object_nested_configs(self):
        invalid_fields = (
            "shellConfig",
            "shellToolConfig",
            "injectorConfig",
        )
        for invalid_field in invalid_fields:
            with (
                self.subTest(invalid_field=invalid_field),
                self.assertRaisesRegex(
                    TypeError,
                    rf"body\.{invalid_field} must be an object",
                ),
            ):
                build_generate_body(body={invalid_field: "invalid"})

    def test_body_rejects_non_dictionary_value(self):
        with self.assertRaisesRegex(TypeError, "body must be a dictionary"):
            build_generate_body(body="invalid")

    def test_camelcase_official_fields(self):
        body = build_generate_body(
            behinder_pass="example-pass",
            header_value="example-token",
            target_jre_version="61",
        )
        self.assertEqual(body["shellToolConfig"]["behinderPass"], "example-pass")
        self.assertEqual(body["shellToolConfig"]["headerValue"], "example-token")
        self.assertEqual(body["shellConfig"]["targetJreVersion"], 61)
        self.assertTrue(body["shellConfig"]["byPassJavaModule"])


class TestBuildProbeBody(unittest.TestCase):
    def test_defaults(self):
        body = build_probe_body()
        self.assertEqual(body["probeConfig"]["probeMethod"], "ResponseBody")
        self.assertEqual(body["probeConfig"]["probeContent"], "Command")
        self.assertEqual(body["probeConfig"]["targetJreVersion"], 50)
        self.assertFalse(body["probeConfig"]["byPassJavaModule"])
        self.assertTrue(body["probeConfig"]["shrink"])
        self.assertTrue(body["probeConfig"]["staticInitialize"])
        self.assertFalse(body["probeConfig"]["debug"])
        self.assertFalse(body["probeConfig"]["lambdaSuffix"])
        self.assertEqual(body["packer"], "DefaultBase64")
        self.assertEqual(body["probeContentConfig"]["server"], "Tomcat")
        self.assertEqual(body["probeContentConfig"]["sleepServer"], "Tomcat")
        self.assertEqual(body["probeContentConfig"]["seconds"], 5)
        self.assertNotIn("host", body["probeContentConfig"])
        self.assertNotIn("reqParamName", body["probeContentConfig"])

    def test_jre9_auto_bypass_and_casefold(self):
        body = build_probe_body(method="dnslog", content="server", jre=9, host="x.example.test")
        self.assertEqual(body["probeConfig"]["probeMethod"], "DNSLog")
        self.assertEqual(body["probeConfig"]["probeContent"], "Server")
        self.assertEqual(body["probeConfig"]["targetJreVersion"], 53)
        self.assertTrue(body["probeConfig"]["byPassJavaModule"])
        self.assertEqual(body["probeContentConfig"]["host"], "x.example.test")

    def test_script_engine_and_filter_casefold(self):
        body = build_probe_body(content="scriptengine")
        self.assertEqual(body["probeConfig"]["probeContent"], "ScriptEngine")
        body2 = build_probe_body(content="filter")
        self.assertEqual(body2["probeConfig"]["probeContent"], "Filter")

    def test_rejects_bool_seconds(self):
        with self.assertRaises((TypeError, ValueError)):
            build_probe_body(seconds=True)

    def test_omits_empty_content_fields(self):
        body = build_probe_body(host="", req_param_name="", command_template="")
        self.assertNotIn("host", body["probeContentConfig"])
        self.assertNotIn("reqParamName", body["probeContentConfig"])
        self.assertNotIn("commandTemplate", body["probeContentConfig"])

    def test_body_merge_and_unknown_passthrough(self):
        body = build_probe_body(
            {"probeConfig": {"probeMethod": "Sleep"}, "packer": "JSP"},
            method="ResponseBody",
            content="NopeContent",
        )
        self.assertEqual(body["probeConfig"]["probeMethod"], "Sleep")
        self.assertEqual(body["probeConfig"]["probeContent"], "NopeContent")
        self.assertEqual(body["packer"], "JSP")

    def test_rejects_non_dict_body(self):
        with self.assertRaisesRegex(TypeError, "body must be a dictionary"):
            build_probe_body(["not", "a", "dict"])

    def test_rejects_illegal_nested_objects(self):
        with self.assertRaisesRegex(TypeError, "body.probeConfig must be an object"):
            build_probe_body({"probeConfig": []})
        with self.assertRaisesRegex(TypeError, "body.probeContentConfig must be an object"):
            build_probe_body({"probeContentConfig": "invalid"})

    def test_omits_seconds_when_none(self):
        body = build_probe_body(seconds=None)
        self.assertNotIn("seconds", body["probeContentConfig"])

    def test_jre_overrides_target_jre_version(self):
        body = build_probe_body(jre=11, target_jre_version=8)
        self.assertEqual(body["probeConfig"]["targetJreVersion"], 55)

    def test_accepts_enums_and_casefolds_server(self):
        body = build_probe_body(
            method=ProbeMethod.DNS_LOG,
            content=ProbeContent.SERVER,
            server="tomcat",
            sleep_server=Server.JETTY,
            host="x.example.test",
        )
        self.assertEqual(body["probeConfig"]["probeMethod"], "DNSLog")
        self.assertEqual(body["probeConfig"]["probeContent"], "Server")
        self.assertEqual(body["probeContentConfig"]["server"], "Tomcat")
        self.assertEqual(body["probeContentConfig"]["sleepServer"], "Jetty")


class TestExtractGenerateMeta(unittest.TestCase):
    def test_strips_bytes_and_exposes_output(self):
        result = {
            "packResult": "example-payload-" * 100,
            "memShellResult": {
                "shellClassName": "a.b.Shell",
                "injectorClassName": "a.b.Inj",
                "shellSize": 10,
                "injectorSize": 20,
                "shellConfig": {"shellTool": "Behinder"},
                "shellToolConfig": {"pass": "example-pass", "headerName": "User-Agent"},
                "injectorConfig": {
                    "urlPattern": "/*",
                    "shellClassBytes": "AAAA",
                    "helperClassBytes": "BBBB",
                    "fooBytes": "CCCC",
                },
            },
        }
        meta = extract_generate_meta(result, output="/tmp/out.txt")
        self.assertEqual(meta["shellClassName"], "a.b.Shell")
        self.assertEqual(meta["output"], "/tmp/out.txt")
        self.assertTrue(meta["hasPackResult"])
        self.assertNotIn("shellClassBytes", meta["injectorConfig"])
        self.assertNotIn("fooBytes", meta["injectorConfig"])
        self.assertEqual(meta["injectorConfig"]["urlPattern"], "/*")
        self.assertNotIn("packResult", meta)

    def test_rejects_invalid_nested_response_objects(self):
        invalid_nested_values = (None, False, 0, "", [], "invalid")
        for invalid_nested_value in invalid_nested_values:
            with (
                self.subTest(
                    field="memShellResult",
                    invalid_nested_value=invalid_nested_value,
                ),
                self.assertRaisesRegex(
                    TypeError,
                    "memShellResult must be an object",
                ),
            ):
                extract_generate_meta(
                    {"memShellResult": invalid_nested_value}
                )

            with (
                self.subTest(
                    field="injectorConfig",
                    invalid_nested_value=invalid_nested_value,
                ),
                self.assertRaisesRegex(
                    TypeError,
                    "injectorConfig must be an object",
                ),
            ):
                extract_generate_meta(
                    {
                        "memShellResult": {
                            "injectorConfig": invalid_nested_value,
                        }
                    }
                )


class TestExtractProbeMeta(unittest.TestCase):
    def test_strips_payload_and_exposes_output(self):
        meta = extract_probe_meta(
            {
                "packResult": "example-pack",
                "probeShellResult": {
                    "shellClassName": "example.Probe",
                    "shellSize": 12,
                    "shellBytesBase64Str": "example-bytes",
                    "probeConfig": {"probeMethod": "ResponseBody", "probeContent": "Command"},
                    "probeContentConfig": {"host": "x.example.test"},
                },
            },
            output="C:\\out.txt",
        )
        self.assertEqual(meta["shellClassName"], "example.Probe")
        self.assertEqual(meta["shellSize"], 12)
        self.assertTrue(meta["hasPackResult"])
        self.assertFalse(meta["hasAllPackResults"])
        self.assertEqual(meta["output"], "C:\\out.txt")
        self.assertNotIn("packResult", meta)
        self.assertNotIn("shellBytesBase64Str", meta)
        self.assertEqual(meta["probeConfig"], {"probeMethod": "ResponseBody", "probeContent": "Command"})
        self.assertEqual(meta["probeContentConfig"], {"host": "x.example.test"})

    def test_rejects_invalid_nested_response_objects(self):
        invalid_nested_values = (None, False, 0, "", [], "invalid")
        for invalid_nested_value in invalid_nested_values:
            with (
                self.subTest(
                    field="probeShellResult",
                    invalid_nested_value=invalid_nested_value,
                ),
                self.assertRaisesRegex(TypeError, "probeShellResult must be an object"),
            ):
                extract_probe_meta({"probeShellResult": invalid_nested_value})

            with (
                self.subTest(
                    field="probeConfig",
                    invalid_nested_value=invalid_nested_value,
                ),
                self.assertRaisesRegex(TypeError, "probeConfig must be an object"),
            ):
                extract_probe_meta(
                    {"probeShellResult": {"probeConfig": invalid_nested_value}}
                )

            with (
                self.subTest(
                    field="probeContentConfig",
                    invalid_nested_value=invalid_nested_value,
                ),
                self.assertRaisesRegex(TypeError, "probeContentConfig must be an object"),
            ):
                extract_probe_meta(
                    {"probeShellResult": {"probeContentConfig": invalid_nested_value}}
                )

    def test_redacts_nested_payload_fields(self):
        meta = extract_probe_meta(
            {
                "packResult": "example-pack",
                "probeShellResult": {
                    "shellClassName": "example.Probe",
                    "probeConfig": {
                        "probeMethod": "ResponseBody",
                        "packResult": "nested-pack",
                        "shellBytesBase64Str": "nested-bytes",
                        "evilBytes": "yy",
                        "unknownExtra": "drop-me",
                    },
                    "probeContentConfig": {
                        "host": {
                            "ok": "keep",
                            "packResult": "hidden",
                            "shellClassBase64": "zz",
                        },
                        "allPackResults": "nope",
                    },
                },
            }
        )
        self.assertEqual(meta["probeConfig"], {"probeMethod": "ResponseBody"})
        self.assertEqual(meta["probeContentConfig"], {"host": {"ok": "keep"}})
        self.assertNotIn("unknownExtra", meta["probeConfig"])
        self.assertNotIn("allPackResults", meta["probeContentConfig"])

    def test_accepts_probe_generate_result(self):
        result = ProbeGenerateResult(
            pack_result="example-pack",
            shell_class_name="example.Probe",
            shell_size=4,
            probe_config={
                "probeMethod": "Sleep",
                "packResult": "nested-pack",
                "unknownExtra": "drop-me",
            },
            probe_content_config={
                "seconds": 5,
                "shellClassBase64": "zz",
            },
        )
        meta = extract_probe_meta(result, output="C:\\out.txt")
        self.assertEqual(meta["shellClassName"], "example.Probe")
        self.assertEqual(meta["probeConfig"], {"probeMethod": "Sleep"})
        self.assertEqual(meta["probeContentConfig"], {"seconds": 5})
        self.assertTrue(meta["hasPackResult"])
        self.assertEqual(meta["output"], "C:\\out.txt")
        self.assertNotIn("packResult", meta)
        self.assertNotIn("unknownExtra", meta["probeConfig"])
        self.assertNotIn("shellClassBase64", meta["probeContentConfig"])


class TestMemShellPartyClient(unittest.TestCase):
    @mock.patch("wtfutil.memshellutil.requests_session")
    def test_internal_session_uses_connect_only_retry(self, session_factory):
        session_factory.return_value = mock.Mock()

        client = MemShellParty(base_url="https://example.test")

        retry = session_factory.call_args.kwargs["max_retries"]
        self.assertEqual(retry.total, 2)
        self.assertEqual(retry.connect, 2)
        self.assertEqual(retry.read, 0)
        self.assertEqual(retry.status, 0)
        self.assertEqual(retry.other, 0)
        self.assertEqual(retry.redirect, 0)
        self.assertEqual(retry.backoff_factor, 0.25)
        self.assertEqual(retry.allowed_methods, frozenset({"GET", "POST"}))
        client.close()

    @mock.patch("wtfutil.memshellutil.requests_session")
    def test_connect_retries_can_be_disabled(self, session_factory):
        session_factory.return_value = mock.Mock()

        client = MemShellParty(connect_retries=0)

        retry = session_factory.call_args.kwargs["max_retries"]
        self.assertEqual(retry.total, 0)
        self.assertEqual(retry.connect, 0)
        client.close()

    @mock.patch("wtfutil.memshellutil.Retry")
    def test_retry_builder_supports_urllib3_legacy_arguments(self, retry_class):
        legacy_retry = object()
        retry_class.side_effect = [TypeError("legacy signature"), legacy_retry]

        result = _build_connect_retry(2, 0.25)

        self.assertIs(result, legacy_retry)
        self.assertEqual(retry_class.call_count, 2)
        modern_arguments = retry_class.call_args_list[0].kwargs
        self.assertEqual(modern_arguments["other"], 0)
        self.assertEqual(
            modern_arguments["allowed_methods"], frozenset({"GET", "POST"})
        )
        legacy_arguments = retry_class.call_args_list[1].kwargs
        self.assertEqual(
            legacy_arguments["method_whitelist"], frozenset({"GET", "POST"})
        )
        self.assertNotIn("other", legacy_arguments)

    def test_retry_options_reject_invalid_values(self):
        for value in (-1, True, 1.5, "2"):
            with self.subTest(connect_retries=value), self.assertRaises(
                (TypeError, ValueError)
            ):
                MemShellParty(connect_retries=value)

        for value in (-0.1, "invalid", True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(retry_backoff=value), self.assertRaises(
                (TypeError, ValueError)
            ):
                MemShellParty(retry_backoff=value)

        sensitive_retry_backoff = "example-sensitive-backoff"
        with self.assertRaises(TypeError) as context:
            MemShellParty(retry_backoff=sensitive_retry_backoff)
        traceback_text = "".join(traceback.format_exception(context.exception))
        self.assertNotIn("example-sensitive-backoff", traceback_text)

    @mock.patch("wtfutil.memshellutil.requests_session")
    def test_external_session_retry_configuration_is_untouched(self, session_factory):
        session = mock.Mock()
        adapter = object()
        session.adapters = {"https://": adapter}
        session.proxies = {"https": "http://proxy.example"}
        session.trust_env = False

        client = MemShellParty(
            session=session,
            connect_retries=5,
            retry_backoff=1.0,
        )

        session_factory.assert_not_called()
        self.assertIs(client.req, session)
        self.assertIs(session.adapters["https://"], adapter)
        self.assertEqual(session.proxies, {"https": "http://proxy.example"})
        self.assertFalse(session.trust_env)
        client.close()
        session.close.assert_not_called()

    def test_get_config(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp({"Tomcat": {"Behinder": ["Listener"]}})
        client = MemShellParty(base_url="https://example.test", session=session)

        cfg = client.get_config()

        self.assertEqual(cfg["Tomcat"]["Behinder"], ["Listener"])
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/api/config"))
        self.assertEqual(kwargs["timeout"], 60)
        client.close()

    def test_generate_posts_json(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(
            {
                "packResult": "example-result",
                "memShellResult": {
                    "shellClassName": "ExampleShell",
                    "shellToolConfig": {"pass": "example-pass"},
                },
            }
        )
        client = MemShellParty(base_url="https://example.test/", session=session)

        result = client.generate(shell_tool="Behinder", behinder_pass="example-pass")

        self.assertIsInstance(result, MemShellGenerateResult)
        self.assertEqual(result.pack_result, "example-result")
        self.assertEqual(result.shell_class_name, "ExampleShell")
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/api/memshell/generate"))
        self.assertEqual(kwargs["json"]["shellConfig"]["shellTool"], "Behinder")
        self.assertEqual(kwargs["json"]["shellToolConfig"]["behinderPass"], "example-pass")
        client.close()

    def test_transport_error_is_wrapped_without_exposing_original_exception(self):
        session = mock.Mock()
        cause = RequestsConnectionError(OSError(101, "example-sensitive-detail"))
        session.request.side_effect = cause
        client = MemShellParty(base_url="https://example.test", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        self.assertIsNone(ctx.exception.__cause__)
        self.assertIsNone(ctx.exception.__context__)
        self.assertIsNone(ctx.exception.status_code)
        self.assertIsNone(ctx.exception.body)
        self.assertIn("GET https://example.test/api/config", str(ctx.exception))
        self.assertIn("ConnectionError", str(ctx.exception))
        self.assertIn("[Errno 101]", str(ctx.exception))
        self.assertNotIn("example-sensitive-detail", str(ctx.exception))
        client.close()

    def test_transport_error_traceback_does_not_include_sensitive_details(self):
        session = mock.Mock()
        session.request.side_effect = RequestsConnectionError(
            "proxy https://proxy-user:proxy-pass@proxy.example unavailable"
        )
        client = MemShellParty(
            base_url="https://api-user:api-pass@example.test",
            session=session,
        )

        with self.assertRaises(MemShellPartyError) as context:
            client.generate(
                shell_tool="Behinder",
                behinder_pass="example-pass",
                shell_class_base64="example-class-data",
            )

        traceback_text = "".join(traceback.format_exception(context.exception))
        for secret in (
            "api-user",
            "api-pass",
            "proxy-user",
            "proxy-pass",
            "example-pass",
            "example-class-data",
        ):
            self.assertNotIn(secret, traceback_text)
        client.close()

    def test_transport_error_redacts_credentials_and_request_body(self):
        session = mock.Mock()
        session.request.side_effect = RequestsConnectionError(
            "proxy https://proxy-user:proxy-pass@proxy.example unavailable"
        )
        client = MemShellParty(
            base_url="https://api-user:api-pass@example.test",
            session=session,
        )

        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate(
                shell_tool="Behinder",
                behinder_pass="example-pass",
                shell_class_base64="example-class-data",
            )

        message = str(ctx.exception)
        self.assertIn("POST https://example.test/api/memshell/generate", message)
        self.assertIn("ConnectionError: transport error", message)
        for secret in (
            "api-user",
            "api-pass",
            "proxy-user",
            "proxy-pass",
            "example-pass",
            "example-class-data",
        ):
            self.assertNotIn(secret, message)
        client.close()

    def test_transport_error_handles_malformed_base_url(self):
        session = mock.Mock()
        cause = RequestsConnectionError("example-sensitive-detail")
        session.request.side_effect = cause
        client = MemShellParty(base_url="https://[example-invalid", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        self.assertIsNone(ctx.exception.__cause__)
        self.assertIsNone(ctx.exception.__context__)
        self.assertIn("GET /api/config", str(ctx.exception))
        self.assertNotIn("example-invalid", str(ctx.exception))
        self.assertNotIn("example-sensitive-detail", str(ctx.exception))
        client.close()

    def test_transport_error_redacts_base_url_path(self):
        session = mock.Mock()
        session.request.side_effect = RequestsConnectionError("example-sensitive-detail")
        client = MemShellParty(
            base_url="https://example.test/example-path-secret",
            session=session,
        )

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        message = str(ctx.exception)
        self.assertIn("GET https://example.test/api/config", message)
        self.assertNotIn("example-path-secret", message)
        self.assertNotIn("example-sensitive-detail", message)
        client.close()

    def test_other_config_endpoints_use_session_request(self):
        session = mock.Mock()
        session.request.side_effect = [_fake_resp([]), _fake_resp({})]
        client = MemShellParty(base_url="https://example.test", session=session)

        self.assertEqual(client.get_packers_tree(), [])
        self.assertEqual(client.get_command_configs(), {})

        calls = session.request.call_args_list
        self.assertEqual(calls[0].args[:2], ("GET", "https://example.test/api/config/packers/tree"))
        self.assertEqual(
            calls[1].args[:2],
            ("GET", "https://example.test/api/config/command/configs"),
        )
        client.close()

    def test_invalid_json_error_redacts_response_body(self):
        session = mock.Mock()
        response = mock.Mock()
        response.status_code = 502
        response.text = "example-sensitive-response-payload"
        response.json.side_effect = ValueError("example-sensitive-parser-detail")
        session.request.return_value = response
        client = MemShellParty(base_url="https://example.test", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        self.assertEqual(str(ctx.exception), "invalid JSON response (HTTP 502)")
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIsNone(ctx.exception.body)
        traceback_text = "".join(traceback.format_exception(ctx.exception))
        self.assertNotIn("example-sensitive", traceback_text)
        response.json.assert_called_once_with()
        client.close()

    def test_enhanced_response_invalid_json_has_no_output_side_effect(self):
        session = mock.Mock()
        response = EnhancedResponse()
        response.status_code = 502
        response.url = "https://example.test/api/config"
        response._content = b"example-sensitive-response-payload"
        response.encoding = "utf-8"
        response._debug = False
        session.request.return_value = response
        client = MemShellParty(base_url="https://example.test", session=session)
        standard_output = io.StringIO()
        error_output = io.StringIO()

        with (
            mock.patch("sys.stdout", standard_output),
            mock.patch("sys.stderr", error_output),
            self.assertRaises(MemShellPartyError) as ctx,
        ):
            client.get_config()

        self.assertEqual(str(ctx.exception), "invalid JSON response (HTTP 502)")
        self.assertIsNone(ctx.exception.body)
        self.assertEqual(standard_output.getvalue(), "")
        self.assertEqual(error_output.getvalue(), "")
        client.close()

    def test_http_error_redacts_response_body_and_server_message(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(
            {
                "error": "example-sensitive-server-detail",
                "packResult": "example-generated-payload",
            },
            status_code=500,
        )
        client = MemShellParty(base_url="https://example.test", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()

        self.assertEqual(str(ctx.exception), "HTTP 500")
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIsNone(ctx.exception.body)
        self.assertNotIn("example-sensitive", str(ctx.exception))
        self.assertNotIn("example-generated-payload", str(ctx.exception))
        client.close()

    def test_body_error_field_redacts_server_message(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(
            {"error": "example-sensitive-server-detail"},
            status_code=200,
        )
        client = MemShellParty(base_url="https://example.test", session=session)

        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate()

        self.assertEqual(str(ctx.exception), "API response reported an error (HTTP 200)")
        self.assertEqual(ctx.exception.status_code, 200)
        self.assertIsNone(ctx.exception.body)
        self.assertNotIn("example-sensitive", str(ctx.exception))
        client.close()

    def test_generate_probe_posts_json(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(
            {"packResult": "example-probe", "probeShellResult": {"shellClassName": "P"}}
        )
        client = MemShellParty(base_url="https://example.test/", session=session)
        result = client.generate_probe(method="ResponseBody", content="Command")
        self.assertIsInstance(result, ProbeGenerateResult)
        self.assertEqual(result.pack_result, "example-probe")
        self.assertEqual(result.shell_class_name, "P")
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/api/probe/generate"))
        self.assertEqual(kwargs["json"]["probeConfig"]["probeMethod"], "ResponseBody")
        self.assertEqual(kwargs["json"]["probeConfig"]["probeContent"], "Command")
        self.assertTrue(kwargs["json"]["probeConfig"]["shrink"])
        client.close()

    def test_generate_probe_http_error_redacts_body(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(
            {"error": "example-server-secret"}, status_code=400
        )
        client = MemShellParty(base_url="https://example.test/", session=session)
        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate_probe()
        self.assertIsNone(ctx.exception.body)
        self.assertNotIn("example-server-secret", str(ctx.exception))
        client.close()

    def test_generate_probe_rejects_non_object_response(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(["not", "an", "object"])
        client = MemShellParty(base_url="https://example.test/", session=session)
        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate_probe()
        self.assertEqual(str(ctx.exception), "invalid JSON response (HTTP 200)")
        self.assertEqual(ctx.exception.status_code, 200)
        self.assertNotIn("not", str(ctx.exception))
        client.close()

    def test_generate_rejects_non_object_response(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp(["not", "an", "object"])
        client = MemShellParty(base_url="https://example.test/", session=session)
        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate()
        self.assertEqual(str(ctx.exception), "invalid JSON response (HTTP 200)")
        self.assertEqual(ctx.exception.status_code, 200)
        self.assertIsNone(ctx.exception.body)
        self.assertNotIn("not", str(ctx.exception))
        client.close()

    def test_generate_wraps_invalid_nested_result(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp({"memShellResult": []})
        client = MemShellParty(base_url="https://example.test/", session=session)
        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate()
        self.assertEqual(str(ctx.exception), "invalid JSON response (HTTP 200)")
        self.assertIsNone(ctx.exception.body)
        client.close()

    def test_generate_probe_wraps_invalid_nested_result(self):
        session = mock.Mock()
        session.request.return_value = _fake_resp({"probeShellResult": "invalid"})
        client = MemShellParty(base_url="https://example.test/", session=session)
        with self.assertRaises(MemShellPartyError) as ctx:
            client.generate_probe()
        self.assertEqual(str(ctx.exception), "invalid JSON response (HTTP 200)")
        self.assertIsNone(ctx.exception.body)
        client.close()


class TestMemshellCli(unittest.TestCase):
    def test_body_only_requires_body(self):
        code = memshell_main(["generate", "--body-only", "-o", "x.txt"])
        self.assertEqual(code, 1)

    def test_generate_writes_pack_result(self):
        fake_result = {
            "packResult": "example-generated-payload",
            "memShellResult": {
                "shellClassName": "example.Shell",
                "injectorClassName": "example.Injector",
                "shellSize": 1,
                "injectorSize": 2,
                "shellConfig": {"shellTool": "Behinder"},
                "shellToolConfig": {"pass": "example-pass"},
                "injectorConfig": {"urlPattern": "/*"},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "payload.txt"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate.return_value = _as_generate_result(fake_result)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = memshell_main(
                        ["generate", "-o", str(out), "--password", "example-pass"]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "example-generated-payload")
            meta = json.loads(buf.getvalue())
            self.assertEqual(meta["shellClassName"], "example.Shell")
            self.assertEqual(meta["shellToolConfig"]["pass"], "example-pass")
            self.assertIn("output", meta)
            self.assertNotIn("packResult", meta)
            # 通用 --password 应映射为 password 传给 generate
            kwargs = inst.generate.call_args.kwargs
            self.assertEqual(kwargs.get("password"), "example-pass")

    def test_cli_pass_maps_for_godzilla(self):
        fake_result = {
            "packResult": "example-godzilla-payload",
            "memShellResult": {
                "shellClassName": "S",
                "injectorClassName": "I",
                "shellConfig": {"shellTool": "Godzilla"},
                "shellToolConfig": {},
                "injectorConfig": {},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "g.txt"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate.return_value = _as_generate_result(fake_result)
                with mock.patch("sys.stdout", io.StringIO()):
                    code = memshell_main(
                        [
                            "generate",
                            "--shell-tool",
                            "Godzilla",
                            "--password",
                            "example-pass",
                            "--key",
                            "example-key",
                            "-o",
                            str(out),
                        ]
                    )
            self.assertEqual(code, 0)
            kwargs = inst.generate.call_args.kwargs
            self.assertEqual(kwargs.get("shell_tool"), "Godzilla")
            self.assertEqual(kwargs.get("password"), "example-pass")
            self.assertEqual(kwargs.get("key"), "example-key")

    def test_cli_case_insensitive_and_hidden_flags(self):
        fake_result = {
            "packResult": "example-case-insensitive-payload",
            "memShellResult": {
                "shellClassName": "S",
                "injectorClassName": "I",
                "shellConfig": {},
                "shellToolConfig": {},
                "injectorConfig": {},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "x.txt"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate.return_value = _as_generate_result(fake_result)
                with mock.patch("sys.stdout", io.StringIO()):
                    code = memshell_main(
                        [
                            "generate",
                            "--server",
                            "tomcat",
                            "--shell-tool",
                            "behinder",
                            "--shell-type",
                            "filter",
                            "--jre",
                            "9",
                            "--behinder-pass",
                            "example-pass",
                            "--target-jre-version",
                            "8",
                            "-o",
                            str(out),
                        ]
                    )
            self.assertEqual(code, 0)
            kwargs = inst.generate.call_args.kwargs
            self.assertEqual(kwargs.get("server"), "tomcat")
            self.assertEqual(kwargs.get("shell_tool"), "behinder")
            self.assertEqual(kwargs.get("shell_type"), "filter")
            self.assertEqual(kwargs.get("jre"), "9")
            self.assertEqual(kwargs.get("behinder_pass"), "example-pass")
            # --jre 优先，不应再带 target_jre_version
            self.assertNotIn("target_jre_version", kwargs)

    def test_cli_hidden_target_jre_still_works(self):
        fake_result = {
            "packResult": "example-target-jre-payload",
            "memShellResult": {
                "shellClassName": "S",
                "injectorClassName": "I",
                "shellConfig": {},
                "shellToolConfig": {},
                "injectorConfig": {},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "y.txt"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate.return_value = _as_generate_result(fake_result)
                with mock.patch("sys.stdout", io.StringIO()):
                    code = memshell_main(
                        ["generate", "--target-jre-version", "17", "-o", str(out)]
                    )
            self.assertEqual(code, 0)
            kwargs = inst.generate.call_args.kwargs
            self.assertEqual(kwargs.get("target_jre_version"), "17")
            self.assertNotIn("jre", kwargs)

    def test_cli_reports_invalid_nested_body_without_traceback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            body_path = Path(temporary_directory) / "body.json"
            body_path.write_text(
                json.dumps({"shellConfig": "invalid"}),
                encoding="utf-8",
            )
            error_output = io.StringIO()
            with mock.patch("wtfutil.memshell.MemShellParty") as client_class:
                client_class.return_value.generate.side_effect = (
                    lambda body, **kwargs: build_generate_body(body, **kwargs)
                )
                with mock.patch("sys.stderr", error_output):
                    code = memshell_main(
                        ["generate", "--body", str(body_path), "--body-only"]
                    )

        self.assertEqual(code, 1)
        self.assertIn("body.shellConfig must be an object", error_output.getvalue())
        self.assertNotIn("Traceback", error_output.getvalue())

    def test_cli_redacts_unwrapped_request_exception(self):
        error_output = io.StringIO()
        with mock.patch("wtfutil.memshell.MemShellParty") as client_class:
            client_class.return_value.get_config.side_effect = RequestsConnectionError(
                "proxy https://example-user:example-pass@proxy.example unavailable"
            )
            with mock.patch("sys.stderr", error_output):
                code = memshell_main(["config"])

        message = error_output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("request failed: transport error", message)
        self.assertNotIn("example-user", message)
        self.assertNotIn("example-pass", message)
        self.assertNotIn("Traceback", message)

    def test_cli_redacts_body_file_os_error(self):
        error_output = io.StringIO()
        file_error = OSError(
            5,
            "example-sensitive-os-detail",
            "example-sensitive-body-path.json",
        )
        with mock.patch("builtins.open", side_effect=file_error), mock.patch(
            "sys.stderr", error_output
        ):
            code = memshell_main(
                ["generate", "--body", "example-sensitive-body-path.json"]
            )

        message = error_output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("I/O error [Errno 5]", message)
        self.assertNotIn("example-sensitive", message)
        self.assertNotIn("Traceback", message)

    def test_cli_redacts_invalid_json_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            body_path = Path(temporary_directory) / "example-body.json"
            body_path.write_text("{example-sensitive-json-content", encoding="utf-8")
            error_output = io.StringIO()

            with mock.patch("sys.stderr", error_output):
                code = memshell_main(["generate", "--body", str(body_path)])

        message = error_output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("invalid JSON input", message)
        self.assertNotIn("example-sensitive", message)
        self.assertNotIn("Traceback", message)

    def test_cli_redacts_invalid_utf8_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            body_path = Path(temporary_directory) / "example-body.json"
            body_path.write_bytes(b"\xffexample-sensitive-utf8-content")
            error_output = io.StringIO()

            with mock.patch("sys.stderr", error_output):
                code = memshell_main(["generate", "--body", str(body_path)])

        message = error_output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("invalid UTF-8 input", message)
        self.assertNotIn("example-sensitive", message)
        self.assertNotIn("Traceback", message)

    def test_cli_redacts_output_file_os_error(self):
        error_output = io.StringIO()
        file_error = OSError(
            5,
            "example-sensitive-os-detail",
            "example-sensitive-output-path.txt",
        )
        with (
            mock.patch("wtfutil.memshell.MemShellParty") as client_class,
            mock.patch("pathlib.Path.write_text", side_effect=file_error),
            mock.patch("sys.stderr", error_output),
        ):
            client_class.return_value.generate.return_value = _as_generate_result(
                {
                    "packResult": "example-generated-payload",
                    "memShellResult": {},
                }
            )
            code = memshell_main(
                ["generate", "-o", "example-sensitive-output-path.txt"]
            )

        message = error_output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("I/O error [Errno 5]", message)
        self.assertNotIn("example-sensitive", message)
        self.assertNotIn("Traceback", message)

    def test_cli_reports_wrapped_transport_error_without_traceback(self):
        error_output = io.StringIO()
        with mock.patch("wtfutil.memshell.MemShellParty") as client_class:
            client_class.return_value.get_config.side_effect = MemShellPartyError(
                "GET https://example.test/api/config request failed: ConnectionError"
            )
            with mock.patch("sys.stderr", error_output):
                code = memshell_main(["config"])

        self.assertEqual(code, 1)
        self.assertIn("request failed", error_output.getvalue())
        self.assertNotIn("Traceback", error_output.getvalue())

    def test_generate_empty_pack_uses_all_pack_results(self):
        fake_result = {
            "packResult": "",
            "allPackResults": {
                "DefaultBase64": "example-default-payload",
                "GzipBase64": "example-gzip-payload",
            },
            "memShellResult": {
                "shellClassName": "S",
                "injectorClassName": "I",
                "shellConfig": {},
                "shellToolConfig": {},
                "injectorConfig": {},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "payload.json"
            with (
                mock.patch("wtfutil.memshell.MemShellParty") as cls,
                mock.patch("sys.stdout", io.StringIO()),
            ):
                cls.return_value.generate.return_value = _as_generate_result(fake_result)
                code = memshell_main(["generate", "-o", str(out)])
            self.assertEqual(code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["GzipBase64"], "example-gzip-payload")

    def test_install_skill_project(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            with (
                mock.patch("wtfutil.memshell.Path.cwd", return_value=td_path),
                mock.patch("sys.stdout", io.StringIO()),
            ):
                code = memshell_main(["install-skill", "--project"])
            self.assertEqual(code, 0)
            skill = td_path / ".agents" / "skills" / "memshell" / "SKILL.md"
            self.assertTrue(skill.is_file())
            self.assertIn("memshell generate", skill.read_text(encoding="utf-8"))
            self.assertFalse((td_path / ".agents" / "skills" / "memshell" / "__init__.py").exists())

    def test_install_skill_requires_flag(self):
        code = memshell_main(["install-skill"])
        self.assertEqual(code, 2)

    def test_probe_writes_pack_result(self):
        fake = {
            "packResult": "example-probe-pack",
            "probeShellResult": {
                "shellClassName": "example.Probe",
                "shellSize": 3,
                "probeConfig": {"probeMethod": "ResponseBody", "probeContent": "Command"},
                "probeContentConfig": {},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "p.txt"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate_probe.return_value = _as_probe_result(fake)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = memshell_main(
                        ["probe", "-m", "ResponseBody", "-c", "Command", "-o", str(out)]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "example-probe-pack")
            meta = json.loads(buf.getvalue())
            self.assertEqual(meta["shellClassName"], "example.Probe")
            self.assertNotIn("packResult", meta)
            kwargs = inst.generate_probe.call_args.kwargs
            self.assertEqual(kwargs.get("method"), "ResponseBody")
            self.assertEqual(kwargs.get("content"), "Command")

    def test_probe_error_no_traceback(self):
        with mock.patch("wtfutil.memshell.MemShellParty") as cls:
            inst = cls.return_value
            inst.generate_probe.side_effect = MemShellPartyError("HTTP 400")
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                code = memshell_main(["probe", "-m", "ResponseBody", "-c", "Command"])
        self.assertEqual(code, 1)
        message = err.getvalue()
        self.assertEqual(message, "error: HTTP 400\n")
        self.assertNotIn("Traceback", message)
        self.assertNotIn("usage:", message)

    def test_probe_writes_all_pack_results_fallback(self):
        fake = {
            "packResult": "",
            "allPackResults": {"GzipBase64": "example-gzip-probe"},
            "probeShellResult": {
                "shellClassName": "example.Probe",
                "shellSize": 3,
                "probeConfig": {"probeMethod": "ResponseBody"},
                "probeContentConfig": {},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "p.json"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate_probe.return_value = _as_probe_result(fake)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = memshell_main(["probe", "-o", str(out)])
            self.assertEqual(code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["GzipBase64"], "example-gzip-probe")
            meta = json.loads(buf.getvalue())
            self.assertTrue(meta["hasAllPackResults"])
            self.assertNotIn("packResult", meta)

    def test_probe_without_output_prints_full_json(self):
        fake = {
            "packResult": "example-probe-pack",
            "probeShellResult": {
                "shellClassName": "example.Probe",
                "probeConfig": {"probeMethod": "ResponseBody"},
                "probeContentConfig": {},
            },
        }
        with mock.patch("wtfutil.memshell.MemShellParty") as cls:
            inst = cls.return_value
            inst.generate_probe.return_value = _as_probe_result(fake)
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = memshell_main(["probe", "-m", "dnslog", "-c", "server"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["packResult"], "example-probe-pack")
        self.assertEqual(inst.generate_probe.call_args.kwargs["method"], "dnslog")
        self.assertEqual(inst.generate_probe.call_args.kwargs["content"], "server")

    def test_probe_non_object_response_is_single_line_error(self):
        with mock.patch("wtfutil.memshell.MemShellParty") as cls:
            inst = cls.return_value
            inst.generate_probe.side_effect = MemShellPartyError(
                "invalid JSON response (HTTP 200)",
                status_code=200,
            )
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                code = memshell_main(["probe"])
        self.assertEqual(code, 1)
        message = err.getvalue()
        self.assertEqual(message, "error: invalid JSON response (HTTP 200)\n")
        self.assertNotIn("Traceback", message)
        self.assertNotIn("usage:", message)

    def test_probe_invalid_seconds_is_single_line_error(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            code = memshell_main(["probe", "--seconds", "nope"])
        self.assertEqual(code, 1)
        message = err.getvalue()
        self.assertEqual(message, "error: seconds must be an integer\n")
        self.assertNotIn("Traceback", message)
        self.assertNotIn("usage:", message)


@unittest.skipUnless(_RUN_LIVE, "设置 MEMSHELL_RUN_LIVE=1 以运行外部联调")
class TestMemShellPartyLive(unittest.TestCase):
    """访问真实 MemShellParty 服务（默认 https://party.mem.mk）。"""

    def test_live_get_config(self):
        with MemShellParty(base_url=DEFAULT_BASE_URL, timeout=30) as client:
            cfg = client.get_config()
        self.assertIn("Tomcat", cfg)
        self.assertIn("Behinder", cfg["Tomcat"])
        self.assertIn("Listener", cfg["Tomcat"]["Behinder"])

    def test_live_get_packers_tree(self):
        with MemShellParty(timeout=30) as client:
            tree = client.get_packers_tree()
        self.assertIsInstance(tree, list)
        names = {item.get("name") for item in tree if isinstance(item, dict)}
        self.assertIn("Base64", names)

    def test_live_generate_behinder(self):
        with MemShellParty(timeout=60) as client:
            result = client.generate(
                server="Tomcat",
                shell_tool="Behinder",
                shell_type="Listener",
                target_jre_version=50,
                behinder_pass="example-pass",
                header_value="example-token",
                packer="DefaultBase64",
            )
        self.assertTrue(result.pack_result)
        self.assertTrue(result.shell_class_name)
        self.assertTrue(result.injector_class_name)
        self.assertIsInstance(result.shell_tool_config, dict)

    def test_live_cli_generate_to_file(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "live_payload.txt"
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = memshell_main(
                    [
                        "generate",
                        "--shell-tool",
                        "Behinder",
                        "--shell-type",
                        "Listener",
                        "--password",
                        "example-pass",
                        "--header-value",
                        "example-token",
                        "-o",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertGreater(out.stat().st_size, 100)
            meta = json.loads(buf.getvalue())
            self.assertEqual(meta.get("shellConfig", {}).get("shellTool"), "Behinder")
            self.assertTrue(meta.get("output"))


if __name__ == "__main__":
    unittest.main()
