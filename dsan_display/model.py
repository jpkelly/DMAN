"""Per-source decoding and freshness. Never advances a timer locally."""
import threading
import time
from dsan_capture.hid_stream import normalize_report, STREAM
from dsan_capture.limitimer import FrameSplitter, Frame, TYPE_STATE, decode_state
from dsan_capture.perfectcue import CueStreamDecoder


class Source:
    def __init__(self, identity, label, kind, target, stale_after=2.0, warmup=1.0, role='limitimer'):
        if role not in ('limitimer', 'perfectcue'):
            raise ValueError('Unknown hardware role')
        self.role = role
        self.identity, self.label, self.kind, self.target = identity, label, kind, target
        self.stale_after, self.warmup = stale_after, warmup
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with self.lock:
            self.splitter = FrameSplitter()
            self.cue_decoder = CueStreamDecoder()
            self.state = None
            self.last_received = None
            self.connected_at = None
            self.status, self.error = 'starting', None
            self.reports = self.states = self.rejected = 0
            self.cue = None
            self.cue_display_received = None
            self.cue_sequence = self.unknown_cue_bytes = 0
            self.last_report_hex = None

    def connected(self, now=None):
        with self.lock:
            self.connected_at = time.monotonic() if now is None else now
            self.status = 'connected'

    def end(self, status, error=None):
        with self.lock:
            self.status, self.error = status, error

    def receive(self, raw, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self.reports += 1
            self.last_report_hex = raw.hex(' ')
            report = normalize_report(raw, report_id_slot=False)
            if report.truncated:
                self.rejected += 1
                self.splitter = FrameSplitter()
                self.cue_decoder = CueStreamDecoder()
                return
            if report.kind != STREAM:
                return
            if self.role == 'perfectcue':
                discarded = self.cue_decoder.discarded_bytes
                rejected = self.cue_decoder.rejected_frames
                frames = self.cue_decoder.feed(report.payload)
                self.unknown_cue_bytes += self.cue_decoder.discarded_bytes - discarded
                self.rejected += self.cue_decoder.rejected_frames - rejected
                for frame in frames:
                    if frame.name is None:
                        self.unknown_cue_bytes += len(frame.raw)
                        continue
                    self.cue = frame.name
                    self.cue_sequence += 1
                    self.last_received = now
                    if self.connected_at is not None and now - self.connected_at >= self.warmup:
                        self.cue_display_received = now
                return
            for frame in self.splitter.feed(report.payload):
                if not isinstance(frame, Frame) or frame.type != TYPE_STATE:
                    continue
                try:
                    state = decode_state(frame)
                    if state.selected not in range(4):
                        raise ValueError('Selected program out of range')
                except ValueError:
                    self.rejected += 1
                    continue
                self.state = state
                self.states += 1
                self.last_received = now

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            age = None if self.last_received is None else max(0, now - self.last_received)
            warming = self.connected_at is not None and now - self.connected_at < self.warmup
            fresh = self.status == 'connected' and age is not None and age <= self.stale_after and not warming
            programs = []
            if self.state:
                for i, program in enumerate(self.state.programs):
                    raw = program.remaining if self.state.counts_down else program.elapsed
                    seconds = max(0, raw) if self.state.counts_down and not self.state.continue_after_zero else raw
                    programs.append({'index': i, 'seconds': seconds, 'raw_seconds': raw,
                                     'running': program.running, 'total': program.total,
                                     'elapsed': program.elapsed, 'minutes_seconds': self.state.programs_minutes_seconds if i < 3 else self.state.session_minutes_seconds})
            return {'id': self.identity, 'label': self.label, 'kind': self.kind, 'target': self.target, 'role': self.role,
                    'status': self.status, 'fresh': fresh, 'warming': warming, 'age': age,
                    'selected': self.state.selected if self.state else None, 'programs': programs,
                    'checksum': self.state.checksum_status if self.state else None,
                    'reports': self.reports, 'states': self.states, 'rejected': self.rejected,
                    'error': self.error,
                    'cue': self.cue, 'cue_sequence': self.cue_sequence,
                    'cue_active': self.role == 'perfectcue' and fresh and self.cue_display_received is not None and now - self.cue_display_received <= 1.0,
                    'cue_mapping_verified': False, 'unknown_cue_bytes': self.unknown_cue_bytes,
                    'cue_mapping_evidence': 'Emulator + dongle captures; real PerfectCue untested',
                    'last_report_hex': self.last_report_hex}
