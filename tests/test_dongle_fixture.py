"""Regression against a real, user-labelled PRO-2000/VC-2000PC capture."""
import hashlib
import json
import unittest
from pathlib import Path

from dsan_capture.hid_stream import STREAM, normalize_report
from dsan_capture.limitimer import CHECKSUM_ABSENT, Frame, FrameSplitter, TYPE_STATE, decode_state


class DongleFixtureTests(unittest.TestCase):
    def test_p2_selection_does_not_change_paused_p1(self):
        folder = Path(__file__).parent / "fixtures" / "dongle"
        meta = json.loads((folder / "pi-program-switch.json").read_text())
        raw = (folder / "pi-program-switch.bin").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])
        splitter = FrameSplitter()
        selections = []
        count = 0
        for offset in range(0, len(raw), 8):
            report = normalize_report(raw[offset:offset + 8], report_id_slot=False)
            for frame in splitter.feed(report.payload):
                if not isinstance(frame, Frame) or frame.type != TYPE_STATE:
                    continue
                state = decode_state(frame)
                count += 1
                if not selections or state.selected != selections[-1]:
                    selections.append(state.selected)
                self.assertFalse(state.programs[0].running)
                self.assertEqual(state.programs[0].remaining, 52)
                self.assertFalse(state.programs[1].running)
                self.assertEqual(state.programs[1].total, 1920)
                self.assertEqual(state.programs[1].elapsed, 0)
        self.assertEqual(count, meta["state_frames"])
        self.assertEqual(selections, [0, 1])

    def test_user_confirmed_pause_holds_at_52_seconds(self):
        folder = Path(__file__).parent / "fixtures" / "dongle"
        meta = json.loads((folder / "pi-p1-paused-0052.json").read_text())
        raw = (folder / "pi-p1-paused-0052.bin").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])
        splitter = FrameSplitter()
        states = []
        for offset in range(0, len(raw), 8):
            report = normalize_report(raw[offset:offset + 8], report_id_slot=False)
            for frame in splitter.feed(report.payload):
                if isinstance(frame, Frame) and frame.type == TYPE_STATE:
                    states.append(decode_state(frame))
        self.assertEqual(len(states), 112)
        self.assertTrue(all(s.programs[0].running for s in states[:3]))
        self.assertEqual(len(states[3:]), 109)
        for state in states[3:]:
            self.assertEqual(state.selected, 0)
            self.assertFalse(state.programs[0].running)
            self.assertEqual(state.programs[0].total, 60)
            self.assertEqual(state.programs[0].elapsed, 8)
            self.assertEqual(state.programs[0].remaining, 52)
            self.assertEqual(state.checksum_status, CHECKSUM_ABSENT)

    def test_user_started_minute_crosses_zero_without_display_overtime(self):
        folder = Path(__file__).parent / "fixtures" / "dongle"
        meta = json.loads((folder / "pi-p1-running-through-zero.json").read_text())
        raw = (folder / "pi-p1-running-through-zero.bin").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])
        splitter = FrameSplitter()
        states = []
        for offset in range(0, len(raw), 8):
            report = normalize_report(raw[offset:offset + 8], report_id_slot=False)
            self.assertFalse(report.truncated)
            for frame in splitter.feed(report.payload):
                if isinstance(frame, Frame) and frame.type == TYPE_STATE:
                    states.append(decode_state(frame))
        self.assertEqual(len(states), meta["state_frames"])
        self.assertFalse(states[0].programs[0].running)
        first_run = next(i for i, state in enumerate(states) if state.programs[0].running)
        elapsed_changes = []
        for state in states:
            self.assertEqual(state.selected, 0)
            self.assertEqual(state.programs[0].total, 60)
            self.assertTrue(state.counts_down)
            self.assertFalse(state.continue_after_zero)
            self.assertEqual(state.checksum_status, CHECKSUM_ABSENT)
            elapsed = state.programs[0].elapsed
            if not elapsed_changes or elapsed != elapsed_changes[-1]:
                elapsed_changes.append(elapsed)
        self.assertTrue(all(state.programs[0].running for state in states[first_run:]))
        self.assertEqual(elapsed_changes, list(range(72)))
        self.assertEqual(states[-1].programs[0].remaining, -11)
        # Owner observed 0:00 after expiry. Negative raw arithmetic is preserved;
        # future rendering must honor stop-at-zero instead of showing overtime.
        self.assertEqual(splitter.terminated, 0)

    def test_user_confirmed_p1_stopped_at_one_minute(self):
        folder = Path(__file__).parent / "fixtures" / "dongle"
        meta = json.loads((folder / "pi-p1-stopped-0100.json").read_text())
        raw = (folder / "pi-p1-stopped-0100.bin").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])
        self.assertEqual(len(raw) % 8, 0)
        splitter = FrameSplitter()
        states = []
        for offset in range(0, len(raw), 8):
            report = normalize_report(raw[offset:offset + 8], report_id_slot=False)
            self.assertEqual(report.kind, STREAM)
            self.assertFalse(report.truncated)
            # Deliberately split payloads at different positions. USB report
            # boundaries must not be mistaken for timer packet boundaries.
            boundary = (offset // 8) % (len(report.payload) + 1)
            frames = splitter.feed(report.payload[:boundary]) + splitter.feed(report.payload[boundary:])
            for frame in frames:
                if isinstance(frame, Frame) and frame.type == TYPE_STATE:
                    states.append(decode_state(frame))
        self.assertEqual(len(states), meta["state_frames"])
        # Preserve the old state observed briefly at opening; do not label it
        # as the physical 1:00 state or pretend it was never received.
        previous = states[:meta["initial_previous_state_frames"]]
        self.assertTrue(all(s.programs[0].total == 1800 and s.programs[0].running for s in previous))
        stopped = states[len(previous):]
        self.assertEqual(len(stopped), meta["stopped_0100_frames"])
        for state in stopped:
            self.assertEqual(state.selected, 0)
            self.assertFalse(state.programs[0].running)
            self.assertEqual(state.programs[0].total, 60)
            self.assertEqual(state.programs[0].elapsed, 0)
            self.assertEqual(state.programs[0].remaining, 60)
            self.assertEqual(state.checksum_status, CHECKSUM_ABSENT)
        self.assertEqual(splitter.terminated, 0)


if __name__ == "__main__":
    unittest.main()
