"""Mock HID API boundaries with real timer fixtures; not Windows hardware tests."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dsan_capture.init_output import send_hid
from dsan_display.model import Source
from dsan_display.windows import configure, launch_arguments, validate_config
from dsan_display.workers import Worker
from dsan_display.__main__ import main as display_main


DEVICES = [dict(vendor_id=0x0483, product_id=0x101A, path_hex=p.hex(),
                serial_number='Ver 0.17 10/03/14') for p in (b'path-a', b'path-b')]


def configuration():
    return {'schema': 1,
            'sources': [dict(label=label, path_hex=device['path_hex'], role=role, initialize=True)
                        for label, device, role in zip(('Stage A', 'Stage B'), DEVICES, ('limitimer', 'perfectcue'))]}


class WindowsBindingTests(unittest.TestCase):
    def test_same_serial_devices_use_individual_paths(self):
        args = launch_arguments(configuration(), DEVICES)
        self.assertEqual(args.count('--hid'), 1)
        self.assertEqual(args.count('--perfectcue-hid'), 1)
        self.assertIn('Stage A=' + b'path-a'.hex(), args)
        self.assertIn('Stage B=' + b'path-b'.hex(), args)
        self.assertEqual(args.count('--init-hid'), 2)

    def test_missing_device_does_not_substitute_identical_peer(self):
        with self.assertRaisesRegex(ValueError, 'Stage A'):
            launch_arguments(configuration(), DEVICES[1:])

    def test_reject_duplicate_paths_even_with_different_hex_format(self):
        config = configuration()
        config['sources'][1]['path_hex'] = bytes.fromhex(DEVICES[0]['path_hex']).hex(' ').upper()
        with self.assertRaisesRegex(ValueError, 'unique'):
            validate_config(config)

    def test_receive_only_setup_does_not_enable_write_by_default(self):
        responses = iter(['1', 'Main stage', '1', ''])
        with patch('builtins.print'):
            config = configure(DEVICES, read=lambda _: next(responses))
        self.assertNotIn('--init-hid', launch_arguments(config, DEVICES))

    def test_string_false_cannot_enable_initialization(self):
        config = configuration()
        config['sources'][0]['initialize'] = 'false'
        with self.assertRaisesRegex(ValueError, 'true or false'):
            validate_config(config)

    def test_same_device_cannot_be_bound_to_both_roles(self):
        path = DEVICES[0]['path_hex']
        with patch('sys.stderr'), self.assertRaises(SystemExit) as result:
            display_main(['--hid', 'Timer=' + path, '--perfectcue-hid', 'Cue=' + path])
        self.assertEqual(result.exception.code, 2)


class HidWorkerTests(unittest.TestCase):
    def test_exact_output_and_short_write_not_retried(self):
        writes = []
        receiver = SimpleNamespace(info=DEVICES[0], device=SimpleNamespace(
            write=lambda data: writes.append(data) or 64))
        with self.assertRaisesRegex(OSError, 'not retried'):
            send_hid(receiver)
        self.assertEqual(writes, [b'\x00\x8d\x00' + bytes(62)])

    def test_non_dsan_receives_no_output(self):
        receiver = SimpleNamespace(info={'vendor_id': 1, 'product_id': 2})
        with self.assertRaisesRegex(ValueError, 'DSAN'):
            send_hid(receiver)

    def test_perfectcue_uses_its_own_mode(self):
        writes = []
        receiver = SimpleNamespace(info=DEVICES[1], device=SimpleNamespace(
            write=lambda data: writes.append(data) or len(data)))
        self.assertEqual(send_hid(receiver, 'perfectcue'), 65)
        self.assertEqual(writes, [b'\x00\x8d\x01' + bytes(62)])

    def test_cue_events_are_not_timer_state_and_expire_locally(self):
        # Observed framed Next message, with a controlled display clock.
        cue = Source('cue', 'Cue', 'hid', DEVICES[1]['path_hex'], role='perfectcue', warmup=0)
        cue.connected(now=0)
        cue.receive(bytes.fromhex('05 81 0f 01 00 83 00 00'), now=2)
        snapshot = cue.snapshot(now=2)
        self.assertEqual(snapshot['programs'], [])
        self.assertEqual(snapshot['states'], 0)
        self.assertEqual(snapshot['cue'], 'next')
        self.assertEqual(snapshot['unknown_cue_bytes'], 0)
        self.assertFalse(snapshot['cue_mapping_verified'])
        self.assertTrue(snapshot['cue_active'])
        self.assertFalse(cue.snapshot(now=4)['cue_active'])
        cue.end('disconnected')
        self.assertFalse(cue.snapshot(now=2)['cue_active'])

    def test_opening_buffered_cue_does_not_reappear_after_warmup(self):
        cue = Source('cue', 'Cue', 'hid', DEVICES[1]['path_hex'], role='perfectcue', warmup=1)
        cue.connected(now=0)
        cue.receive(bytes.fromhex('05 81 0f 01 00 83 00 00'), now=0.5)
        self.assertFalse(cue.snapshot(now=1.1)['cue_active'])
        self.assertEqual(cue.snapshot(now=1.1)['cue'], 'next')

    def test_mixed_roles_do_not_share_state(self):
        timer = Source('timer', 'Timer', 'hid', DEVICES[0]['path_hex'], warmup=0)
        cue = Source('cue', 'Cue', 'hid', DEVICES[1]['path_hex'], role='perfectcue', warmup=0)
        timer.connected(now=0)
        cue.connected(now=0)
        fixture = (Path(__file__).parent / 'fixtures/dongle/pi-p1-paused-0052.bin').read_bytes()
        for i in range(0, len(fixture), 8):
            timer.receive(fixture[i:i+8], now=2)
        for byte, expected in ((0, 'next'), (1, 'previous')):
            cue.receive(bytes((5, 0x81, 0x0F, 1, byte, 0x83, 0, 0)), now=2)
            self.assertEqual(cue.snapshot(2)['cue'], expected)
            self.assertEqual(cue.snapshot(2)['programs'], [])
            self.assertEqual(timer.snapshot(2)['programs'][0]['seconds'], 52)
        cue.end('disconnected')
        self.assertTrue(timer.snapshot(2)['fresh'])
        self.assertIsNone(timer.snapshot(2)['cue'])

    def test_native_handles_isolate_disconnect_and_preserve_input_count_byte(self):
        # A reports a disconnect. B delivers real unnumbered HID input. In
        # particular, the leading byte is a count, not another report-ID slot.
        fixture = (Path(__file__).parent / 'fixtures/dongle/pi-p1-paused-0052.bin').read_bytes()
        a = Worker(Source('a', 'Stage A', 'hid', DEVICES[0]['path_hex'], warmup=0), initialize_hid=True)
        b = Worker(Source('b', 'Stage B', 'hid', DEVICES[1]['path_hex'], warmup=0))
        handles = []

        class Handle:
            def __init__(self):
                self.path, self.writes, self.closed, self.offset = None, [], False, 0
                handles.append(self)

            def open_path(self, path):
                self.path = path

            def write(self, data):
                self.writes.append(data)
                return len(data)

            def read(self, size, timeout_ms):
                if self.path == b'path-a':
                    raise OSError('Test unplug A')
                result = fixture[self.offset:self.offset + 8]
                self.offset += 8
                if self.offset >= len(fixture):
                    b.cancel.set()
                return list(result)

            def close(self):
                self.closed = True

        with patch('dsan_capture.discovery.hid_devices', return_value=DEVICES), patch('hid.device', Handle):
            with self.assertLogs('dsan_display.workers', level='ERROR'):
                a.run()
            b.run()
        self.assertEqual([h.path for h in handles], [b'path-a', b'path-b'])
        self.assertEqual(handles[0].writes, [b'\x00\x8d\x00' + bytes(62)])
        self.assertEqual(handles[1].writes, [])
        self.assertTrue(all(h.closed for h in handles))
        self.assertEqual(a.source.snapshot()['status'], 'disconnected')
        snapshot = b.source.snapshot()
        self.assertTrue(snapshot['fresh'])
        self.assertEqual(snapshot['programs'][0]['seconds'], 52)


if __name__ == '__main__':
    unittest.main()
