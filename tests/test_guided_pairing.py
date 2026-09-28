"""Simulated plug/unplug sequences for first-run pairing; no USB writes."""
import unittest
from unittest.mock import Mock, patch
from dsan_display.windows import guided_configure, launch_arguments

A = {'path_hex': b'new-machine-port-a'.hex(), 'serial_number': 'same firmware string'}
B = {'path_hex': b'new-machine-port-b'.hex(), 'serial_number': 'same firmware string'}


def pair(responses, snapshots, already_connected=False):
    answers = iter(responses)
    enumerate_devices = Mock(side_effect=snapshots if already_connected else [[]] + snapshots)
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

    def test_both_connected_at_launch_are_identified_by_disappearance(self):
        config = pair(['1', '', '', 'Timer', '2', '', '', 'Cues', ''],
                      [[A, B], [B, A], [B], [A, B], [A, B], [A], [B, A], [A, B]],
                      already_connected=True)
        self.assertEqual([(s['role'], s['path_hex']) for s in config['sources']],
                         [('limitimer', A['path_hex']), ('perfectcue', B['path_hex'])])

    def test_reconnected_target_can_receive_a_new_path(self):
        moved = {**A, 'path_hex': b'reconnected-a'.hex()}
        config = pair(['1', '', '', '', ''],
                      [[A], [A], [], [moved], [moved]], already_connected=True)
        self.assertEqual(config['sources'][0]['path_hex'], moved['path_hex'])

    def test_removing_both_is_not_mistaken_for_one_identified_device(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected USB change'):
            pair(['1', ''], [[A, B], [A, B], []], already_connected=True)

    def test_removing_an_already_paired_peer_aborts_without_reassignment(self):
        with self.assertRaisesRegex(ValueError, 'already-paired'):
            pair(['1', '', '', '', '2', ''],
                 [[A, B], [A, B], [B], [A, B], [A, B], [B]], already_connected=True)


if __name__ == '__main__':
    unittest.main()
