"""Real subprocess pipes against a loopback API, without live keys or paid calls."""
from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class TestPipelineProcess(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.release = threading.Event()
        self.release.set()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                query = base64.b64decode(payload['keyword']).decode('utf-8')
                owner.calls.append((self.path, payload, query))
                if 'aggregate' in self.path:
                    data = {'port': [{'name': '80', 'count': 2}], 'ip_num': 2}
                else:
                    owner.release.wait(10)
                    width = payload['page_size']
                    start = (payload['page'] - 1) * width
                    data = {'total': 2, 'list': [
                        {'ip': f'192.0.2.{i + 1}', 'port': 80, 'title': '示例'}
                        for i in range(start, min(start + width, 2))]}
                body = json.dumps({'code': 200, 'data': data}, ensure_ascii=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def start(self, args):
        # DAYDAYMAP_TEST_PYTHON optionally exercises an already-installed wheel.
        python = os.environ.get('DAYDAYMAP_TEST_PYTHON', sys.executable)
        isolated = ['-I'] if os.environ.get('DAYDAYMAP_TEST_PYTHON') else []
        bootstrap = (
            'from wtfutil import daydaymaputil as sdk; '
            f'sdk.DEFAULT_BASE_URL = "http://127.0.0.1:{self.server.server_port}"; '
            'from wtfutil.daydaymap import main; raise SystemExit(main())'
        )
        environment = {key: value for key, value in os.environ.items() if not key.startswith('DAYDAYMAP_')}
        environment.update(DAYDAYMAP_API_KEY='example-pipeline-key', NO_PROXY='*', no_proxy='*', PYTHONIOENCODING='utf-8')
        process = subprocess.Popen([python, *isolated, '-W', 'error::ResourceWarning', '-c', bootstrap,
                                    '--interval', '0', *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8', env=environment)
        self.addCleanup(self.stop_process, process)
        return process

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            if not stream.closed:
                stream.close()

    def test_first_count_arrives_before_stdin_eof(self):
        process = self.start(['--count', '--template', 'domain="{}"'])
        output = queue.Queue()

        def read_lines():
            for line in process.stdout:
                output.put(line)

        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()
        process.stdin.write('example.com\n')
        process.stdin.flush()
        first = json.loads(output.get(timeout=10))
        self.assertEqual(first['query'], '(domain="example.com") && ip.tag!="蜜罐"')
        self.assertIsNone(process.poll())
        process.stdin.write('示例.example\n')
        process.stdin.flush()
        second = json.loads(output.get(timeout=10))
        self.assertIn('示例.example', second['query'])
        process.stdin.close()
        self.assertEqual(process.wait(timeout=10), 0)
        reader.join(5)
        self.assertEqual(process.stderr.read(), '')
        self.assertEqual(len(self.calls), 2)

    def test_closed_consumer_stops_after_first_page_without_traceback(self):
        self.release.clear()
        process = self.start(['x', '--quiet', '--page-size', '1'])
        process.stdout.close()
        self.release.set()
        process.stdin.close()
        code = process.wait(timeout=10)
        errors = process.stderr.read()
        self.assertEqual(code, 0, errors)
        self.assertEqual(errors, '')
        paid_calls = [call for call in self.calls if 'search/all' in call[0]]
        self.assertEqual(len(paid_calls), 1)
        self.assertEqual(paid_calls[0][1]['page'], 1)


if __name__ == '__main__':
    unittest.main()
