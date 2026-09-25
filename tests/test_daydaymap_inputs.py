"""Query, source and pipe contracts. Only local/mock services and fake credentials."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wtfutil import daydaymaputil as sdk
from tests.test_daydaymap import ClientCase, FakeSession, agg, error, page, row


class TestQueryRules(ClientCase):
    def test_builder_wraps_or_and_always_excludes_honeypots(self):
        self.assertTrue(callable(getattr(sdk, 'build_query', None)), 'missing query builder')
        self.assertEqual(sdk.build_query(' a || b '), '(a || b) && ip.tag!="蜜罐"')
        # Text inside a quoted value must not disable the mandatory exclusion.
        query = sdk.build_query('web.title="ip.tag!=\\\"蜜罐\\\""')
        self.assertTrue(query.endswith(' && ip.tag!="蜜罐"'))

    def test_optional_filters_apply_to_count_fallback_and_all_pages(self):
        client = self.make_client(api=[page([row(1)], 2)], web=[error(2006)], max_retries=0)
        result = client.count('a || b', is_china=True, is_domain=True)
        queries = [base64.b64decode(c['json']['keyword']).decode() for c in self.web.calls + self.api.calls]
        self.assertEqual(queries, [result.query, result.query])
        for clause in ('ip.tag!="蜜罐"', 'ip.country="CN"', 'ip.province!="台湾"',
                       'ip.province!="香港"', 'ip.province!="澳门"', 'ip.city!="香港"',
                       'ip.city!="澳门"', 'is_domain="true"'):
            self.assertIn(clause, result.query)
        client = self.make_client(api=[error(2004), page([row(1)], 2), page([row(2)], 2)], web=[agg(2)])
        self.assertEqual(len(list(client.search('a || b', is_china=True, is_domain=True, page_size=1))), 2)
        self.assertTrue(all(base64.b64decode(c['json']['keyword']).decode() == result.query
                            for c in self.web.calls + self.api.calls))

    def test_count_callback_precedes_rows_without_extra_api_probe(self):
        for web in ([agg(1)], [error(2006)]):
            with self.subTest(aggregate=web):
                client = self.make_client(api=[page([row(1)], 1)], web=web, max_retries=0)
                events = []
                iterator = client.search('x', on_count=lambda c: events.append(c.to_dict()))
                self.assertEqual(next(iterator), row(1))
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['total'], 1)
                self.assertEqual(events[0]['query'], '(x) && ip.tag!="蜜罐"')
                self.assertEqual(len(self.api.calls), 1)
                iterator.close()

    def test_no_implicit_region_domain_or_ipv4_filter(self):
        client = self.make_client(web=[agg(1)])
        self.assertEqual(client.count('x').query, '(x) && ip.tag!="蜜罐"')


ICON = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'


class SourceResponse:
    def __init__(self, content=ICON, status=200, headers=None, chunks=None):
        self.status_code = status
        self.headers = headers or {}
        self.chunks = chunks if chunks is not None else [content]
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self.chunks

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


class TestSources(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(sdk, 'query_from_icon', None)), 'missing icon source helper')
        self.assertTrue(callable(getattr(sdk, 'query_from_certificate', None)), 'missing certificate source helper')

    def test_icon_file_and_download_use_same_raw_bytes(self):
        expected = 'web.icon="' + hashlib.md5(ICON).hexdigest() + '"'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'icon.svg'
            path.write_bytes(ICON)
            self.assertEqual(sdk.query_from_icon(path), expected)
        response = SourceResponse()
        with mock.patch('wtfutil.daydaymaputil.requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            session.get.return_value = response
            result = sdk.query_from_icon(url='https://example.com/icon.svg', proxy='http://127.0.0.1:8080')
        self.assertEqual(result, expected)
        self.assertTrue(response.closed)
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_args.kwargs['proxies'],
                         {'http': 'http://127.0.0.1:8080', 'https': 'http://127.0.0.1:8080'})
        self.assertTrue(session.get.call_args.kwargs['verify'])
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_empty_html_and_oversized_downloads_are_rejected(self):
        for response in (SourceResponse(b''), SourceResponse(b'<html>error</html>'),
                         SourceResponse(status=404), SourceResponse(chunks=[ICON, b'x' * (2 * 1024 * 1024)])):
            with self.subTest(status=response.status_code), mock.patch('wtfutil.daydaymaputil.requests.Session') as factory:
                factory.return_value.__enter__.return_value.get.return_value = response
                with self.assertRaises(sdk.DayDayMapError):
                    sdk.query_from_icon(url='https://example.com/icon?token=example-secret')
                self.assertTrue(response.closed)

    def test_unknown_svg_encoding_is_a_sanitized_invalid_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'icon.svg'
            path.write_bytes(b'<?xml version="1.0" encoding="example-secret"?><svg/>')
            with self.assertRaises(sdk.DayDayMapError) as caught:
                sdk.query_from_icon(path)
        self.assertEqual(caught.exception.reason, 'invalid_icon')
        self.assertNotIn('example-secret', str(caught.exception))

    def test_file_size_bound_and_invalid_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'icon.bin'
            for content in (b'', b'not an icon', ICON + b'x' * (2 * 1024 * 1024)):
                path.write_bytes(content)
                with self.assertRaises(sdk.DayDayMapError):
                    sdk.query_from_icon(path)
            with self.assertRaises(sdk.DayDayMapError) as caught:
                sdk.query_from_icon(path / 'missing')
            self.assertEqual(caught.exception.reason, 'icon_file')

    def test_redirects_are_bounded_and_destinations_validated(self):
        with mock.patch('wtfutil.daydaymaputil.requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            session.get.side_effect = [SourceResponse(status=302, headers={'Location': '/real.svg'}), SourceResponse()]
            self.assertIn('web.icon=', sdk.query_from_icon(url='https://example.com/icon'))
            self.assertEqual(session.get.call_args.args[0], 'https://example.com/real.svg')
        for location in ('https://example.com/loop', 'file:///example-secret', 'https://user:example-secret@example.com/icon'):
            with self.subTest(location=location), mock.patch('wtfutil.daydaymaputil.requests.Session') as factory:
                session = factory.return_value.__enter__.return_value
                session.get.return_value = SourceResponse(status=302, headers={'Location': location})
                with self.assertRaises((ValueError, sdk.DayDayMapError)) as caught:
                    sdk.query_from_icon(url='https://example.com/icon')
                self.assertLessEqual(session.get.call_count, 6)
                self.assertNotIn('example-secret', str(caught.exception))

    def test_invalid_arguments_do_not_echo_url_or_proxy_credentials(self):
        for kwargs in ({}, {'path': 'icon', 'url': 'https://example.com/icon'},
                       {'url': 'ftp://example.com/icon'}, {'url': 'https://u:example-secret@example.com/icon'},
                       {'url': 'https://example.com:bad/icon'}, {'url': 'https://example.com/\nsecret'},
                       {'url': 'https://example.com/icon', 'proxy': 'bad://u:example-secret@localhost:88'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError) as caught:
                sdk.query_from_icon(**kwargs)
            self.assertNotIn('example-secret', str(caught.exception))
        for url in ('http://example.com', 'example.com', 'https://example.com:0', 'https://u:example-secret@example.com'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sdk.query_from_certificate(url)

    def test_transport_errors_are_sanitized(self):
        import requests
        with mock.patch('wtfutil.daydaymaputil.requests.Session') as factory:
            factory.return_value.__enter__.return_value.get.side_effect = requests.ReadTimeout('example-secret')
            with self.assertRaises(sdk.DayDayMapError) as caught:
                sdk.query_from_icon(url='https://example.com/icon')
        self.assertEqual(caught.exception.reason, 'icon_download')
        self.assertNotIn('example-secret', str(caught.exception))

    def test_certificate_closes_connection_and_manager_on_failure(self):
        with mock.patch('wtfutil.daydaymaputil.urllib3.PoolManager') as factory, \
                mock.patch('wtfutil.daydaymaputil.get_environ_proxies', return_value={}):
            manager = factory.return_value
            pool = manager.connection_from_url.return_value
            pool.proxy = None
            conn = pool._get_conn.return_value
            conn.connect.side_effect = OSError('example-secret')
            with self.assertRaises(sdk.DayDayMapError) as caught:
                sdk.query_from_certificate('https://example.com')
            self.assertEqual(caught.exception.reason, 'certificate_fetch')
            conn.close.assert_called_once()
            manager.clear.assert_called_once()
            self.assertNotIn('example-secret', str(caught.exception))

    def test_proxy_environment_and_explicit_override(self):
        from wtfutil.daydaymaputil import _proxy_for
        with mock.patch('wtfutil.daydaymaputil.get_environ_proxies', return_value={'https': 'http://127.0.0.1:9999'}):
            self.assertEqual(_proxy_for('https://example.com', None), 'http://127.0.0.1:9999')
            self.assertEqual(_proxy_for('https://example.com', 'socks5h://localhost:1080'), 'socks5h://localhost:1080')
        with mock.patch('wtfutil.daydaymaputil.get_environ_proxies', return_value={}):
            self.assertIsNone(_proxy_for('https://example.com', None))


from tests import test_daydaymap as existing


class TestPipes(existing.KeyFileCase):
    invoke = existing.TestCLI.invoke

    def test_flat_search_and_count(self):
        code, out, err = self.invoke(['-q', 'x', '--interval', '0'],
                                    api=[page([row(1)], 1)], web=[agg(1)],
                                    environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), row(1))
        self.assertEqual([json.loads(line)['type'] for line in err.splitlines()], ['count', 'summary'])
        code, out, err = self.invoke(['--count', 'x'], web=[agg(5)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['total'], 5)
        self.assertEqual(err, '')

    def test_old_subcommand_words_fail_before_key_loading_or_output_truncation(self):
        output = self.work / 'existing.jsonl'
        for argv in (['search'], ['count'], ['--count', 'count'], ['search', '-q', 'x']):
            with self.subTest(argv=argv):
                output.write_text('old', encoding='utf-8')
                code, out, err = self.invoke([*argv, '-o', str(output)],
                                             environ={'DAYDAYMAP_API_KEY': 'example-a'})
                self.assertEqual(code, 2)
                self.assertEqual(out, '')
                self.assertIn('invalid_argument', err)
                self.assertEqual(output.read_text(encoding='utf-8'), 'old')
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_quoted_old_words_still_work_as_explicit_query(self):
        code, out, _ = self.invoke(['--count', '-q', 'count'], web=[agg(2)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['query'], '(count) && ip.tag!="蜜罐"')

    def test_count_rejects_every_explicit_search_option_before_output(self):
        output = self.work / 'existing.jsonl'
        options = (['--fields', 'ip'], ['--exclude-fields', 'body'], ['--page-size', '500'],
                   ['--limit', '10000'], ['-l0'], ['--max-effort'], ['--max-effort-depth', '10'],
                   ['--format', 'jsonl'], ['--format=url'], ['--quiet'])
        for option in options:
            with self.subTest(option=option):
                output.write_text('old', encoding='utf-8')
                code, out, err = self.invoke(['--count', '-q', 'x', *option, '-o', str(output)])
                self.assertEqual(code, 2)
                self.assertEqual(out, '')
                self.assertIn('invalid_argument', err)
                self.assertEqual(output.read_text(encoding='utf-8'), 'old')
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_max_effort_depth_requires_max_effort_before_opening_output(self):
        output = self.work / 'existing.jsonl'
        output.write_text('old', encoding='utf-8')
        code, out, err = self.invoke(['-q', 'x', '--max-effort-depth', '10', '-o', str(output)],
                                     environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual(code, 2)
        self.assertEqual(out, '')
        self.assertIn('invalid_argument', err)
        self.assertEqual(output.read_text(encoding='utf-8'), 'old')
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_legacy_cli_aliases_are_removed(self):
        code, help_text, _ = self.invoke(['--help'])
        self.assertEqual(code, 0)
        for option in ('--keys-file', '--silent'):
            with self.subTest(option=option):
                self.assertNotIn(option, help_text)
                output = self.work / 'existing.jsonl'
                output.write_text('old', encoding='utf-8')
                parameters = [option, str(self.work / 'nonexistent-key-file')] if option == '--keys-file' else [option]
                code, out, _ = self.invoke(['--count', '-q', 'x', *parameters, '-o', str(output)], web=[agg(1)])
                self.assertEqual(code, 2)
                self.assertEqual(out, '')
                self.assertEqual(output.read_text(encoding='utf-8'), 'old')
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_automatic_stdin_is_incremental_and_never_calls_read(self):
        parent = self
        class Input:
            def isatty(self):
                return False
            def read(self, *_):
                raise AssertionError('stdin must be read line by line')
            def __iter__(self):
                yield '\ufeff# comment\n'
                yield '\n'
                yield 'x\n'
                parent.assertEqual(len(parent.web.calls), 1, 'first query must execute before reading next input')
                yield 'y\n'
                yield 'x\n'
        with mock.patch('sys.stdin', Input()):
            code, out, _ = self.invoke(['--count', '--interval', '0'], web=[agg(2), agg(3)])
        self.assertEqual(code, 0)
        self.assertEqual([json.loads(line)['total'] for line in out.splitlines()], [2, 3])

    def test_explicit_query_does_not_consume_implicit_stdin(self):
        stream = mock.Mock()
        stream.__iter__ = mock.Mock(side_effect=AssertionError('unexpected stdin read'))
        with mock.patch('sys.stdin', stream):
            code, _, _ = self.invoke(['--count', '-q', 'x'], web=[agg(1)])
        self.assertEqual(code, 0)

    def test_explicit_stdin_combines_with_query_and_is_consumed_once(self):
        with mock.patch('sys.stdin', io.StringIO('y\nx\n')):
            code, out, _ = self.invoke(['--count', '-q', 'x', '--query-file', '-', '--query-file', '-', '--interval', '0'],
                                       web=[agg(1), agg(2)])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 2)

    def test_template_escapes_values_instead_of_injecting_queries(self):
        value = 'a" || ip.tag="蜜罐\\end'
        with mock.patch('sys.stdin', io.StringIO(value + '\n')):
            code, out, _ = self.invoke(['--count', '--template', 'domain="{}"'], web=[agg(1)])
        self.assertEqual(code, 0)
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        self.assertEqual(json.loads(out)['query'], '(domain="' + escaped + '") && ip.tag!="蜜罐"')

    def test_invalid_templates_preserve_output(self):
        output = self.work / 'existing.jsonl'
        for template in ('domain={}', 'domain="example.com"', 'domain="{name}"', 'domain="{}', 'domain="\\{}"'):
            with self.subTest(template=template):
                output.write_text('old', encoding='utf-8')
                code, _, _ = self.invoke(['--count', '-q', 'example.com', '--template', template, '-o', str(output)])
                self.assertEqual(code, 2)
                self.assertEqual(output.read_text(), 'old')
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_source_only_input_and_filtered_count(self):
        icon = self.work / 'icon.svg'
        icon.write_bytes(ICON)
        code, out, _ = self.invoke(['--count', '--icon-file', str(icon), '--is-china', '--is-domain'], web=[agg(1)])
        self.assertEqual(code, 0)
        query = json.loads(out)['query']
        self.assertIn('web.icon="' + hashlib.md5(ICON).hexdigest() + '"', query)
        self.assertIn('ip.tag!="蜜罐"', query)
        self.assertIn('ip.province!="澳门"', query)
        self.assertIn('is_domain="true"', query)

    def test_remote_sources_resolved_once_and_combined_with_each_query(self):
        with mock.patch('wtfutil.daydaymap.query_from_icon', return_value='web.icon="example-md5"') as icon, \
                mock.patch('wtfutil.daydaymap.query_from_certificate', return_value='cert.md5="example-md5"') as cert:
            code, out, _ = self.invoke(['--count', '-q', 'x', '-q', 'y', '--icon-url', 'https://example.com/icon',
                                       '--cert-url', 'https://example.com', '--proxy', 'http://127.0.0.1:8080', '--interval', '0'],
                                      web=[agg(1), agg(2)])
        self.assertEqual(code, 0)
        icon.assert_called_once()
        cert.assert_called_once()
        self.assertEqual(icon.call_args.kwargs['proxy'], 'http://127.0.0.1:8080')
        self.assertEqual(cert.call_args.kwargs['proxy'], 'http://127.0.0.1:8080')
        self.assertTrue(all('web.icon=' in json.loads(line)['query'] and 'cert.md5=' in json.loads(line)['query']
                            for line in out.splitlines()))

    def test_source_failure_and_samefile_do_not_truncate_output(self):
        icon = self.work / 'icon.svg'
        icon.write_bytes(ICON)
        output = self.work / 'existing.jsonl'
        output.write_text('old', encoding='utf-8')
        with mock.patch('wtfutil.daydaymap.query_from_icon', side_effect=sdk.DayDayMapError('icon_download')):
            code, _, _ = self.invoke(['--count', '--icon-url', 'https://example.com/icon', '-o', str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(output.read_text(), 'old')
        code, _, _ = self.invoke(['--count', '--icon-file', str(icon), '-o', str(icon)])
        self.assertEqual(code, 2)
        self.assertEqual(icon.read_bytes(), ICON)
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_empty_or_missing_input_preserves_existing_output(self):
        output = self.work / 'existing.jsonl'
        output.write_text('old', encoding='utf-8')
        with mock.patch('sys.stdin', io.StringIO('  \n# no queries\n')):
            code, _, _ = self.invoke(['--count', '-o', str(output)])
        self.assertEqual(code, 2)
        self.assertEqual(output.read_text(), 'old')
        code, _, _ = self.invoke(['--count', '-q', 'x', '--query-file', str(self.work / 'missing'), '-o', str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(output.read_text(), 'old')

    def test_dash_output_and_quiet_keep_stdout_clean(self):
        code, out, err = self.invoke(['x', '--format', 'url', '-o', '-', '--quiet', '--interval', '0'],
                                    api=[page([row(1)], 1)], web=[agg(1)], environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual((code, out, err), (0, 'http://192.0.2.1\n', ''))

    def test_help_describes_current_cli_without_migration_notes(self):
        code, help_text, _ = self.invoke(['--help'])
        self.assertEqual(code, 0)
        self.assertIn('--count', help_text)
        self.assertNotIn('旧', help_text)
        self.assertNotIn('移除', help_text)
        for word in ('search', 'count'):
            with self.subTest(word=word):
                code, _, error_text = self.invoke([word])
                self.assertEqual(code, 2)
                self.assertNotIn('旧', error_text)
                self.assertNotIn('移除', error_text)

    def test_no_dry_run_and_mandatory_honeypot_filter_has_no_switch(self):
        code, out, _ = self.invoke(['--help'])
        self.assertEqual(code, 0)
        self.assertIn('--count', out)
        self.assertNotIn('--dry-run', out)
        self.assertNotIn('--include-honeypot', out)
        self.assertNotIn('{count,search}', out)

    def test_redirected_stdin_cannot_be_overwritten(self):
        for explicit in (False, True):
            with self.subTest(explicit_stdin=explicit):
                query_file = self.work / 'stdin.txt'
                query_file.write_text('x\ny\n', encoding='utf-8')
                argv = ['--count', '-o', str(query_file)] + (['-q', 'z', '--query-file', '-'] if explicit else [])
                with query_file.open(encoding='utf-8') as stream, mock.patch('sys.stdin', stream):
                    code, _, _ = self.invoke(argv, web=[agg(1), agg(2)])
                self.assertEqual(code, 2)
                self.assertEqual(query_file.read_text(), 'x\ny\n')
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_invalid_utf8_input_reports_io_error_and_preserves_output(self):
        source = self.work / 'queries.txt'
        source.write_bytes(b'\xff')
        output = self.work / 'output.jsonl'
        output.write_text('old', encoding='utf-8')
        code, _, err = self.invoke(['--count', '--query-file', str(source), '-o', str(output)])
        self.assertEqual(code, 1)
        self.assertIn('io_error', err)
        self.assertEqual(output.read_text(), 'old')

    def test_stdout_permission_error_is_not_a_successful_broken_pipe(self):
        from wtfutil.daydaymap import main
        output = mock.Mock()
        output.write.side_effect = PermissionError('example-secret')
        errors = io.StringIO()
        api, web = FakeSession([page([row(1)], 2)]), FakeSession([agg(2)])
        with mock.patch.dict(os.environ, {'DAYDAYMAP_API_KEY': 'example-a'}, clear=True), \
                mock.patch('wtfutil.daydaymaputil.requests_session', side_effect=[api, web]), \
                mock.patch('sys.stdout', output), mock.patch('sys.stderr', errors):
            code = main(['x', '--quiet', '--page-size', '1', '--interval', '0'])
        self.assertEqual(code, 1)
        self.assertIn('io_error', errors.getvalue())
        self.assertNotIn('example-secret', errors.getvalue())
        self.assertEqual(len(api.calls), 1)

    def test_broken_pipe_stops_pagination_without_error_output(self):
        from wtfutil.daydaymap import main
        api, web = FakeSession([page([row(1)], 3)]), FakeSession([agg(3)])
        output = mock.Mock()
        output.write.side_effect = BrokenPipeError
        errors = io.StringIO()
        with mock.patch.dict(os.environ, {'DAYDAYMAP_API_KEY': 'example-a'}, clear=True), \
                mock.patch('wtfutil.daydaymaputil.requests_session', side_effect=[api, web]), \
                mock.patch('sys.stdout', output), mock.patch('sys.stderr', errors):
            code = main(['x', '--page-size', '1', '--quiet', '--interval', '0'])
        self.assertEqual(code, 0)
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(errors.getvalue(), '')
        self.assertTrue(api.closed)
        self.assertTrue(web.closed)


if __name__ == '__main__':
    unittest.main()
