"""Limitimer byte-stream framing and state-packet decoding.

Original implementation. The frame layout and field positions follow the
reverse engineering in Depili/limitimer (GPL-2.0-or-later, see
docs/limitimer-protocol.md), checked against that project's RS-485 captures.
Pi/VC-2000PC captures now confirm framing and P1 stopped at 1:00. Other timer
states remain to be checked; these dongle frames carry absent (zero) checksums.

Wire frame: 81, 7-bit body bytes (second byte is the type), 83, two checksum
bytes, then FF on RS-485. The checksum is CRC-16/MODBUS over 81..83 inclusive,
high byte first. Upstream wire captures end frames with FF; our sustained
dongle capture omits it, so the terminator is optional here.
"""
from dataclasses import dataclass

START = 0x81
CHECKSUM_MARK = 0x83
TERMINATOR = 0xFF

TYPE_STATE = 0x00
TYPE_SYNC = 0x10

STATE_BODY_LENGTH = 52   # 81 through 83 inclusive
MAX_BODY_LENGTH = 256    # Resynchronize rather than grow without bound

CHECKSUM_VALID = "valid"
CHECKSUM_ABSENT = "absent"    # Both bytes zero; seen from some senders, proves nothing
CHECKSUM_INVALID = "invalid"


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


@dataclass(frozen=True)
class Frame:
    body: bytes       # 81 through 83 inclusive
    checksum: bytes   # Two bytes as received

    @property
    def type(self):
        return self.body[1] if len(self.body) > 2 else None

    @property
    def checksum_status(self):
        if self.checksum == b"\0\0":
            return CHECKSUM_ABSENT
        crc = crc16_modbus(self.body)
        return CHECKSUM_VALID if self.checksum == bytes((crc >> 8, crc & 0xFF)) else CHECKSUM_INVALID


@dataclass(frozen=True)
class Discarded:
    data: bytes
    reason: str


class FrameSplitter:
    """Reassembles frames from one source's byte stream. Use one per source."""

    def __init__(self):
        self.buffer = bytearray()
        self.state = "seek"
        self.terminated = 0     # Frames followed by FF
        self.unterminated = 0   # Frames followed by anything else

    def feed(self, data):
        out = []
        for byte in data:
            self._byte(byte, out)
        return out

    def _discard(self, out, reason):
        if self.buffer:
            out.append(Discarded(bytes(self.buffer), reason))
        self.buffer.clear()

    def _start(self):
        self.buffer.append(START)
        self.state = "body"

    def _byte(self, byte, out):
        if self.state == "after":
            self.state = "seek"
            if byte == TERMINATOR:
                self.terminated += 1
                return
            self.unterminated += 1
        if self.state == "seek":
            if byte == START:
                self._discard(out, "outside frame")
                self._start()
            else:
                self.buffer.append(byte)
        elif self.state == "body":
            if byte == CHECKSUM_MARK:
                self.buffer.append(byte)
                self.state = "checksum"
            elif byte == START:
                self._discard(out, "restart before checksum mark")
                self._start()
            elif byte & 0x80:
                self.buffer.append(byte)
                self._discard(out, "control byte in body")
                self.state = "seek"
            elif len(self.buffer) >= MAX_BODY_LENGTH:
                self.buffer.append(byte)
                self._discard(out, "body too long")
                self.state = "seek"
            else:
                self.buffer.append(byte)
        elif self.state == "checksum":
            # Checksum bytes are 8-bit and may look like control bytes.
            self.buffer.append(byte)
            self.state = "checksum2"
        else:
            out.append(Frame(bytes(self.buffer[:-1]), bytes((self.buffer[-1], byte))))
            self.buffer.clear()
            self.state = "after"


@dataclass(frozen=True)
class Program:
    flags: int        # Bits: 1 run, 2 blink, 4 beep, 8 seconds-adjust; others unknown
    unknown: int      # Byte after flags; meaning not established
    total: int        # Seconds
    sumup: int        # Seconds; warning (yellow) threshold
    elapsed: int      # Seconds

    @property
    def running(self):
        return bool(self.flags & 0x01)

    @property
    def blink(self):
        return bool(self.flags & 0x02)

    @property
    def beep(self):
        return bool(self.flags & 0x04)

    @property
    def seconds_adjust(self):
        return bool(self.flags & 0x08)

    @property
    def remaining(self):
        """Seconds to zero; negative in overtime."""
        return self.total - self.elapsed


@dataclass(frozen=True)
class State:
    sequence: int
    selected: int          # Program index 0-3 as sent (P1 = 0)
    config_high: int
    config_low: int
    programs: tuple
    trailer: int           # Byte before 83; meaning not established
    checksum_status: str

    # Configuration bits as labelled by upstream; unverified on our controller.
    @property
    def counts_down(self):
        return bool(self.config_low & 0x08)

    @property
    def programs_minutes_seconds(self):
        return bool(self.config_low & 0x04)

    @property
    def session_minutes_seconds(self):
        return bool(self.config_low & 0x02)

    @property
    def continue_after_zero(self):
        return bool(self.config_low & 0x10)

    @property
    def beep_loud(self):
        return bool(self.config_low & 0x20)

    @property
    def beep_type(self):
        return (self.config_high & 0x01) << 1 | (self.config_low & 0x40) >> 6

    @property
    def permit_changes(self):
        return bool(self.config_high & 0x20)


def _seconds(body, offset):
    return body[offset] << 14 | body[offset + 1] << 7 | body[offset + 2]


def decode_state(frame):
    """Decode a complete state frame. Raises ValueError rather than guessing.

    Frames with an absent (zero) checksum are decoded but marked; with no
    checksum, exact length is the only protection against dropped bytes.
    """
    if frame.type != TYPE_STATE:
        raise ValueError("Not a state frame")
    if len(frame.body) != STATE_BODY_LENGTH:
        raise ValueError(f"State frame body is {len(frame.body)} bytes, expected {STATE_BODY_LENGTH}")
    status = frame.checksum_status
    if status == CHECKSUM_INVALID:
        raise ValueError("State frame checksum mismatch")
    body = frame.body
    programs = tuple(
        Program(body[o], body[o + 1], _seconds(body, o + 2), _seconds(body, o + 5), _seconds(body, o + 8))
        for o in range(6, 50, 11))
    return State(body[4], body[5], body[2], body[3], programs, body[50], status)
