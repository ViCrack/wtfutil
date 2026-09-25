"""DayDayMap SDK / CLI regression tests; no paid requests or real credentials."""
from __future__ import annotations

import base64
import inspect
import io
import json
import os
import tempfile
import threading
import traceback
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import requests

from wtfutil.daydaymaputil import DayDayMapClient, DayDayMapError, _KeyPool, load_keys


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def filtered(query):
    return f'({query}) && ip.tag!="蜜罐"'


def ok(data):
    return FakeResponse({'code': 200, 'msg': 'success', 'data': data})


def error(code):
    return FakeResponse({'code': code, 'msg': 'example-secret-server-message', 'data': {}})


def agg(total=6):
    return ok({'port': [{'name': 80, 'value': total}], 'ip_num': 2})


def row(n, **extra):
    return {'ip': f'192.0.2.{n}', 'port': 80, 'protocol': 'tcp', 'domain': '', 'service': 'http',
            'url': f'http://192.0.2.{n}', **extra}


def page(items, total):
    return ok({'list': items, 'total': total})


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append({'url': url, **kwargs})
        if not self.responses:
            raise AssertionError('unexpected HTTP request')
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def close(self):
        self.closed = True


class ClientCase(unittest.TestCase):
    def make_client(self, api=(), web=(), keys=('example-a', 'example-b'), **kwargs):
        self.api = FakeSession(api)
        self.web = FakeSession(web)
        return DayDayMapClient(keys, session=self.api, web_session=self.web, interval=0, retry_backoff=0, **kwargs)


class TestCount(ClientCase):
    def test_count_strategy_options_are_removed_from_sdk(self):
        parameters = inspect.signature(DayDayMapClient.count).parameters
        self.assertNotIn('exact', parameters)
        self.assertNotIn('free_only', parameters)
        client = self.make_client()
        for option in ('exact', 'free_only'):
            with self.subTest(option=option), self.assertRaises(TypeError):
                client.count('x', **{option: True})
        self.assertEqual(self.web.calls + self.api.calls, [])

    def test_aggregate_is_anonymous_and_distinguishes_ip_count(self):
        client = self.make_client(web=[agg(394)])
        result = client.count('domain="example.com"')
        self.assertEqual((result.total, result.estimated, result.source, result.ip_count), (394, True, 'aggregate', 2))
        self.assertEqual(self.api.calls, [])
        self.assertNotIn('api-key', self.web.calls[0]['headers'])
        self.assertEqual(base64.b64decode(self.web.calls[0]['json']['keyword']).decode(), filtered('domain="example.com"'))
        self.assertEqual(result.to_dict()['query'], filtered('domain="example.com"'))

    def test_estimate_maximum_includes_other_and_zero_is_valid(self):
        for data, total in [
            ({'port': [{'value': 2}, {'name': '其他', 'value': 3}], 'service': [{'count': 7}]}, 7),
            ({'port': [{'value': 0}], 'ip_num': 100}, 0),
            ({'port': [{'count': 0, 'value': 999}]}, 0),
        ]:
            with self.subTest(data=data):
                client = self.make_client(web=[ok(data)])
                self.assertEqual(client.count('port="80"').total, total)
                self.assertEqual(self.api.calls, [])

    def test_unusable_aggregate_falls_back_to_one_row(self):
        for data in ({}, {'ip_num': 12}, {'port': []}, {'port': [{'value': 'bad'}]}, {'port': [{'value': -2}]}):
            with self.subTest(data=data):
                client = self.make_client(api=[page([row(1)], 12)], web=[ok(data)])
                result = client.count('port="80"')
                self.assertEqual((result.total, result.estimated, result.source), (12, False, 'api'))
                body = self.api.calls[0]['json']
                self.assertEqual((body['page'], body['page_size'], body['fields']), (1, 1, 'ip'))

    def test_aggregate_transport_error_can_fallback(self):
        client = self.make_client(api=[page([row(1)], 12)], web=[requests.ReadTimeout('example-secret')])
        self.assertEqual(client.count('port="80"').total, 12)

    def test_aggregate_unavailable_without_keys_never_uses_api(self):
        client = self.make_client(web=[ok({})], keys=())
        with self.assertRaises(DayDayMapError) as caught:
            client.count('port="80"')
        self.assertEqual(caught.exception.reason, 'aggregate_unavailable')
        self.assertEqual(self.api.calls, [])

    def test_api_fallback_requires_unusable_aggregate(self):
        client = self.make_client(api=[page([row(1)], 3)], web=[ok({})])
        result = client.count('port="80"')
        self.assertFalse(result.estimated)
        self.assertEqual(len(self.web.calls), 1)
        self.assertEqual(len(self.api.calls), 1)

    def test_no_key_needed_when_aggregate_works(self):
        client = self.make_client(web=[agg()], keys=())
        self.assertEqual(client.count('port="80"').total, 6)

    def test_invalid_query_rejected_locally(self):
        client = self.make_client()
        with self.assertRaises(ValueError):
            client.count('')
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_syntax_error_does_not_fall_back_or_rotate(self):
        client = self.make_client(web=[error(470)])
        with self.assertRaises(DayDayMapError) as caught:
            client.count('bad syntax')
        self.assertEqual(caught.exception.reason, 'invalid_query')
        self.assertEqual(self.api.calls, [])
        client = self.make_client(api=[error(2002)], web=[ok({})])
        with self.assertRaises(DayDayMapError):
            client.count('bad syntax')
        self.assertEqual(len(self.api.calls), 1)
        self.assertEqual(client.available_keys, 2)

    def test_count_api_limit_is_not_fabricated_as_total(self):
        client = self.make_client(api=[error(2005)], web=[ok({})])
        with self.assertRaises(DayDayMapError) as caught:
            client.count('x')
        self.assertEqual(caught.exception.reason, 'result_limit')
        self.assertEqual(client.available_keys, 2)

    def test_invalid_total_or_json_raises_sanitized_error(self):
        for response in [page([], True), page([], -1), page([], 'bad'), ok([]), FakeResponse(ValueError('example-secret'))]:
            with self.subTest(response=response):
                client = self.make_client(api=[response], web=[ok({})])
                with self.assertRaises(DayDayMapError) as caught:
                    client.count('x')
                text = ''.join(traceback.format_exception(caught.exception))
                self.assertNotIn('example-secret', text)
                self.assertNotIn('example-a', text)


