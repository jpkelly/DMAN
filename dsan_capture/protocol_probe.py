"""Classify observed HID traffic, not dongle identity or physical switch position.

No hardware access or output commands. Run against a saved HID capture so all
results can be repeated. Silence and conflicting evidence stay inconclusive.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from .hid_stream import normalize_report, STREAM
from .limitimer import Frame, FrameSplitter, TYPE_STATE, decode_state
from .perfectcue import CueStreamDecoder
from .session import replay


class ProtocolEvidence:
    def __init__(self):
        self.timer = FrameSplitter()
        self.cue = CueStreamDecoder()
        self.reports = self.empty_reports = self.truncated_reports = 0
        self.timer_frames = self.cue_frames = self.invalid_timer_frames = 0
        self.checksums, self.cue_values = Counter(), Counter()

    def feed(self, raw):
        self.reports += 1
        report = normalize_report(raw, report_id_slot=False)
        if report.truncated:
            self.truncated_reports += 1
            self.timer, self.cue = FrameSplitter(), CueStreamDecoder()
            return
        if report.kind != STREAM:
            return
        if not report.payload:
            self.empty_reports += 1
            return
        for frame in self.timer.feed(report.payload):
            if not isinstance(frame, Frame) or frame.type != TYPE_STATE:
                continue
            try:
                state = decode_state(frame)
                if state.selected not in range(4):
                    raise ValueError('Invalid selected program')
            except ValueError:
                self.invalid_timer_frames += 1
                continue
            self.timer_frames += 1
            self.checksums[state.checksum_status] += 1
        for frame in self.cue.feed(report.payload):
            if frame.name is not None:
                self.cue_frames += 1
                self.cue_values[frame.name] += 1

    def result(self):
        if self.timer_frames and self.cue_frames:
            protocol = 'ambiguous'
        elif self.timer_frames >= 3:
            protocol = 'limitimer'
        elif self.cue_frames >= 2:
            protocol = 'perfectcue-framed'
        else:
            protocol = 'unknown'
        return {'observed_protocol': protocol, 'reports_analyzed': self.reports,
                'empty_reports': self.empty_reports, 'truncated_reports': self.truncated_reports,
                'limitimer_state_frames': self.timer_frames,
                'limitimer_invalid_frames': self.invalid_timer_frames,
                'limitimer_checksums': dict(self.checksums),
                'cue_frames': self.cue_frames, 'cue_values': dict(self.cue_values),
                'scope': 'Active traffic only; not physical role, device identity or cold-start mode detection',
                'thresholds': 'Conservative heuristic: 3 timer states or 2 known cue frames; conflicting traffic is ambiguous',
                'cue_evidence': 'Framing currently verified with emulator + dongle, not real PerfectCue controller'}


def analyze(directory, skip_seconds=1.0):
    directory = Path(directory)
    metadata = json.loads((directory / 'metadata.json').read_text())
    transport = metadata.get('transport') or metadata.get('requested_settings', {}).get('transport')
    if transport not in ('linux-hidraw', 'hid', 'usb-interrupt'):
        raise ValueError('Expected a HID-report capture')
    evidence = ProtocolEvidence()
    for event, data in replay(directory):
        if event['kind'] == 'rx' and event['elapsed_ns'] >= skip_seconds * 1e9:
            evidence.feed(data)
    return {**evidence.result(), 'capture': str(directory), 'ignored_initial_seconds': skip_seconds}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.capture), indent=2))
