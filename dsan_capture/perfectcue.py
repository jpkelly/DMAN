"""Original decoder for framed cues observed via emulator + VC-2000PC.

Captures establish 81 0F 01 value 83, with 00 = Next and 01 = Previous.
This is NOT the bare serial protocol documented upstream. Real PerfectCue,
other values and release semantics remain unverified. No checksum is present
in these observed five-byte messages.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CueFrame:
    raw: bytes
    value: int

    @property
    def name(self):
        return {0: 'next', 1: 'previous'}.get(self.value)


class CueStreamDecoder:
    """Bounded framing across HID reads; unknown values retained explicitly."""
    def __init__(self):
        self.buffer = bytearray()
        self.discarded_bytes = 0
        self.rejected_frames = 0

    def feed(self, payload):
        frames = []
        for byte in payload:
            if byte == 0x81:
                self.discarded_bytes += len(self.buffer)
                self.buffer = bytearray((byte,))
                continue
            if not self.buffer:
                self.discarded_bytes += 1
                continue
            self.buffer.append(byte)
            if len(self.buffer) < 5:
                continue
            raw = bytes(self.buffer)
            self.buffer.clear()
            if raw[1:3] != b'\x0f\x01' or raw[4] != 0x83 or raw[3] >= 0x80:
                self.rejected_frames += 1
                self.discarded_bytes += len(raw)
                continue
            frames.append(CueFrame(raw, raw[3]))
        return frames
