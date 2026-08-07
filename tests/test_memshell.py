"""memshellutil / memshell CLI 测试。

默认只运行 mock 单测。设置 ``MEMSHELL_RUN_LIVE=1`` 后才运行访问
``https://party.mem.mk`` 的联调用例。
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wtfutil.memshell import main as memshell_main
from wtfutil.memshellutil import (
    DEFAULT_BASE_URL,
    MemShellParty,
    MemShellPartyError,
    build_generate_body,
    extract_generate_meta,
    resolve_shell_credentials,
)

_RUN_LIVE = os.getenv("MEMSHELL_RUN_LIVE", "").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _fake_resp(data, status_code: int = 200):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = json.dumps(data) if not isinstance(data, str) else data
    return resp


class TestResolveShellCredentials(unittest.TestCase):
    def test_pass_maps_behinder(self):
        c = resolve_shell_credentials("Behinder", password="p1")
        self.assertEqual(c["behinder_pass"], "p1")
        self.assertEqual(c["godzilla_pass"], "")
        self.assertEqual(c["ant_sword_pass"], "")

    def test_pass_maps_case_insensitive(self):
        c = resolve_shell_credentials("behinder", password="p1")
        self.assertEqual(c["behinder_pass"], "p1")
        c2 = resolve_shell_credentials("GODZILLA", password="gp", key="gk")
        self.assertEqual(c2["godzilla_pass"], "gp")
        self.assertEqual(c2["godzilla_key"], "gk")

    def test_pass_maps_godzilla_with_key(self):
        c = resolve_shell_credentials("Godzilla", password="gp", key="gk")
        self.assertEqual(c["godzilla_pass"], "gp")
        self.assertEqual(c["godzilla_key"], "gk")
        self.assertEqual(c["behinder_pass"], "")

    def test_pass_maps_antsword(self):
        c = resolve_shell_credentials("AntSword", password="ap")
        self.assertEqual(c["ant_sword_pass"], "ap")

    def test_specific_overrides_generic(self):
        c = resolve_shell_credentials(
            "Behinder",
            password="generic",
            behinder_pass="specific",
        )
        self.assertEqual(c["behinder_pass"], "specific")

    def test_build_body_password_convenience(self):
        body = build_generate_body(shell_tool="Behinder", password="via")
        self.assertEqual(body["shellToolConfig"]["behinderPass"], "via")
        body2 = build_generate_body(shell_tool="Godzilla", password="p", key="k")
        self.assertEqual(body2["shellToolConfig"]["godzillaPass"], "p")
        self.assertEqual(body2["shellToolConfig"]["godzillaKey"], "k")


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
            password="p",
            key="k",
        )
        self.assertEqual(body["shellConfig"]["server"], "Tomcat")
        self.assertEqual(body["shellConfig"]["shellTool"], "Godzilla")
        self.assertEqual(body["shellConfig"]["shellType"], "Filter")
        self.assertEqual(body["shellToolConfig"]["godzillaPass"], "p")
        self.assertEqual(body["shellToolConfig"]["godzillaKey"], "k")

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
            password="p",
            key="k",
            body={"shellConfig": {"shellTool": "godzilla"}},
        )
        self.assertEqual(body["shellConfig"]["shellTool"], "Godzilla")
        self.assertEqual(body["shellToolConfig"]["godzillaPass"], "p")
        self.assertEqual(body["shellToolConfig"]["godzillaKey"], "k")
        self.assertEqual(body["shellToolConfig"]["behinderPass"], "")

    def test_invalid_jre_raises(self):
        with self.assertRaises(ValueError):
            build_generate_body(jre="abc")

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
            behinder_pass="p",
            header_value="v",
            target_jre_version="61",
        )
        self.assertEqual(body["shellToolConfig"]["behinderPass"], "p")
        self.assertEqual(body["shellToolConfig"]["headerValue"], "v")
        self.assertEqual(body["shellConfig"]["targetJreVersion"], 61)
        self.assertTrue(body["shellConfig"]["byPassJavaModule"])


class TestExtractGenerateMeta(unittest.TestCase):
    def test_strips_bytes_and_exposes_output(self):
        result = {
            "packResult": "PAYLOAD" * 100,
            "memShellResult": {
                "shellClassName": "a.b.Shell",
                "injectorClassName": "a.b.Inj",
                "shellSize": 10,
                "injectorSize": 20,
                "shellConfig": {"shellTool": "Behinder"},
                "shellToolConfig": {"pass": "x", "headerName": "User-Agent"},
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


class TestMemShellPartyClient(unittest.TestCase):
    def test_get_config(self):
        session = mock.Mock()
        session.get.return_value = _fake_resp({"Tomcat": {"Behinder": ["Listener"]}})
        client = MemShellParty(base_url="https://example.test", session=session)
        cfg = client.get_config()
        self.assertEqual(cfg["Tomcat"]["Behinder"], ["Listener"])
        session.get.assert_called_once()
        self.assertIn("/api/config", session.get.call_args[0][0])
        client.close()

    def test_generate_posts_json(self):
        session = mock.Mock()
        session.post.return_value = _fake_resp(
            {
                "packResult": "abc",
                "memShellResult": {"shellClassName": "S", "shellToolConfig": {"pass": "p"}},
            }
        )
        client = MemShellParty(base_url="https://example.test/", session=session)
        result = client.generate(shell_tool="Behinder", behinder_pass="p")
        self.assertEqual(result["packResult"], "abc")
        args, kwargs = session.post.call_args
        self.assertTrue(args[0].endswith("/api/memshell/generate"))
        self.assertEqual(kwargs["json"]["shellConfig"]["shellTool"], "Behinder")
        self.assertEqual(kwargs["json"]["shellToolConfig"]["behinderPass"], "p")
        client.close()

    def test_http_error_raises(self):
        session = mock.Mock()
        session.get.return_value = _fake_resp({"error": "boom"}, status_code=500)
        client = MemShellParty(base_url="https://example.test", session=session)
        with self.assertRaises(MemShellPartyError) as ctx:
            client.get_config()
        self.assertIn("boom", str(ctx.exception))
        client.close()

    def test_body_error_field_raises(self):
        session = mock.Mock()
        session.post.return_value = _fake_resp({"error": "bad combo"}, status_code=200)
        client = MemShellParty(base_url="https://example.test", session=session)
        with self.assertRaises(MemShellPartyError):
            client.generate()
        client.close()


class TestMemshellCli(unittest.TestCase):
    def test_body_only_requires_body(self):
        code = memshell_main(["generate", "--body-only", "-o", "x.txt"])
        self.assertEqual(code, 1)

    def test_generate_writes_pack_result(self):
        fake_result = {
            "packResult": "ONLY_PAYLOAD",
            "memShellResult": {
                "shellClassName": "pkg.Shell",
                "injectorClassName": "pkg.Inj",
                "shellSize": 1,
                "injectorSize": 2,
                "shellConfig": {"shellTool": "Behinder"},
                "shellToolConfig": {"pass": "secret"},
                "injectorConfig": {"urlPattern": "/*"},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "payload.txt"
            with mock.patch("wtfutil.memshell.MemShellParty") as cls:
                inst = cls.return_value
                inst.generate.return_value = fake_result
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = memshell_main(["generate", "-o", str(out), "--password", "secret"])
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "ONLY_PAYLOAD")
            meta = json.loads(buf.getvalue())
            self.assertEqual(meta["shellClassName"], "pkg.Shell")
            self.assertEqual(meta["shellToolConfig"]["pass"], "secret")
            self.assertIn("output", meta)
            self.assertNotIn("packResult", meta)
            # 通用 --password 应映射为 password 传给 generate
            kwargs = inst.generate.call_args.kwargs
            self.assertEqual(kwargs.get("password"), "secret")

    def test_cli_pass_maps_for_godzilla(self):
        fake_result = {
            "packResult": "G",
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
                inst.generate.return_value = fake_result
                with mock.patch("sys.stdout", io.StringIO()):
                    code = memshell_main(
                        [
                            "generate",
                            "--shell-tool",
                            "Godzilla",
                            "--password",
                            "gp",
                            "--key",
                            "gk",
                            "-o",
                            str(out),
                        ]
                    )
            self.assertEqual(code, 0)
            kwargs = inst.generate.call_args.kwargs
            self.assertEqual(kwargs.get("shell_tool"), "Godzilla")
            self.assertEqual(kwargs.get("password"), "gp")
            self.assertEqual(kwargs.get("key"), "gk")

    def test_cli_case_insensitive_and_hidden_flags(self):
        fake_result = {
            "packResult": "X",
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
                inst.generate.return_value = fake_result
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
                            "hidden-ok",
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
            self.assertEqual(kwargs.get("behinder_pass"), "hidden-ok")
            # --jre 优先，不应再带 target_jre_version
            self.assertNotIn("target_jre_version", kwargs)

    def test_cli_hidden_target_jre_still_works(self):
        fake_result = {
            "packResult": "Y",
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
                inst.generate.return_value = fake_result
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

    def test_generate_empty_pack_uses_all_pack_results(self):
        fake_result = {
            "packResult": "",
            "allPackResults": {"DefaultBase64": "x", "GzipBase64": "y"},
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
                cls.return_value.generate.return_value = fake_result
                code = memshell_main(["generate", "-o", str(out)])
            self.assertEqual(code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["GzipBase64"], "y")

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
                behinder_pass="testpass",
                header_value="testua",
                packer="DefaultBase64",
            )
        self.assertTrue(result.get("packResult"))
        mem = result["memShellResult"]
        self.assertTrue(mem.get("shellClassName"))
        self.assertTrue(mem.get("injectorClassName"))
        tool = mem.get("shellToolConfig") or {}
        self.assertIsInstance(tool, dict)

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
                        "clipass",
                        "--header-value",
                        "clihdr",
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
