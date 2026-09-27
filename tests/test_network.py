"""LAN request handling using a real HTTP server, without dongles."""
import http.client
import json
import socket
import threading
import unittest
from types import SimpleNamespace

from dsan_display.__main__ import Handler, Server, create_server
from dsan_display.network import host_allowed, listen_address


class NetworkTests(unittest.TestCase):
    def test_interface_addresses_and_local_names(self):
        names = {'displaybox.local', 'localhost'}
        self.assertTrue(host_allowed('10.65.1.56:8765', 8765, '10.65.1.56', names))
        self.assertTrue(host_allowed('DISPLAYBOX.local:8765', 8765, '10.65.1.56', names))
        for header in ('evil.example:8765', '10.65.1.56:9999', 'user@10.65.1.56:8765',
                       '10.65.1.56:8765/path', '10.65.1.56:8765?x=1', '10.65.1.56:bad', ''):
            self.assertFalse(host_allowed(header, 8765, '10.65.1.56', names), header)

    def test_listen_address_is_explicit_ip(self):
        self.assertEqual(listen_address('0.0.0.0'), '0.0.0.0')
        self.assertEqual(listen_address('127.0.0.1'), '127.0.0.1')
        self.assertEqual(listen_address('::'), '::')
        for value in ('example.com', '999.1.1.1'):
            with self.assertRaises(ValueError):
                listen_address(value)

    def test_mapped_and_scoped_ipv6_hosts(self):
        self.assertTrue(host_allowed('127.0.0.1:8765', 8765, '::ffff:127.0.0.1', set()))
        self.assertTrue(host_allowed('[fe80::1234%25eth0]:8765', 8765, 'fe80::1234', set()))
        self.assertFalse(host_allowed('[fe80::9999]:8765', 8765, 'fe80::1234', set()))

    @unittest.skipUnless(socket.has_dualstack_ipv6(), 'Dual-stack sockets unavailable')
    def test_wildcard_listener_accepts_both_ip_families(self):
        server = create_server('0.0.0.0', 0)
        server.workers, server.control_lock = {}, threading.Lock()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for host in ('127.0.0.1', '::1'):
                conn = http.client.HTTPConnection(host, server.server_port, timeout=5)
                try:
                    conn.request('GET', '/api/state')
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), {'sources': []})
                finally:
                    conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_lan_origin_can_restart_replay_but_foreign_origins_cannot(self):
        restarted = []
        worker = SimpleNamespace(source=SimpleNamespace(snapshot=lambda: {'id': 'replay-test'}),
                                 restart_replay=lambda: restarted.append(True))
        server = Server(('127.0.0.1', 0), Handler)
        server.allowed_hostnames.add('displaybox.local')
        server.workers, server.control_lock = {'replay-test': worker}, threading.Lock()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, host, origin=None):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Host': host}
            body = None
            if origin is not None:
                headers['Origin'] = origin
            if method == 'POST':
                body = json.dumps({'id': 'replay-test'})
                headers['Content-Type'] = 'application/json'
            try:
                conn.request(method, path, body, headers)
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()

        try:
            host = f'displaybox.local:{server.server_port}'
            self.assertEqual(request('GET', '/api/state', host)[0], 200)
            self.assertIn(b'<body class="output">', request('GET', '/output', host)[1])
            self.assertEqual(request('POST', '/api/restart-replay', host, 'http://' + host)[0], 200)
            self.assertEqual(request('POST', '/api/restart-replay', host, 'http://evil.example')[0], 403)
            self.assertEqual(request('POST', '/api/restart-replay', host)[0], 403)
            self.assertEqual(request('GET', '/api/state', f'evil.example:{server.server_port}')[0], 403)
            self.assertEqual(restarted, [True])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
