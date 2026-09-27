"""Protocol evidence from real capture fixtures; never a dongle identity claim."""
from pathlib import Path
import unittest
from dsan_capture.protocol_probe import ProtocolEvidence

FIXTURES = Path(__file__).parent / 'fixtures/dongle'


def feed_fixture(evidence, name):
    raw = (FIXTURES / name).read_bytes()
    for offset in range(0, len(raw), 8):
        evidence.feed(raw[offset:offset+8])


class ProtocolProbeTests(unittest.TestCase):
    def test_timer_fixture_identifies_traffic_with_absent_checksums(self):
        evidence = ProtocolEvidence()
        feed_fixture(evidence, 'pi-p1-stopped-0100.bin')
        result = evidence.result()
        self.assertEqual(result['observed_protocol'], 'limitimer')
        self.assertEqual(result['cue_frames'], 0)
        self.assertIn('absent', result['limitimer_checksums'])

    def test_emulator_cue_fixture(self):
        evidence = ProtocolEvidence()
        feed_fixture(evidence, 'pi-perfectcue-previous-isolated.bin')
        self.assertEqual(evidence.result()['observed_protocol'], 'perfectcue-framed')
        self.assertEqual(evidence.timer_frames, 0)

    def test_silence_and_single_cue_are_not_identity_evidence(self):
        evidence = ProtocolEvidence()
        for _ in range(20):
            evidence.feed(bytes(8))
        self.assertEqual(evidence.result()['observed_protocol'], 'unknown')
        evidence.feed(bytes.fromhex('05 81 0f 01 00 83 00 00'))
        self.assertEqual(evidence.result()['observed_protocol'], 'unknown')

    def test_conflicting_stream_is_ambiguous(self):
        evidence = ProtocolEvidence()
        feed_fixture(evidence, 'pi-p1-stopped-0100.bin')
        feed_fixture(evidence, 'pi-perfectcue-previous-isolated.bin')
        self.assertEqual(evidence.result()['observed_protocol'], 'ambiguous')


if __name__ == '__main__':
    unittest.main()
