"""Reviewed, opt-in per-role initialization outputs.

Derived from the vendor application (docs/dongle-research.md): after opening the
dongle, VideoClock for Limitimer writes 8D 00 in a 65-byte Windows HID output
buffer (report-ID slot 0 + 64 bytes). The device has no interrupt-OUT endpoint,
so the standard USB equivalent is HID SET_REPORT (Output, ID 0) on endpoint 0.
The equivalent control transfer was subsequently captured successfully on the
Pi; see docs/pi5-investigation.md. Windows execution remains to be tested.
"""
LIMITIMER_INIT = bytes((0x8D, 0x00))
REPORT_LENGTH = 64

REQUEST_TYPE = 0x21   # Host-to-device, class, interface
SET_REPORT = 0x09
OUTPUT_REPORT_ID0 = 0x0200


def limitimer_init_request(interface):
    """Exact control request fields; nothing is sent here."""
    return {
        "bmRequestType": REQUEST_TYPE,
        "bRequest": SET_REPORT,
        "wValue": OUTPUT_REPORT_ID0,
        "wIndex": interface,
        "data": LIMITIMER_INIT + bytes(REPORT_LENGTH - len(LIMITIMER_INIT)),
    }


def send(device, request, timeout_ms=1000):
    """Issue one control transfer to the given, already-selected device. No retries."""
    return device.ctrl_transfer(request["bmRequestType"], request["bRequest"], request["wValue"], request["wIndex"], request["data"], timeout=timeout_ms)


def send_hid(receiver, role='limitimer'):
    """One reviewed output on an exact, already-open DSAN HID handle; no retry.

    HIDAPI requires the zero report-ID slot on writes, even though its Windows
    backend removes that slot on reads of unnumbered reports.
    """
    if (receiver.info.get('vendor_id'), receiver.info.get('product_id')) != (0x0483, 0x101A):
        raise ValueError('Mode initialization requires DSAN 0483:101A')
    modes = {'limitimer': 0, 'perfectcue': 1}
    if role not in modes:
        raise ValueError('Unknown DSAN hardware role')
    report = bytes((0, 0x8D, modes[role])) + bytes(62)
    written = receiver.device.write(report)
    if written != len(report):
        raise OSError(f'{role} initialization wrote {written!r} of {len(report)} bytes; not retried')
    return written
