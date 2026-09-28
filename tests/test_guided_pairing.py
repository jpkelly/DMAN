"""Simulated plug/unplug sequences for first-run pairing; no USB writes."""
import unittest
from unittest.mock import Mock, patch
from dsan_display.windows import guided_configure, launch_arguments

A = {'path_hex': b'new-machine-port-a'.hex(), 'serial_number': 'same firmware string'}
B = {'path_hex': b'new-machine-port-b'.hex(), 'serial_number': 'same firmware string'}


def pair(responses, snapshots):
    answers = iter(responses)
    enumerate_devices = Mock(side_effect=snapshots)
    with patch('builtins.print'):
        result = guided_configure(read=lambda _: next(answers), enumerate_devices=enumerate_devices)
    return result


class GuidedPairingTests(unittest.TestCase):
    def test_new_machine_pairs_identical_serials_by_connection_sequence(self):
        config = pair(['', '1', '', 'Timer', '2', '', 'Cues', ''],
                      [[], [A], [B, A], [A, B]])
        self.assertEqual([(s['label'], s['role'], s['path_hex']) for s in config['sources']],
                         [('Timer', 'limitimer', A['path_hex']), ('Cues', 'perfectcue', B['path_hex'])])
        args = launch_arguments(config, [B, A])
        self.assertEqual(args.count('--init-hid'), 2)

    def test_requires_empty_baseline_and_only_one_new_device(self):
        config = pair(['', '', '2', '', '', '', ''],
                      [[A], [], [A, B], [B], [B]])
        self.assertEqual(config['sources'][0]['path_hex'], B['path_hex'])
        self.assertEqual(config['sources'][0]['role'], 'perfectcue')

    def test_missing_paired_device_is_not_replaced_by_new_peer(self):
        config = pair(['', '1', '', '', '2', '', '', '', ''],
                      [[], [A], [B], [A, B], [B, A]])
        self.assertEqual([s['path_hex'] for s in config['sources']], [A['path_hex'], B['path_hex']])

    def test_second_device_must_appear_as_distinct_path(self):
        config = pair(['', '1', '', '', '2', '', '', '', ''],
                      [[], [A], [A], [A, B], [A, B]])
        self.assertEqual(len(config['sources']), 2)

    def test_duplicate_os_paths_are_not_assumed_to_be_two_dongles(self):
        with self.assertRaisesRegex(ValueError, 'duplicate HID paths'):
            pair(['', '1', ''], [[], [A, A]])

    def test_cancel_does_not_return_partial_configuration(self):
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            pair(['', '1', '', '', 'q'], [[], [A]])


if __name__ == '__main__':
    unittest.main()
