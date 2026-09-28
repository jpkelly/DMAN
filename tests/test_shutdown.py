"""Confirmed shutdown closes workers without exposing cross-origin control."""
import http.client
import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dsan_display.__main__ import Handler, Server
from dsan_display.model import Source
from dsan_display.workers import Worker


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.server = Server(('127.0.0.1', 0), Handler)
        self.server.quit_notice_seconds = 1
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        if self.thread.is_alive():
            self.server.shutdown()
        self.server.stop_workers()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path='/api/quit', body=None, origin=None, method='POST'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, path, json.dumps(body if body is not None else {'confirm': True}),
                         {'Origin': self.origin if origin is None else origin,
                          'Content-Type': 'application/json'})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_quit_requires_confirmation_and_same_origin(self):
        for body in ({}, {'confirm': False}, {'confirm': 1}, {'confirm': 'true'}, []):
            self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(self.request(origin='http://other.example')[0], 403)
        self.assertEqual(self.request(method='GET')[0], 404)
        self.assertFalse(self.server.quitting.is_set())

    def test_announces_shutdown_rejects_new_mutations_and_stops_once(self):
        worker = SimpleNamespace(stop=Mock(), source=Source('one', 'Test', 'replay', 'unused'))
        self.server.workers = {'one': worker}
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request()[0], 200)
        state = self.request('/api/state', method='GET')[1]
        self.assertEqual(state['application']['status'], 'stopping')
        self.assertEqual(self.request('/api/video-settings', {'timerSize': 75})[0], 409)
        self.assertEqual(self.request('/api/restart-replay', {'id': 'one'})[0], 409)
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())
        self.server.stop_workers()
        worker.stop.assert_called_once_with()

    def test_real_worker_loop_closes_its_hid_receiver(self):
        ready = threading.Event()
        def read():
            ready.set()
            time.sleep(0.01)
            return b''
        receiver = SimpleNamespace(info={'vendor_id': 0x0483, 'product_id': 0x101A},
                                   read=read, close=Mock())
        worker = Worker(Source('hid', 'Mock HID', 'hid', '00'))
        self.server.workers = {'hid': worker}
        with patch('dsan_display.workers.HidReceiver', return_value=receiver):
            worker.start()
            self.assertTrue(ready.wait(2))
            self.assertEqual(self.request()[0], 200)
            self.thread.join(timeout=5)
        self.assertFalse(worker.thread.is_alive())
        receiver.close.assert_called_once_with()
        self.assertEqual(worker.source.snapshot()['status'], 'disconnected')

    def test_cleanup_failure_does_not_skip_other_sources(self):
        failed = SimpleNamespace(stop=Mock(side_effect=OSError('Test failure')))
        peer = SimpleNamespace(stop=Mock())
        self.server.workers = {'failed': failed, 'peer': peer}
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.request()[0], 200)
            self.thread.join(timeout=5)
        peer.stop.assert_called_once_with()
        self.assertFalse(self.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
