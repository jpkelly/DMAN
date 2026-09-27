"""Real emulator/dongle fixtures; mutation tests are explicitly synthetic."""
import hashlib
import json
import unittest
from pathlib import Path
from dsan_capture.hid_stream import normalize_report
from dsan_capture.perfectcue import CueStreamDecoder

FIXTURES = Path(__file__).parent / 'fixtures/dongle'


class PerfectCueTests(unittest.TestCase):
    def capture(self, name):
        raw = (FIXTURES / (name + '.bin')).read_bytes()
        metadata = json.loads((FIXTURES / (name + '.json')).read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata['sha256'])
        payloads = [normalize_report(raw[i:i+8], report_id_slot=False).payload
                    for i in range(0, len(raw), 8)]
        return payloads, metadata['expected_values']

    def test_actual_usb_boundaries_and_concatenated_split_messages(self):
        for name in ('pi-perfectcue-next-isolated', 'pi-perfectcue-previous-isolated'):
            payloads, expected = self.capture(name)
            decoder = CueStreamDecoder()
            actual = [frame.value for payload in payloads for frame in decoder.feed(payload)]
            self.assertEqual(actual, expected)
            self.assertEqual(decoder.discarded_bytes, 0)
            self.assertEqual(decoder.rejected_frames, 0)

    def test_every_stream_chunk_size_preserves_observed_sequence(self):
        payloads, expected = self.capture('pi-perfectcue-next-isolated')
        stream = b''.join(payloads)
        for size in range(1, len(stream) + 1):
            decoder = CueStreamDecoder()
            actual = [f.value for i in range(0, len(stream), size)
                      for f in decoder.feed(stream[i:i+size])]
            self.assertEqual(actual, expected)

    def test_corruption_and_truncated_prefix_resynchronize(self):
        decoder = CueStreamDecoder()
        # Deliberately damaged copies of the observed Next frame.
        data = bytes.fromhex('ff 0f 81 0f 81 0f 02 00 83 81 0f 01 00 82 81 0f 01 01 83')
        frames = decoder.feed(data)
        self.assertEqual([f.name for f in frames], ['previous'])
        self.assertEqual(decoder.rejected_frames, 2)
        self.assertGreater(decoder.discarded_bytes, 0)

    def test_unknown_value_is_not_guessed_as_blank(self):
        frames = CueStreamDecoder().feed(bytes.fromhex('81 0f 01 02 83'))
        self.assertEqual(frames[0].value, 2)
        self.assertIsNone(frames[0].name)

    def test_bare_serial_bytes_do_not_trigger_hid_cues(self):
        decoder = CueStreamDecoder()
        self.assertEqual(decoder.feed(bytes.fromhex('0f 1f 2f 3f')), [])
        self.assertEqual(decoder.discarded_bytes, 4)


if __name__ == '__main__':
    unittest.main()
