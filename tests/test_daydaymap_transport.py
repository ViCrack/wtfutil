"""Real local TLS/CONNECT/SOCKS tests; certificates are generated only in temp directories."""
from __future__ import annotations

import hashlib
import importlib.util
import select
import shutil
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from wtfutil.daydaymaputil import query_from_certificate


class LocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class TLSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            with self.server.context.wrap_socket(self.request, server_side=True) as secure:
                self.server.payloads.append(secure.recv(1))
        except (OSError, ssl.SSLError):
            pass


def receive(sock, length):
    data = b''
    while len(data) < length:
        part = sock.recv(length - len(data))
        if not part:
            raise OSError('client closed')
        data += part
    return data


class TunnelHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client = self.request
        try:
            client.settimeout(3)
            if self.server.context:
                client = self.server.context.wrap_socket(client, server_side=True)
            if self.server.socks:
                version, methods = receive(client, 2)
                if version != 5 or b'\0' not in receive(client, methods):
                    return
                client.sendall(b'\x05\x00')
                version, command, reserved, address_type = receive(client, 4)
                if (version, command, reserved) != (5, 1, 0):
                    return
                if address_type == 3:
                    host = receive(client, receive(client, 1)[0]).decode('ascii')
                elif address_type == 1:
                    host = socket.inet_ntop(socket.AF_INET, receive(client, 4))
                elif address_type == 4:
                    host = socket.inet_ntop(socket.AF_INET6, receive(client, 16))
                else:
                    return
                port = int.from_bytes(receive(client, 2), 'big')
                self.server.requests.append((host, port))
                reply = b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00'
            else:
                header = bytearray()
                while not header.endswith(b'\r\n\r\n') and len(header) < 65536:
                    header.extend(receive(client, 1))
                self.server.requests.append(bytes(header))
                if not header.startswith(b'CONNECT '):
                    return
                reply = b'HTTP/1.1 200 Connection established\r\n\r\n'
            with socket.create_connection(self.server.destination, timeout=3) as upstream:
                client.sendall(reply)
                while True:
                    ready, _, _ = select.select([client, upstream], [], [], 3)
                    if not ready:
                        break
                    for source in ready:
                        data = source.recv(16384)
                        if not data:
                            return
                        (upstream if source is client else client).sendall(data)
        except OSError:
            pass
        finally:
            client.close()


@unittest.skipUnless(shutil.which('openssl'), 'openssl is needed to generate ephemeral TLS fixtures')
class TestLocalCertificateTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='daydaymap-tls-')
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        cls.cert, key = root / 'cert.pem', root / 'key.pem'
        subprocess.run([shutil.which('openssl'), 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cls.cert), '-days', '1', '-subj', '/CN=localhost'],
                       check=True, capture_output=True, timeout=30)
        cls.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.context.load_cert_chain(cls.cert, key)
        der = ssl.PEM_cert_to_DER_cert(cls.cert.read_text(encoding='ascii'))
        cls.expected = 'cert.md5="' + hashlib.md5(der).hexdigest() + '"'

    def setUp(self):
        # Do not use any real workstation proxy when running a local test.
        self.enterContext(mock.patch('wtfutil.daydaymaputil.get_environ_proxies', return_value={}))
        self.names = []
        self.context.set_servername_callback(lambda sock, name, ctx: self.names.append(name))
        self.target = self.start_server(TLSHandler)
        self.target.context = self.context
        self.target.payloads = []

    def start_server(self, handler):
        server = LocalServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()
        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.addCleanup(cleanup)
        return server

    def proxy(self, *, tls=False, socks=False):
        server = self.start_server(TunnelHandler)
        server.context = self.context if tls else None
        server.socks = socks
        server.requests = []
        server.destination = self.target.server_address
        return server

    def test_direct_self_signed_leaf_der_md5_sni_and_custom_port(self):
        port = self.target.server_address[1]
        result = query_from_certificate(f'https://localhost:{port}/path-ignored', timeout=3)
        self.assertEqual(result, self.expected)
        self.assertIn('localhost', self.names)
        self.assertTrue(all(payload == b'' for payload in self.target.payloads))

    def test_http_connect_and_proxy_auth(self):
        proxy = self.proxy()
        url = f'http://example-user:example-password@127.0.0.1:{proxy.server_address[1]}'
        result = query_from_certificate('https://certificate.example.invalid:8443', proxy=url, timeout=3)
        self.assertEqual(result, self.expected)
        self.assertIn('certificate.example.invalid', self.names)
        self.assertEqual(len(proxy.requests), 1)
        self.assertTrue(proxy.requests[0].startswith(b'CONNECT certificate.example.invalid:8443 '))
        self.assertIn(b'proxy-authorization: basic ', proxy.requests[0].lower())

    def test_https_proxy_uses_tls_in_tls(self):
        proxy = self.proxy(tls=True)
        url = f'https://127.0.0.1:{proxy.server_address[1]}'
        self.assertEqual(query_from_certificate('https://certificate.example.invalid:443', proxy=url, timeout=3), self.expected)
        self.assertEqual(len(proxy.requests), 1)
        self.assertIn('certificate.example.invalid', self.names)

    @unittest.skipUnless(importlib.util.find_spec('socks'), 'optional PySocks is not installed')
    def test_socks5h_resolves_target_at_proxy(self):
        proxy = self.proxy(socks=True)
        url = f'socks5h://127.0.0.1:{proxy.server_address[1]}'
        self.assertEqual(query_from_certificate('https://certificate.example.invalid:9443', proxy=url, timeout=3), self.expected)
        self.assertEqual(proxy.requests, [('certificate.example.invalid', 9443)])
        self.assertIn('certificate.example.invalid', self.names)

    @unittest.skipUnless(importlib.util.find_spec('socks'), 'optional PySocks is not installed')
    def test_socks5_uses_locally_resolved_address(self):
        proxy = self.proxy(socks=True)
        url = f'socks5://127.0.0.1:{proxy.server_address[1]}'
        self.assertEqual(query_from_certificate('https://localhost:9443', proxy=url, timeout=3), self.expected)
        self.assertIn(proxy.requests[0][0], ('127.0.0.1', '::1'))
        self.assertIn('localhost', self.names)


if __name__ == '__main__':
    unittest.main()
