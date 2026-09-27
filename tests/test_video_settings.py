"""Shared presentation state and HTTP updates, without changing timer hardware."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from dsan_display.__main__ import Handler, Server
from dsan_display.video_settings import VideoSettings


class VideoSettingsTests(unittest.TestCase):
    def test_partial_updates_persist_and_keep_unrelated_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'video.json'
            settings = VideoSettings(path)
            settings.update({'timerSize': 75, 'displayMode': 'cue'})
            settings.update({'cueSize': 150})
            restored = VideoSettings(path).snapshot()
            self.assertEqual(restored['revision'], 2)
            self.assertEqual(restored['settings']['timerSize'], 75)
            self.assertEqual(restored['settings']['cueSize'], 150)
            self.assertEqual(restored['settings']['displayMode'], 'cue')

    def test_invalid_changes_never_replace_good_state(self):
        settings = VideoSettings()
        before = settings.snapshot()
        for invalid in ({'timerSize': 500}, {'timerSize': True}, {'cueSize': float('nan')},
                        {'minimal': 'false'}, {'displayMode': 'unknown'}, {'source': 'other-dongle'}, []):
            with self.assertRaises(ValueError):
                settings.update(invalid)
            self.assertEqual(settings.snapshot(), before)

    def test_failed_save_does_not_apply_or_acknowledge_change(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = VideoSettings(Path(folder) / 'video.json')
            before = settings.snapshot()
            with patch.object(Path, 'replace', side_effect=OSError('Simulated write failure')):
                with self.assertRaises(OSError):
                    settings.update({'minimal': False})
            self.assertEqual(settings.snapshot(), before)

    def test_multiple_clients_read_same_live_settings_and_cross_origin_is_denied(self):
        server = Server(('127.0.0.1', 0), Handler)
        server.workers, server.control_lock = {}, threading.Lock()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'

        def request(method, path, data=None, request_origin=origin):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                conn.request(method, path, json.dumps(data) if data is not None else None,
                             {'Origin': request_origin, 'Content-Type': 'application/json'})
                response = conn.getresponse()
                return response.status, json.loads(response.read())
            finally:
                conn.close()

        try:
            code, result = request('POST', '/api/video-settings', {'displayMode': 'timer', 'timerSize': 125})
            self.assertEqual(code, 200)
            for _ in range(2):
                self.assertEqual(request('GET', '/api/state')[1]['video'], result)
            self.assertEqual(request('POST', '/api/video-settings', {'displayMode': 'cue'}, 'http://foreign.example')[0], 403)
            self.assertEqual(request('POST', '/api/video-settings', {'source': 'wrong'})[0], 400)
            self.assertEqual(request('GET', '/api/state')[1]['video'], result)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
