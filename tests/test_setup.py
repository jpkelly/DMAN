"""Browser setup API against the real pairing routine; USB inventories are mocked."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from dsan_display.__main__ import Handler, Server
from dsan_display.setup import Setup

A = {'path_hex': b'port-a'.hex()}
B = {'path_hex': b'port-b'.hex()}


class BrowserSetupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'sources.json'
        self.devices = [A, B]
        self.server = Server(('127.0.0.1', 0), Handler)
        self.factory = Mock(side_effect=lambda s: (s['path_hex'], SimpleNamespace(
            start=Mock(), stop=Mock(), thread=None)))
        self.setup = self.server.setup = Setup(self.server, self.path, lambda: self.devices, self.factory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.setup.close()
        if self.setup.thread:
            self.setup.thread.join(timeout=3)
        self.server.shutdown()
        self.server.stop_workers()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.folder.cleanup()

    def request(self, action, body=None, origin=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request('POST', '/api/setup/' + action, json.dumps(body or {}),
                         {'Origin': origin or self.origin, 'Content-Type': 'application/json'})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def wait(self, status, previous=None):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = self.setup.snapshot()
            if state['status'] == status and (not previous or state['prompt']['id'] != previous):
                return state
            time.sleep(.01)
        self.fail(f'Did not reach {status}: {self.setup.snapshot()}')

    def answer(self, text, next_status='waiting'):
        state = self.wait('waiting')
        prompt = state['prompt']['id']
        self.assertEqual(self.request('answer', {'session': state['session'], 'prompt': prompt, 'answer': text})[0], 200)
        return self.wait(next_status, prompt if next_status == 'waiting' else None)

    def review_two(self):
        self.assertEqual(self.request('start')[0], 200)
        self.answer('1')
        self.devices = [B]
        self.answer('')
        self.devices = [B, A]
        self.answer('')
        self.answer('Stage timer')
        self.answer('2')
        self.devices = [A]
        self.answer('')
        self.devices = [A, B]
        self.answer('')
        self.answer('Stage cues')
        return self.answer('', 'review')

    def test_real_wizard_waits_for_review_then_saves_and_starts_exact_paths(self):
        state = self.review_two()
        self.factory.assert_not_called()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.request('apply', {'session': state['session']})[0], 200)
        self.wait('complete')
        saved = json.loads(self.path.read_text())
        self.assertEqual([(s['role'], s['path_hex']) for s in saved['sources']],
                         [('limitimer', A['path_hex']), ('perfectcue', B['path_hex'])])
        self.assertEqual(self.factory.call_count, 2)
        for worker in self.server.workers.values():
            worker.start.assert_called_once_with()
        self.assertEqual(self.request('apply', {'session': state['session']})[0], 400)

    def test_cancel_preserves_saved_configuration_and_opens_no_devices(self):
        self.path.write_text('existing configuration')
        self.request('start')
        self.wait('waiting')
        self.assertEqual(self.request('cancel')[0], 200)
        self.setup.thread.join(timeout=3)
        self.assertFalse(self.setup.thread.is_alive())
        self.assertEqual(self.path.read_text(), 'existing configuration')
        self.factory.assert_not_called()

    def test_changed_devices_before_apply_do_not_replace_saved_config(self):
        state = self.review_two()
        self.path.write_text('existing configuration')
        self.devices = [B]
        with self.assertLogs(level='ERROR'):
            self.request('apply', {'session': state['session']})
            error = self.wait('error')
        self.assertIn('missing', error['error'])
        self.assertEqual(self.path.read_text(), 'existing configuration')
        self.factory.assert_not_called()

    def test_old_prompt_and_foreign_origin_cannot_advance_setup(self):
        self.assertEqual(self.request('start', origin='http://foreign.example')[0], 403)
        self.request('start')
        state = self.wait('waiting')
        self.assertEqual(self.request('start')[0], 400)
        self.answer('1')
        self.assertEqual(self.request('answer', {'session': state['session'], 'prompt': state['prompt']['id'], 'answer': '2'})[0], 400)
        self.factory.assert_not_called()

    def test_removing_two_devices_is_an_error_not_a_guessed_assignment(self):
        self.request('start')
        self.answer('1')
        self.devices = []
        with self.assertLogs(level='ERROR'):
            state = self.answer('', 'error')
        self.assertIn('Unexpected USB change', state['error'])
        self.assertFalse(self.path.exists())
        self.factory.assert_not_called()

    def test_server_shutdown_releases_waiting_wizard(self):
        self.request('start')
        self.wait('waiting')
        self.server.stop_workers()
        self.setup.thread.join(timeout=3)
        self.assertFalse(self.setup.thread.is_alive())

    def test_saved_configuration_restores_exact_bindings(self):
        config = {'schema': 1, 'sources': [{'path_hex': A['path_hex'], 'role': 'limitimer',
                                          'label': 'Saved timer', 'initialize': False}]}
        self.path.write_text(json.dumps(config))
        self.assertEqual(self.request('resume')[0], 200)
        self.wait('complete')
        self.factory.assert_called_once_with(config['sources'][0])
        self.assertEqual(set(self.server.workers), {A['path_hex']})

    def test_missing_saved_input_is_reported_without_opening_peer(self):
        config = {'schema': 1, 'sources': [{'path_hex': A['path_hex'], 'role': 'limitimer',
                                          'label': 'Saved timer', 'initialize': True}]}
        self.path.write_text(json.dumps(config))
        self.devices = [B]
        self.request('resume')
        self.assertIn('Saved timer', self.wait('error')['error'])
        self.factory.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text()), config)


if __name__ == '__main__':
    unittest.main()
