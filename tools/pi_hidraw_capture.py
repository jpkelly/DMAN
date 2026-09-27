"""Bounded Linux HID capture to tmpfs, then persist and verify the session.

Uses the kernel HID driver, without detaching it. Reviewed per-role initialization
outputs are explicitly opt-in. Active tmpfs data does not survive power
loss; raw/session files are copied to the requested durable directory on exit.
"""
import argparse
import json
import os
import platform
import re
import select
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dsan_capture.init_output import LIMITIMER_INIT, REPORT_LENGTH
from dsan_capture.session import SessionWriter, save_json, utc_now, validate

EXPECTED_DESCRIPTOR = bytes.fromhex(
    "06a0ff0901a1010903150026ff00750895088102"
    "0904150026ff00750895409102"
    "0905150026ff0075089540b102c0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Exact /dev/hidrawN path")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--hardware-role", choices=("unknown", "limitimer", "perfectcue"), default="limitimer")
    parser.add_argument("--controller-model", help="Observed model; do not infer a PerfectCue model")
    parser.add_argument("--signal-path", default="Not recorded")
    parser.add_argument("--seconds", type=int, default=10, choices=range(1, 121), metavar="1..120")
    init_flags = parser.add_mutually_exclusive_group()
    init_flags.add_argument("--send-limitimer-init", action="store_true")
    init_flags.add_argument("--send-perfectcue-init", action="store_true")
    args = parser.parse_args()
    if args.send_limitimer_init and args.hardware_role != "limitimer":
        parser.error("Limitimer initialization cannot be sent to a PerfectCue source")
    if args.send_perfectcue_init and args.hardware_role != "perfectcue":
        parser.error("PerfectCue initialization requires a PerfectCue source")
    send_init = args.send_limitimer_init or args.send_perfectcue_init
    init_bytes = bytes((0x8D, 0x01)) if args.send_perfectcue_init else LIMITIMER_INIT
    if platform.system() != "Linux" or not Path("/dev/shm").is_dir():
        raise RuntimeError("This diagnostic requires Linux with /dev/shm")
    if not re.fullmatch(r"/dev/hidraw[0-9]+", args.device):
        raise ValueError("Select an exact /dev/hidrawN device")
    sysfs = (Path("/sys/class/hidraw") / Path(args.device).name / "device").resolve()
    identity = dict(line.split("=", 1) for line in (sysfs / "uevent").read_text().splitlines() if "=" in line)
    if identity.get("HID_ID", "").upper() != "0003:00000483:0000101A":
        raise ValueError("Selected HID device is not the expected USB VID/PID")
    descriptor = (sysfs / "report_descriptor").read_bytes()
    if descriptor != EXPECTED_DESCRIPTOR:
        raise ValueError("HID report descriptor differs from the verified 8/64/64-byte layout")
    args.out.mkdir(parents=True, exist_ok=False)
    temporary = Path(tempfile.mkdtemp(prefix="dsan-hidraw-", dir="/dev/shm"))
    session = SessionWriter(temporary / "session", {
        "label": args.label, "timer_model": args.controller_model or ("PRO-2000" if args.hardware_role == "limitimer" else "unknown"),
        "hardware_role": args.hardware_role, "signal_path": args.signal_path, "transport": "linux-hidraw",
        "receive_only": not send_init, "device_path": args.device,
        "sysfs_path": str(sysfs), "device_identity": identity,
        "report_descriptor_hex": descriptor.hex(), "input_report_id_slot": False,
        "storage": "tmpfs during acquisition, copied to requested directory after closing",
        "clock_note": "Pi realtime may be unsynchronized; use elapsed_ns and host clock calibration",
    })
    # Make annotations possible while raw acquisition stays on tmpfs.
    shutil.copyfile(temporary / "session" / "metadata.json", args.out / "metadata.json")
    fd = None
    reason = "duration"
    counts = {"reads_with_data": 0, "empty_reads": 0, "bytes_before_init": 0, "bytes_after_init": 0}
    sent = False
    failed = False
    try:
        fd = os.open(args.device, (os.O_RDWR if send_init else os.O_RDONLY) | os.O_NONBLOCK)
        session.event("connected")
        started = time.monotonic()
        next_status = started + 2
        print("HID capture active; writes go to tmpfs during acquisition.", flush=True)
        while time.monotonic() - started < args.seconds:
            if send_init and not sent and time.monotonic() - started >= 2:
                sent = True
                report = b"\x00" + init_bytes + bytes(REPORT_LENGTH - len(init_bytes))
                session.event("tx-request", api="hidraw write", target=args.device,
                              report_id_slot=True, data_hex=report.hex())
                try:
                    written = os.write(fd, report)
                    session.event("tx-result", written=written, complete=written == len(report))
                except OSError as exc:
                    session.event("tx-result", error=str(exc))
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                data = os.read(fd, 64)
                if not data:
                    raise OSError("HID device returned EOF")
                session.receive(data, utc_now(), time.monotonic_ns() - session.origin_ns)
                counts["reads_with_data"] += 1
                counts["bytes_after_init" if sent else "bytes_before_init"] += len(data)
                if session.offset >= 16 * 1024 * 1024:
                    raise RuntimeError("16 MiB diagnostic capture limit reached")
            else:
                counts["empty_reads"] += 1
            if time.monotonic() >= next_status:
                status = session.event("receive-status", **counts)
                status_path = args.out / "live-status.json.tmp"
                status_path.write_text(json.dumps(status) + "\n")
                status_path.replace(args.out / "live-status.json")
                next_status = time.monotonic() + 2
    except KeyboardInterrupt:
        reason = "user-stop"
    except Exception as exc:
        reason, failed = "error", True
        session.event("error", message=repr(exc))
        print(f"Capture error: {exc}", file=sys.stderr, flush=True)
    finally:
        if fd is not None:
            os.close(fd)
        session.close(reason, receive_summary=counts)
        # Keep tmpfs recovery files if durable copy or verification fails.
        try:
            shutil.copytree(temporary / "session", args.out, dirs_exist_ok=True)
            for path in args.out.iterdir():
                if path.is_file():
                    with path.open("rb") as copied:
                        os.fsync(copied.fileno())
            result = validate(args.out)
            save_json(args.out / "persistence.json", {"saved_utc": utc_now(), "integrity": result})
        except Exception:
            print(f"Copy failed; recover raw session from {temporary}", file=sys.stderr)
            raise
        shutil.rmtree(temporary)
        print(json.dumps({"session": str(args.out), "bytes": session.offset,
                          "reason": reason, **counts, "integrity": result}, indent=2), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
