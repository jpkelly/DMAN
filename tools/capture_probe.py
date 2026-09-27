"""Experiment: take the dongle via libusb's macOS capture mode, then probe and receive.

Hypothesis under test: the dongle hangs when macOS's own driver stack requests its
bogus interface string (index 92). Capture re-enumerates the device without
Apple's drivers attached; this checks whether it then stays responsive.

Requires root on macOS. Capture detaches Apple's drivers but does not reset the
device; --reset then issues a USB port reset while captured. Sends only standard
GET_STATUS / GET_CONFIGURATION / SET_CONFIGURATION(1) and reads the
interrupt-IN endpoint. No class, vendor or output requests.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import usb.core  # noqa: E402
import usb.util  # noqa: E402
from dsan_capture.discovery import usb_backend  # noqa: E402
from dsan_capture.session import SessionWriter, utc_now  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bus", type=int, required=True)
    p.add_argument("--address", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--seconds", type=float, default=20)
    p.add_argument("--reset", action="store_true", help="USB port reset after capture (standard bus reset, no device request)")
    args = p.parse_args()

    session = SessionWriter(args.out, {"label": args.label, "timer_model": "DSAN PRO-2000", "signal_path": "PRO-2000 RJ45 -> VC-2000PC -> USB -> Anker hub -> Mac", "requested_settings": vars(args), "receive_only": True, "experiment": "libusb macOS capture (detach_kernel_driver) then standard requests"})
    summary = {"interface_opened": False, "reads_with_data": 0, "empty_reads": 0}
    reason = "duration"
    device = None

    def step(name, fn):
        try:
            result = fn()
            session.event("probe", step=name, ok=True, result=None if result is None else (bytes(result).hex() if not isinstance(result, int) else result))
            print(f"{utc_now()} {name}: ok {result!r}", flush=True)
            return True
        except Exception as exc:
            session.event("probe", step=name, ok=False, error=f"{type(exc).__name__}: {exc}")
            print(f"{utc_now()} {name}: FAILED {type(exc).__name__}: {exc}", flush=True)
            return False

    try:
        matches = list(usb.core.find(find_all=True, idVendor=0x0483, idProduct=0x101A, bus=args.bus, address=args.address, backend=usb_backend()))
        if len(matches) != 1:
            raise ValueError("Expected exactly one matching device at that bus/address")
        device = matches[0]
        step("get-status-before-capture", lambda: device.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=500))
        step("capture (detach_kernel_driver 0)", lambda: device.detach_kernel_driver(0))
        step("get-status-after-capture", lambda: device.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=1000))
        if args.reset:
            # While captured, libusb uses ResetDevice (port reset) and keeps Apple's drivers detached.
            step("port reset while captured", lambda: device.reset())
            step("get-status-after-reset", lambda: device.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=1000))
        step("get-configuration", lambda: device.ctrl_transfer(0x80, 0x08, 0, 0, 1, timeout=1000))
        step("set-configuration 1", lambda: device.set_configuration(1))
        step("get-status-after-configure", lambda: device.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=1000))
        if not step("claim interface 0", lambda: usb.util.claim_interface(device, 0)):
            raise RuntimeError("Could not claim interface")
        summary["interface_opened"] = True
        started = time.monotonic()
        while time.monotonic() - started < args.seconds:
            try:
                data = bytes(device.read(0x81, 8, timeout=100))
            except usb.core.USBTimeoutError:
                data = b""
            if data:
                summary["reads_with_data"] += 1
                session.receive(data, utc_now(), time.monotonic_ns() - session.origin_ns)
                print(f"{utc_now()} RX {data.hex(' ')}", flush=True)
            else:
                summary["empty_reads"] += 1
        step("get-status-after-reading", lambda: device.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=1000))
    except Exception as exc:
        reason = "error"
        session.event("error", message=f"{type(exc).__name__}: {exc}")
        print(f"Error: {exc}", flush=True)
    finally:
        if device is not None:
            try:
                usb.util.release_interface(device, 0)
            except Exception:
                pass
            usb.util.dispose_resources(device)
        session.close(reason, receive_summary=summary)
        print(f"Saved {session.offset} bytes; {summary}", flush=True)


if __name__ == "__main__":
    main()