class KeyFileCase(ClientCase):
    def setUp(self):
        super().setUp()
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.work, self.home = directory / 'work', directory / 'home'
        self.work.mkdir()
        (self.work / 'resource').mkdir()
        self.home.mkdir()
        self.enterContext(mock.patch('pathlib.Path.cwd', return_value=self.work))
        self.enterContext(mock.patch('pathlib.Path.home', return_value=self.home))


class TestKeys(KeyFileCase):
    def test_default_file_loads_without_explicit_path(self):
        path = self.work / 'daydaymap_keys.txt'
        path.write_text('example-default\n', encoding='utf-8')
        self.assertEqual(load_keys(), ['example-default'])
        with DayDayMapClient.from_key_file(session=FakeSession([]), web_session=FakeSession([])) as client:
            self.assertEqual(client.available_keys, 1)

    def test_no_default_file_returns_empty_keys(self):
        self.assertEqual(load_keys(), [])
        with DayDayMapClient.from_key_file(session=FakeSession([]), web_session=FakeSession([])) as client:
            self.assertEqual(client.available_keys, 0)

    def test_explicit_missing_file_does_not_use_default(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-default\n', encoding='utf-8')
        with self.assertRaises(DayDayMapError) as caught:
            load_keys(self.work / 'missing.txt')
        self.assertEqual(caught.exception.reason, 'key_file')

    def test_key_file_bom_comments_order_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'keys.txt'
            path.write_text('\ufeff# comment\n example-a \n\nexample-b\nexample-a\n', encoding='utf-8')
            self.assertEqual(load_keys(path), ['example-a', 'example-b'])
            with DayDayMapClient.from_key_file(path, session=FakeSession([]), web_session=FakeSession([])) as client:
                self.assertEqual(client.available_keys, 2)

    def test_invalid_key_file_error_does_not_echo_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'keys.txt'
            path.write_text('example-secret invalid value', encoding='utf-8')
            with self.assertRaises(ValueError) as caught:
                load_keys(path)
            self.assertNotIn('example-secret', str(caught.exception))

    def test_exhaustion_retries_same_request_with_next_key(self):
        for code in (2001, 2003, 2004):
            with self.subTest(code=code):
                client = self.make_client(api=[error(code), page([row(1)], 1)], web=[agg(1)])
                self.assertEqual(list(client.search('x')), [row(1)])
                self.assertEqual([call['headers']['api-key'] for call in self.api.calls], ['example-a', 'example-b'])
                self.assertEqual([call['json']['page'] for call in self.api.calls], [1, 1])
                self.assertEqual(client.available_keys, 1)

    def test_exhausted_pool_is_finite_and_does_not_retry_disabled_keys(self):
        client = self.make_client(api=[error(2004), error(2004)], web=[agg()])
        with self.assertRaises(DayDayMapError) as caught:
            list(client.search('x'))
        self.assertEqual(caught.exception.reason, 'quota_exhausted')
        self.assertEqual(len(self.api.calls), 2)
        self.assertEqual(client.available_keys, 0)
        self.assertNotIn('example-secret', str(caught.exception))

    def test_pool_waits_for_leased_key_instead_of_exhausting(self):
        pool = _KeyPool(['example-a'])
        key = pool.acquire()
        started = threading.Event()
        def acquire():
            started.set()
            return pool.acquire()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(acquire)
            self.assertTrue(started.wait(1))
            self.assertFalse(future.done())
            pool.release(key)
            self.assertEqual(future.result(timeout=2), 'example-a')
        pool.discard('example-a')
        self.assertIsNone(pool.acquire())

    def test_sessions_are_closed_only_if_owned(self):
        client = self.make_client()
        client.close()
        self.assertFalse(self.api.closed)
        self.assertFalse(self.web.closed)
        with mock.patch('wtfutil.daydaymaputil.requests_session', side_effect=[FakeSession([]), FakeSession([])]) as factory:
            with DayDayMapClient() as internal:
                api, web = internal._session, internal._web_session
            self.assertTrue(api.closed)
            self.assertTrue(web.closed)
            self.assertTrue(all(call.kwargs['verify'] for call in factory.call_args_list))
            self.assertTrue(all(call.kwargs['max_retries'] == 0 for call in factory.call_args_list))


class TestRetry(ClientCase):
    def test_429_retries_same_key_then_success(self):
        client = self.make_client(api=[FakeResponse({}, 429, {'Retry-After': '0'}), page([], 0)],
                                  web=[ok({})], max_retries=1)
        self.assertEqual(client.count('x').total, 0)
        self.assertEqual([call['headers']['api-key'] for call in self.api.calls], ['example-a', 'example-a'])

    def test_429_is_bounded_does_not_rotate(self):
        client = self.make_client(api=[FakeResponse({}, 429)] * 2, web=[ok({})], max_retries=1)
        with self.assertRaises(DayDayMapError) as caught:
            client.count('x')
        self.assertEqual(caught.exception.reason, 'rate_limited')
        self.assertEqual(len(self.api.calls), 2)
        self.assertEqual(client.available_keys, 2)

    def test_web_rate_limit_does_not_trigger_paid_fallback(self):
        client = self.make_client(web=[FakeResponse({}, 429)], max_retries=0)
        with self.assertRaises(DayDayMapError) as caught:
            client.count('x')
        self.assertEqual(caught.exception.reason, 'rate_limited')
        self.assertEqual(self.api.calls, [])

    def test_read_timeout_does_not_repeat_potentially_billed_request(self):
        client = self.make_client(api=[requests.ReadTimeout('example-secret-key')], web=[ok({})])
        with self.assertRaises(DayDayMapError) as caught:
            client.count('x')
        self.assertEqual(len(self.api.calls), 1)
        self.assertEqual(client.available_keys, 2)
        self.assertNotIn('example-secret', ''.join(traceback.format_exception(caught.exception)))

    def test_connect_timeout_and_2006_retry_bounded(self):
        for response in (requests.ConnectTimeout('example-secret'), error(2006)):
            with self.subTest(response=response):
                client = self.make_client(api=[response, page([], 0)], web=[ok({})], max_retries=1)
                self.assertEqual(client.count('x').total, 0)
                self.assertEqual(len(self.api.calls), 2)

    def test_keyed_redirect_is_not_followed(self):
        client = self.make_client(api=[FakeResponse({}, 302)], web=[ok({})])
        with self.assertRaises(DayDayMapError):
            client.count('x')
        self.assertFalse(self.api.calls[0]['allow_redirects'])


class TestSearch(ClientCase):
    def test_page_rotation_and_original_query(self):
        query = '(title="示例 A" || port="80")'
        client = self.make_client(api=[page([row(1), row(2)], 3), page([row(3)], 3)], web=[agg(3)])
        self.assertEqual(list(client.search(query, page_size=2)), [row(1), row(2), row(3)])
        self.assertEqual([c['headers']['api-key'] for c in self.api.calls], ['example-a', 'example-b'])
        self.assertEqual([c['json']['page'] for c in self.api.calls], [1, 2])
        self.assertTrue(all(base64.b64decode(c['json']['keyword']).decode() == filtered(query) for c in self.api.calls))
        self.assertEqual(client.last_summary.total, 3)
        self.assertFalse(client.last_summary.estimated)
        self.assertFalse(client.last_summary.truncated)

    def test_failed_preflight_does_not_probe_paid_count(self):
        client = self.make_client(api=[page([row(1)], 1)], web=[ok({})])
        self.assertEqual(list(client.search('x', page_size=12)), [row(1)])
        self.assertEqual([c['json']['page_size'] for c in self.api.calls], [12])

    def test_estimated_zero_does_not_skip_real_search(self):
        client = self.make_client(api=[page([row(1)], 1)], web=[agg(0)])
        self.assertEqual(list(client.search('x')), [row(1)])

    def test_fields_precedence_and_projection(self):
        client = self.make_client(api=[page([row(1)], 1)], web=[agg(1)])
        self.assertEqual(list(client.search('x', fields=('ip', 'port'), exclude_fields=('body',))), [{'ip': '192.0.2.1', 'port': 80}])
        self.assertEqual(self.api.calls[0]['json']['fields'], 'ip,port')
        self.assertNotIn('exclude_fields', self.api.calls[0]['json'])

    def test_limit_reduces_first_page_width(self):
        client = self.make_client(api=[page([row(1), row(2)], 10)], web=[agg(10)])
        self.assertEqual(len(list(client.search('x', page_size=500, limit=2))), 2)
        self.assertEqual(self.api.calls[0]['json']['page_size'], 2)
        self.assertTrue(client.last_summary.limit_reached)
        self.assertTrue(client.last_summary.truncated)

    def test_fixed_page_width_does_not_shift_offsets(self):
        client = self.make_client(api=[page([row(1), row(2)], 10), page([row(3), row(4)], 10)], web=[agg(10)])
        self.assertEqual(len(list(client.search('x', page_size=2, limit=3))), 3)
        self.assertEqual([c['json']['page_size'] for c in self.api.calls], [2, 2])
        self.assertEqual(client.last_summary.fetched, 4)

    def test_2005_reports_truncation_not_key_exhaustion(self):
        client = self.make_client(api=[error(2005)], web=[agg(20000)])
        self.assertEqual(list(client.search('x')), [])
        self.assertTrue(client.last_summary.truncated)
        self.assertEqual(client.last_summary.reason, 'result_limit')
        self.assertEqual(client.available_keys, 2)

    def test_short_or_empty_page_before_total_is_incomplete(self):
        for items in ([row(1)], []):
            with self.subTest(items=items):
                client = self.make_client(api=[page(items, 5)], web=[agg(5)])
                stream = client.search('x', page_size=2)
                seen = []
                with self.assertRaises(DayDayMapError) as caught:
                    for item in stream:
                        seen.append(item)
                self.assertEqual(seen, items)
                self.assertEqual(caught.exception.reason, 'incomplete_page')
                self.assertTrue(client.last_summary.truncated)

    def test_zero_limit_means_no_local_cap(self):
        client = self.make_client(api=[page([row(1), row(2)], 3), page([row(3)], 3)], web=[agg(3)])
        self.assertEqual(len(list(client.search('x', page_size=2, limit=0))), 3)

    def test_invalid_limits_rejected_before_http(self):
        client = self.make_client()
        for kwargs in ({'page_size': 0}, {'page_size': 10001}, {'limit': -1}, {'max_effort_depth': 0}, {'page_size': True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    list(client.search('x', **kwargs))
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_max_effort_skips_root_wraps_query_and_deduplicates_before_projection(self):
        buckets = {'port': [{'name': 80, 'value': 6000}, {'name': 443, 'value': 6000}]}
        client = self.make_client(api=[page([row(1), row(2)], 2), page([row(2), row(3)], 2)], web=[ok(buckets)])
        items = list(client.search('title="A" || title="B"', fields=('ip',), max_effort=True))
        self.assertEqual(items, [{'ip': '192.0.2.1'}, {'ip': '192.0.2.2'}, {'ip': '192.0.2.3'}])
        queries = [base64.b64decode(c['json']['keyword']).decode() for c in self.api.calls]
        expected = '(' + filtered('title="A" || title="B"') + ') && ('
        self.assertTrue(all(q.startswith(expected) and q.count('ip.tag!="蜜罐"') == 1 for q in queries))
        self.assertEqual(len(queries), 2)
        self.assertIn('port', self.api.calls[0]['json']['fields'])
        self.assertTrue(client.last_summary.truncated)
        self.assertEqual(client.last_summary.reason, 'best_effort')

    def test_same_ip_different_ports_survive_projected_output(self):
        client = self.make_client(api=[page([row(1), row(1, port=443)], 2)], web=[agg(2)])
        items = list(client.search('x', fields=('ip',), max_effort=True))
        self.assertEqual(len(items), 2)

    def test_cap_never_requests_past_window(self):
        client = self.make_client(api=[page([row(1), row(2)], 10), page([row(3), row(4)], 10)], web=[agg(10)])
        with mock.patch('wtfutil.daydaymaputil.API_LIMIT', 4):
            self.assertEqual(len(list(client.search('x', page_size=2, limit=0))), 4)
        self.assertTrue(client.last_summary.truncated)
        self.assertEqual(len(self.api.calls), 2)


class TestCLI(KeyFileCase):
    def invoke(self, argv, *, api=(), web=(), environ=None):
        from wtfutil.daydaymap import main
        self.api = FakeSession(api)
        self.web = FakeSession(web)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, environ or {}, clear=True), \
                mock.patch('wtfutil.daydaymaputil.requests_session', side_effect=[self.api, self.web]), \
                mock.patch('sys.stdout', stdout), mock.patch('sys.stderr', stderr):
            try:
                result = main(argv)
            except SystemExit as exc:
                result = exc.code
        return result, stdout.getvalue(), stderr.getvalue()

    def test_free_count_requires_no_key(self):
        code, out, err = self.invoke(['--count', 'port="80"'], web=[agg(9)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['total'], 9)
        self.assertEqual(self.api.calls, [])
        self.assertNotIn('example-a', err)

    def test_query_and_key_files_bom_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            keys = Path(directory) / 'keys.txt'
            queries = Path(directory) / 'queries.txt'
            keys.write_text('\ufeffexample-a\nexample-b\n', encoding='utf-8')
            queries.write_text('\ufeff# comment\nx\ny\nx\n', encoding='utf-8')
            code, out, _ = self.invoke(['--count', '-q', 'x', '--query-file', str(queries),
                                        '--key-file', str(keys), '--interval', '0'],
                                       api=[page([], 1), page([], 2)], web=[ok({}), ok({})])
        self.assertEqual(code, 0)
        self.assertEqual([json.loads(line)['query'] for line in out.splitlines()], [filtered('x'), filtered('y')])
        self.assertEqual([call['headers']['api-key'] for call in self.api.calls], ['example-a', 'example-b'])

    def test_search_jsonl_and_summary_are_separate(self):
        code, out, err = self.invoke(['x', '--interval', '0'], api=[page([row(1), row(2)], 2)],
                                    web=[agg(2)], environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual(code, 0)
        self.assertEqual([json.loads(line) for line in out.splitlines()], [row(1), row(2)])
        summary = json.loads(err.splitlines()[-1])
        self.assertEqual(summary['returned'], 2)
        self.assertFalse(summary['truncated'])

    def test_short_page_keeps_partial_output_and_nonzero_status(self):
        code, out, err = self.invoke(['x', '--page-size', '2', '--interval', '0'],
                                    api=[page([row(1)], 3)], web=[agg(3)],
                                    environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out), row(1))
        self.assertIn('incomplete_page', err)
        self.assertNotIn('example-a', err)

    def test_exhausted_keys_exit_three_and_do_not_print_server_message(self):
        code, out, err = self.invoke(['--count', 'x', '--interval', '0'], api=[error(2004)], web=[ok({})],
                                    environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual(code, 3)
        self.assertEqual(out, '')
        self.assertIn('quota_exhausted', err)
        self.assertNotIn('example-a', err)
        self.assertNotIn('example-secret', err)

    def test_removed_count_flags_are_rejected_without_network(self):
        for option in ('--exact', '--free-only'):
            with self.subTest(option=option):
                code, _, _ = self.invoke(['--count', 'x', option], api=[page([], 0)], web=[agg(0)],
                                        environ={'DAYDAYMAP_API_KEY': 'example-a'})
                self.assertEqual(code, 2)
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_count_help_omits_removed_flags(self):
        code, out, _ = self.invoke(['--count', '--help'])
        self.assertEqual(code, 0)
        self.assertNotIn('--exact', out)
        self.assertNotIn('--free-only', out)

    def test_output_file_and_url_mode_with_ipv6(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'urls.txt'
            asset = row(1, ip='2001:db8::1', port=8443, url='', service='https')
            code, out, _ = self.invoke(['x', '--format', 'url', '-o', str(output), '--interval', '0'],
                                      api=[page([asset], 1)], web=[agg(1)],
                                      environ={'DAYDAYMAP_API_KEY': 'example-a'})
            text = output.read_text(encoding='utf-8')
        self.assertEqual((code, out, text), (0, '', 'https://[2001:db8::1]:8443\n'))

    def test_invalid_options_fail_without_network(self):
        for argv in (['x', '--limit', '-1'], ['x', '--page-size', '10001'],
                     ['--count', 'x', '--timeout', 'nan'], ['--count']):
            with self.subTest(argv=argv):
                code, _, _ = self.invoke(argv)
                self.assertEqual(code, 2)
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_explicit_key_file_overrides_environment_and_defaults(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-default\n', encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            keys = Path(directory) / 'keys.txt'
            keys.write_text('example-file-key\n', encoding='utf-8')
            code, _, _ = self.invoke(['--count', 'x', '--key-file', str(keys), '--interval', '0'],
                                    api=[page([], 0)], web=[ok({})],
                                    environ={'DAYDAYMAP_API_KEY': 'example-env-key',
                                             'DAYDAYMAP_KEY_FILE': str(self.work / 'not-used.txt')})
        self.assertEqual(code, 0)
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-file-key')

    def test_working_directory_key_file_has_priority(self):
        for path, key in ((self.work / 'daydaymap_keys.txt', 'example-local'),
                          (self.work / 'resource' / 'daydaymap_keys.txt', 'example-resource'),
                          (self.home / 'daydaymap_keys.txt', 'example-home')):
            path.write_text(key + '\n', encoding='utf-8')
        code, _, _ = self.invoke(['x', '--interval', '0'], api=[page([], 0)], web=[agg(0)])
        self.assertEqual(code, 0)
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-local')

    def test_resource_key_file_precedes_home(self):
        (self.work / 'resource' / 'daydaymap_keys.txt').write_text('example-resource\n', encoding='utf-8')
        (self.home / 'daydaymap_keys.txt').write_text('example-home\n', encoding='utf-8')
        code, _, _ = self.invoke(['x', '--interval', '0'], api=[page([], 0)], web=[agg(0)])
        self.assertEqual(code, 0)
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-resource')

    def test_home_key_file_is_used(self):
        (self.home / 'daydaymap_keys.txt').write_text('example-home\n', encoding='utf-8')
        code, _, _ = self.invoke(['x', '--interval', '0'], api=[page([], 0)], web=[agg(0)])
        self.assertEqual(code, 0)
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-home')

    def test_environment_file_precedes_environment_key_and_defaults(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-default\n', encoding='utf-8')
        path = self.home / 'configured.txt'
        path.write_text('example-configured\n', encoding='utf-8')
        code, _, _ = self.invoke(['x', '--interval', '0'], api=[page([], 0)], web=[agg(0)],
                                environ={'DAYDAYMAP_KEY_FILE': str(path), 'DAYDAYMAP_API_KEY': 'example-env'})
        self.assertEqual(code, 0)
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-configured')

    def test_environment_key_precedes_default_file(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-default invalid\n', encoding='utf-8')
        code, _, _ = self.invoke(['x', '--interval', '0'], api=[page([], 0)], web=[agg(0)],
                                environ={'DAYDAYMAP_API_KEY': 'example-env'})
        self.assertEqual(code, 0)
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-env')

    def test_count_uses_free_aggregate_before_discovered_keys(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-default\n', encoding='utf-8')
        code, out, _ = self.invoke(['--count', 'x'], web=[agg(6)])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)['estimated'])
        self.assertEqual(self.api.calls, [])
        self.assertNotIn('api-key', self.web.calls[0]['headers'])

    def test_count_can_fallback_with_discovered_keys(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-default\n', encoding='utf-8')
        code, out, _ = self.invoke(['--count', 'x', '--interval', '0'], web=[ok({})], api=[page([], 8)])
        self.assertEqual(code, 0)
        self.assertEqual((json.loads(out)['total'], json.loads(out)['source']), (8, 'api'))
        self.assertEqual(self.api.calls[0]['headers']['api-key'], 'example-default')
        self.assertEqual(self.api.calls[0]['json']['page_size'], 1)

    def test_no_default_keys_and_failed_aggregate_do_not_call_api(self):
        code, _, err = self.invoke(['--count', 'x'], web=[ok({})])
        self.assertEqual(code, 1)
        self.assertIn('aggregate_unavailable', err)
        self.assertEqual(self.api.calls, [])

    def test_empty_default_file_does_not_fall_through_to_home(self):
        (self.work / 'daydaymap_keys.txt').write_text('# empty\n', encoding='utf-8')
        (self.home / 'daydaymap_keys.txt').write_text('example-home\n', encoding='utf-8')
        code, _, _ = self.invoke(['x'])
        self.assertEqual(code, 2)
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_invalid_default_file_does_not_fall_through_to_home(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-secret invalid\n', encoding='utf-8')
        (self.home / 'daydaymap_keys.txt').write_text('example-home\n', encoding='utf-8')
        code, _, err = self.invoke(['x'])
        self.assertEqual(code, 2)
        self.assertIn('invalid_argument', err)
        self.assertNotIn('example-secret', err)
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_unreadable_default_file_does_not_fall_through(self):
        (self.work / 'daydaymap_keys.txt').write_text('example-local\n', encoding='utf-8')
        (self.home / 'daydaymap_keys.txt').write_text('example-home\n', encoding='utf-8')
        with mock.patch.object(Path, 'read_text', side_effect=PermissionError):
            code, _, err = self.invoke(['x'])
        self.assertEqual(code, 1)
        self.assertIn('key_file', err)
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_keyboard_interrupt_preserves_output_and_returns_130(self):
        code, out, err = self.invoke(['x', '--page-size', '1', '--interval', '0'],
                                    api=[page([row(1)], 2), KeyboardInterrupt()], web=[agg(2)],
                                    environ={'DAYDAYMAP_API_KEY': 'example-a'})
        self.assertEqual(code, 130)
        self.assertEqual(json.loads(out), row(1))
        self.assertIn('interrupted', err)

    def test_field_arguments_preserve_projection_and_url_requirements(self):
        cases = (
            ('jsonl', '--fields', ' ip , port,ip ', 'fields', 'ip,port'),
            ('url', '--fields', ' ip ,ip ', 'fields', 'ip,url,domain,port,service'),
            ('url', '--exclude-fields', ' url, ip,body,body ', 'exclude_fields', 'body'),
        )
        for output_format, option, value, payload_name, expected in cases:
            with self.subTest(format=output_format, option=option):
                code, out, _ = self.invoke(
                    ['x', '--format', output_format, option, value, '--interval', '0'],
                    api=[page([row(1)], 1)], web=[agg(1)],
                    environ={'DAYDAYMAP_API_KEY': 'example-a'},
                )
                self.assertEqual(code, 0)
                self.assertEqual(self.api.calls[0]['json'][payload_name], expected)
                if output_format == 'jsonl':
                    self.assertEqual(json.loads(out), {'ip': '192.0.2.1', 'port': 80})
                else:
                    self.assertEqual(out, 'http://192.0.2.1\n')

    def test_invalid_field_arguments_preserve_existing_output(self):
        cases = (
            ('--fields', 'ip,,port', 'jsonl'),
            ('--fields', 'ip,bad field', 'url'),
            ('--exclude-fields', 'body,,title', 'jsonl'),
            ('--exclude-fields', 'body,', 'url'),
        )
        output = self.work / 'existing.jsonl'
        for option, value, output_format in cases:
            with self.subTest(option=option, value=value, format=output_format):
                output.write_text('existing-data\n', encoding='utf-8')
                code, _, _ = self.invoke(
                    ['x', option, value, '--format', output_format, '-o', str(output)],
                    environ={'DAYDAYMAP_API_KEY': 'example-a'},
                )
                self.assertEqual(code, 2)
                self.assertEqual(output.read_text(encoding='utf-8'), 'existing-data\n')
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_output_cannot_overwrite_hardlinked_inputs(self):
        for source_kind in ('explicit_key', 'discovered_key', 'query'):
            with self.subTest(source=source_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ('daydaymap_keys.txt' if source_kind == 'discovered_key' else 'input.txt')
                output = root / 'output.jsonl'
                text = 'port="80"\n' if source_kind == 'query' else 'example-file-key\n'
                source.write_text(text, encoding='utf-8')
                try:
                    os.link(source, output)
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f'hard links unavailable: {exc}')
                self.assertNotEqual(source.resolve(), output.resolve())
                self.assertTrue(source.samefile(output))
                argv = ['--count', '-o', str(output)]
                if source_kind == 'explicit_key':
                    argv.extend(['x', '--key-file', str(source)])
                elif source_kind == 'query':
                    argv.extend(['--query-file', str(source)])
                else:
                    argv.append('x')
                with mock.patch('pathlib.Path.cwd', return_value=root):
                    code, _, _ = self.invoke(argv, web=[agg(1)])
                self.assertEqual(source.read_text(encoding='utf-8'), text)
                self.assertEqual(code, 2)
                self.assertEqual(self.api.calls + self.web.calls, [])

    def test_dash_named_key_file_is_not_treated_as_query_stdin(self):
        keyfile = self.work / '-'
        keyfile.write_text('example-dash-key\n', encoding='utf-8')
        original_directory = os.getcwd()
        try:
            os.chdir(self.work)
            code, _, _ = self.invoke(['--count', 'x', '--key-file', '-', '-o', '-'], web=[agg(1)])
        finally:
            os.chdir(original_directory)
        self.assertEqual(keyfile.read_text(encoding='utf-8'), 'example-dash-key\n')
        self.assertEqual(code, 0)
        self.assertEqual(len(self.web.calls), 1)
        self.assertEqual(self.api.calls, [])

    def test_missing_required_keys_does_not_truncate_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.jsonl'
            output.write_text('existing-data\n', encoding='utf-8')
            code, _, _ = self.invoke(['x', '-o', str(output)], web=[agg(1)])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_text(encoding='utf-8'), 'existing-data\n')
            self.assertEqual(self.web.calls, [])

    def test_output_cannot_overwrite_key_file(self):
        with tempfile.TemporaryDirectory() as directory:
            keyfile = Path(directory) / 'keys.txt'
            keyfile.write_text('example-file-key\n', encoding='utf-8')
            code, _, _ = self.invoke(['--count', 'x', '--key-file', str(keyfile), '-o', str(keyfile)])
            self.assertEqual(code, 2)
            self.assertEqual(keyfile.read_text(encoding='utf-8'), 'example-file-key\n')
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_output_cannot_overwrite_discovered_key_file(self):
        keyfile = self.work / 'daydaymap_keys.txt'
        keyfile.write_text('example-default\n', encoding='utf-8')
        code, _, _ = self.invoke(['--count', 'x', '-o', str(keyfile)], web=[agg(1)])
        self.assertEqual(code, 2)
        self.assertEqual(keyfile.read_text(encoding='utf-8'), 'example-default\n')
        self.assertEqual(self.api.calls + self.web.calls, [])

    def test_query_stdin_has_only_mandatory_filter(self):
        with mock.patch('sys.stdin', io.StringIO('port="80"\nport="443"\n')):
            code, out, _ = self.invoke(['--count', '--query-file', '-', '--interval', '0'], web=[agg(1), agg(2)])
        self.assertEqual(code, 0)
        self.assertEqual([json.loads(line)['query'] for line in out.splitlines()], [filtered('port="80"'), filtered('port="443"')])


if __name__ == '__main__':
    unittest.main()
