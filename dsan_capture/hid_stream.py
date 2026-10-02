"""HID envelope layer: DSAN dongle input reports -> timer byte stream.

Report layout comes from static analysis of the vendor USB library (see
docs/development/dongle-research.md, "Input reports wrap a byte stream"). It has now been
exercised on sustained Pi/hidraw input; see the labelled stopped-1:00 fixture.

Normalizing one report is stateless. Frame assembly across reports belongs to a
per-source decoder, so separate dongles never share a buffer here.
"""
from dataclasses import dataclass

TAG_EXTENDED_COUNT = 0x7F
TAG_STATUS = 0x80

STREAM = "stream"
STATUS = "status"
OTHER = "other"


@dataclass(frozen=True)
class Report:
    kind: str           # STREAM, STATUS or OTHER
    payload: bytes      # Stream bytes for STREAM; the report after any ID slot otherwise
    declared: int = 0   # Count the report declared (STREAM only)
    truncated: bool = False  # Declared count exceeded the received bytes


def normalize_report(report, *, report_id_slot):
    """Classify one input report.

    report_id_slot must be stated by the caller: True for Windows ReadFile
    buffers (a leading report-ID slot), False for raw libusb interrupt reads and
    HIDAPI reads of this unnumbered report. Never guess it from the data.
    """
    report = bytes(report)
    body = report[1:] if report_id_slot else report
    if not body:
        raise ValueError("Empty input report")
    tag = body[0]
    if tag < TAG_EXTENDED_COUNT:
        start, declared = 1, tag
    elif tag == TAG_EXTENDED_COUNT:
        if len(body) < 2:
            return Report(STREAM, b"", 0, truncated=True)
        start, declared = 2, body[1]
    elif tag == TAG_STATUS:
        return Report(STATUS, body)
    else:
        return Report(OTHER, body)
    payload = body[start:start + declared]
    return Report(STREAM, payload, declared, truncated=len(payload) < declared)
