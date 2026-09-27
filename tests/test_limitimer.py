"""Limitimer framing/decoding against upstream RS-485 capture excerpts (real
Limitimer traffic from another setup; see fixtures/upstream-limitimer/README.md)
and our own real dongle fragment. Mutations of real frames are labelled."""
import unittest
from pathlib import Path

from dsan_capture.hid_stream import normalize_report
from dsan_capture.limitimer import (CHECKSUM_ABSENT, CHECKSUM_INVALID, CHECKSUM_VALID, TYPE_STATE, TYPE_SYNC,
                                    Discarded, Frame, FrameSplitter, crc16_modbus, decode_state)

FIXTURES = Path(__file__).parent / "fixtures" / "upstream-limitimer"


def load(name):
    return (FIXTURES / name).read_bytes()


def frames(items):
    return [item for item in items if isinstance(item, Frame)]


def states(items):
    return [decode_state(f) for f in frames(items) if f.type == TYPE_STATE]


class ChecksumTests(unittest.TestCase):
    def test_crc16_modbus_check_value(self):
        self.assertEqual(crc16_modbus(b"123456789"), 0x4B37)


class UpstreamCaptureTests(unittest.TestCase):
    def test_p2_17min_7min_sumup(self):
        splitter = FrameSplitter()
        items = splitter.feed(load("p2-17min-7min-sumup.bin"))
        self.assertIsInstance(items[0], Discarded)  # Excerpt starts mid-frame
        self.assertTrue(all(f.checksum_status == CHECKSUM_VALID for f in frames(items)))
        decoded = states(items)
        self.assertEqual(len(decoded), 19)
        self.assertEqual({f.type for f in frames(items)}, {TYPE_STATE, TYPE_SYNC})
        p2 = decoded[0].programs[1]
        self.assertEqual(decoded[0].selected, 1)
        self.assertEqual((p2.total, p2.sumup, p2.running), (17 * 60, 7 * 60, True))
        self.assertTrue(decoded[0].counts_down)
        # Elapsed advances while running; the other programs stay put.
        self.assertEqual([s.programs[1].elapsed for s in decoded][::6], [506, 507, 508, 509])
        self.assertTrue(all(s.programs[0] == decoded[0].programs[0] for s in decoded))
        self.assertEqual(splitter.unterminated, 0)

    def test_count_up_clears_count_down_bit(self):
        decoded = states(FrameSplitter().feed(load("count-up.bin")))
        self.assertTrue(decoded)
        self.assertFalse(any(s.counts_down for s in decoded))
        self.assertEqual((decoded[0].programs[0].total, decoded[0].programs[0].sumup), (900, 300))

    def test_chunking_does_not_change_results(self):
        data = load("p2-17min-7min-sumup.bin")
        whole = FrameSplitter().feed(data)
        for size in (1, 7, 64):
            splitter = FrameSplitter()
            chunked = [item for i in range(0, len(data), size) for item in splitter.feed(data[i:i + size])]
            self.assertEqual(chunked, whole)

    def test_lossy_capture_rejects_truncated_state_frames(self):
        items = FrameSplitter().feed(load("listener-raw-lossy.bin"))
        state_frames = [f for f in frames(items) if f.type == TYPE_STATE]
        self.assertTrue(all(f.checksum_status == CHECKSUM_ABSENT for f in frames(items)))
        short = [f for f in state_frames if len(f.body) != 52]
        self.assertTrue(short)
        for frame in short:
            with self.assertRaises(ValueError):
                decode_state(frame)
        decoded = [decode_state(f) for f in state_frames if len(f.body) == 52]
        self.assertTrue(decoded)
        self.assertTrue(all(s.checksum_status == CHECKSUM_ABSENT for s in decoded))
        self.assertTrue(any(isinstance(item, Discarded) and item.reason == "restart before checksum mark" for item in items))

    def test_mutated_real_frame_fails_checksum(self):
        frame = next(f for f in frames(FrameSplitter().feed(load("p2-17min-7min-sumup.bin"))) if f.type == TYPE_STATE)
        body = bytearray(frame.body)
        body[20] ^= 0x01  # Mutation of a real frame
        mutated = Frame(bytes(body), frame.checksum)
        self.assertEqual(mutated.checksum_status, CHECKSUM_INVALID)
        with self.assertRaises(ValueError):
            decode_state(mutated)

    def test_checksum_bytes_may_look_like_control_bytes(self):
        # Synthetic frame whose valid checksum is 83 9D: a checksum mark, then a high-bit byte.
        body = bytes.fromhex("81103c0383")
        self.assertEqual(crc16_modbus(body), 0x839D)
        splitter = FrameSplitter()
        item, = splitter.feed(body + bytes.fromhex("839dff"))
        self.assertEqual((item.body, item.checksum_status, splitter.terminated), (body, CHECKSUM_VALID, 1))


class DongleFragmentTests(unittest.TestCase):
    def test_real_fragment_sync_without_terminator_keeps_next_frame(self):
        # captures/pro2000-p1-stopped-0100: sync frame, zero checksum, no FF, then a new frame.
        report = normalize_report(bytes.fromhex("0781108300008100"), report_id_slot=False)
        splitter = FrameSplitter()
        sync, = splitter.feed(report.payload)
        self.assertEqual((sync.type, sync.checksum_status), (TYPE_SYNC, CHECKSUM_ABSENT))
        self.assertEqual((splitter.terminated, splitter.unterminated), (0, 1))
        self.assertEqual(bytes(splitter.buffer), bytes.fromhex("8100"))  # Next frame retained, not discarded

    def test_sources_do_not_share_assembly(self):
        # Interleaving two sources' real bytes through separate splitters gives each
        # exactly what it would get alone.
        a, b = load("p2-17min-7min-sumup.bin"), load("count-up.bin")
        split_a, split_b = FrameSplitter(), FrameSplitter()
        out_a, out_b = [], []
        for i in range(0, max(len(a), len(b)), 7):
            out_a += split_a.feed(a[i:i + 7])
            out_b += split_b.feed(b[i:i + 7])
        self.assertEqual(out_a, FrameSplitter().feed(a))
        self.assertEqual(out_b, FrameSplitter().feed(b))


if __name__ == "__main__":
    unittest.main()
