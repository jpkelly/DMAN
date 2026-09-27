"""Read-only control-endpoint liveness watch across a replug.

Polls for 0483:101A and, while present, issues standard GET_STATUS (device)
requests. Sends no class, vendor or output requests. Writes JSON lines.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import usb.core  # noqa: E402
import usb.util  # noqa: E402
from dsan_capture.discovery import usb_backend  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--seconds", type=float, default=90)
    p.add_argument("--interval", type=float, default=0.25)
    p.add_argument("--timeout-ms", type=int, default=200)
    args = p.parse_args()
    backend = usb_backend()
    origin = time.monotonic()
    with open(args.out, "x", encoding="utf-8") as out:
        def record(**fields):
            fields = {"utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "t": round(time.monotonic() - origin, 3), **fields}
            out.write(json.dumps(fields) + "\n")
            out.flush()
            print(json.dumps(fields), flush=True)

        record(kind="ready")
        present = None
        while time.monotonic() - origin < args.seconds:
            devices = list(usb.core.find(find_all=True, idVendor=0x0483, idProduct=0x101A, backend=backend))
            key = [(d.bus, d.address) for d in devices]
            if key != present:
                record(kind="devices", devices=key)
                present = key
            if len(devices) == 1:
                device = devices[0]
                try:
                    status = bytes(device.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=args.timeout_ms))
                    record(kind="get-status", ok=True, data=status.hex())
                except Exception as exc:
                    record(kind="get-status", ok=False, error=f"{type(exc).__name__}: {exc}")
                finally:
                    usb.util.dispose_resources(device)
            time.sleep(args.interval)
        record(kind="end")


if __name__ == "__main__":
    main()
