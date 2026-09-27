import argparse
import json
import math
import sys
import time
from pathlib import Path

from .discovery import difference, inventory, usb_descriptors
from .session import SessionWriter, annotate, hex_lines, replay, save_json, utc_now, validate


def number(value):
    return int(value, 0)


def positive(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def nonnegative(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return value


def parser():
    p = argparse.ArgumentParser(description="DSAN receive-only discovery/capture. Compatibility and decoding are unverified.")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover", help="Snapshot serial, HID, and native USB inventories without opening ports")
    d.add_argument("--out", required=True)
    d.add_argument("--note", default="Connection state unspecified")
    d = sub.add_parser("diff", help="Compare snapshots; changes do not prove compatibility")
    d.add_argument("before")
    d.add_argument("after")
    d = sub.add_parser("inspect-usb", help="Read USB configuration/interface/endpoint descriptors only")
    d.add_argument("--vid", type=number, required=True)
    d.add_argument("--pid", type=number, required=True)
    d.add_argument("--out", required=True)
    d = sub.add_parser("inspect-hid", help="Read the advertised HID report descriptor with a standard USB IN request")
    for key in ("vid", "pid", "bus", "address", "interface"):
        d.add_argument("--" + key, type=number, required=True)
    d.add_argument("--timeout-ms", type=positive, default=1000)
    d.add_argument("--out", required=True)
    d = sub.add_parser("capture", help="Receive only from one explicitly selected transport")
    d.add_argument("--out", required=True, help="New session directory (never overwritten)")
    d.add_argument("--label", required=True, help="Observed timer state, or explicitly unknown")
    d.add_argument("--timer-model", required=True)
    d.add_argument("--signal-path", required=True, help="Actual controller/port/cable/adapter path, or unknown")
    d.add_argument("--seconds", type=nonnegative, default=10, help="Duration; 0 means until Ctrl-C")
    d.add_argument("--quiet", action="store_true", help="Hide live hex; recording is unchanged")
    transports = d.add_subparsers(dest="transport", required=True)
    s = transports.add_parser("serial", help="Only after a serial interface and settings have been established")
    s.add_argument("--port", required=True)
    s.add_argument("--baud", type=positive, required=True)
    s.add_argument("--data-bits", type=int, choices=(5, 6, 7, 8), required=True)
    s.add_argument("--parity", choices=("N", "E", "O", "M", "S"), required=True)
    s.add_argument("--stop-bits", type=float, choices=(1, 1.5, 2), required=True)
    s = transports.add_parser("hid", help="Preserve each input report without stripping presumed headers")
    s.add_argument("--path-hex", required=True)
    s.add_argument("--read-size", type=positive, required=True, help="At least maximum input report length incl. ID, from descriptors")
    s = transports.add_parser("usb-interrupt", help="Explicit interrupt-IN; no driver detachment or configuration changes")
    for key in ("vid", "pid", "bus", "address", "interface", "endpoint"):
        s.add_argument("--" + key, type=number, required=True)
    s.add_argument("--read-timeout-ms", type=positive, default=100, help="USB input wait, 1–5000 ms; no device settings changed")
    s.add_argument("--send-limitimer-init", action="store_true", help="OPT-IN OUTPUT: send one 8D 00 HID output report to this device only, after reading has started")
    s.add_argument("--init-after", type=nonnegative, default=2, help="Seconds of receive-only baseline before the output (default 2)")
    d = sub.add_parser("annotate", help="Append a separate note without modifying acquisition data")
    d.add_argument("session")
    d.add_argument("text")
    d.add_argument("--at", type=nonnegative, help="Observed seconds from session start; omit if unknown")
    for command in ("replay", "verify"):
        d = sub.add_parser(command)
        d.add_argument("session")
        if command == "replay":
            d.add_argument("--speed", type=nonnegative, default=0, help="0 = immediate, 1 = recorded timing, 2 = double speed")
    return p


def capture(args):
    from .transport import HidReceiver, SerialReceiver, UsbReceiver
    if Path(args.out).exists():
        raise FileExistsError("Session directory already exists; choose a new name")
    from .init_output import limitimer_init_request, send
    init = limitimer_init_request(args.interface) if getattr(args, "send_limitimer_init", False) else None
    if init:
        print(f"OUTPUT ENABLED: will send one SET_REPORT {init['bmRequestType']:#04x}/{init['bRequest']:#04x} wValue={init['wValue']:#06x} wIndex={init['wIndex']} data={init['data'].hex(' ')}", flush=True)
    snapshot = inventory()
    session = SessionWriter(args.out, {"label": args.label, "timer_model": args.timer_model, "signal_path": args.signal_path, "inventory": snapshot, "requested_settings": vars(args), "receive_only": init is None})
    receiver = None
    reason = "duration"
    summary = {"interface_opened": False, "reads_with_data": 0, "empty_reads": 0}
    try:
        session.event("opening")
        if args.transport == "serial":
            receiver = SerialReceiver(args.port, args.baud, args.data_bits, args.parity, args.stop_bits)
        elif args.transport == "hid":
            receiver = HidReceiver(args.path_hex, args.read_size)
        else:
            receiver = UsbReceiver(args.vid, args.pid, args.bus, args.address, args.interface, args.endpoint, timeout_ms=args.read_timeout_ms)
        summary["interface_opened"] = True
        save_json(Path(args.out) / "connection.json", {"device": receiver.info, "settings": receiver.settings})
        session.event("connected")
        print("Receiving only. Ctrl-C stops. No decoder is active." if init is None else "Receiving; one output pending. Ctrl-C stops. No decoder is active.", flush=True)
        started = time.monotonic()
        next_status = started + 2
        while not args.seconds or time.monotonic() - started < args.seconds:
            reads = summary["reads_with_data"] + summary["empty_reads"]
            if init and reads and time.monotonic() - started >= args.init_after:
                # Reading has already started, as in the vendor reader-before-write order.
                fields = {"bmRequestType": init["bmRequestType"], "bRequest": init["bRequest"], "wValue": init["wValue"], "wIndex": init["wIndex"], "data_hex": init["data"].hex()}
                session.event("tx-request", target={"bus": args.bus, "address": args.address, "interface": args.interface}, **fields)
                try:
                    written = send(receiver.device, init)
                    session.event("tx-result", written=written)
                    print(f"{utc_now()} TX sent; device accepted {written} bytes", flush=True)
                except Exception as exc:
                    # Record and keep receiving; never retry or try other messages.
                    session.event("tx-result", error=f"{type(exc).__name__}: {exc}")
                    print(f"{utc_now()} TX failed: {exc}", flush=True)
                init = None
            data = receiver.read()
            # Timestamp immediately after read, before disk IO or terminal output.
            timestamp = utc_now()
            elapsed = time.monotonic_ns() - session.origin_ns
            if data:
                summary["reads_with_data"] += 1
                event = session.receive(data, timestamp, elapsed)
                if not args.quiet:
                    print(f"{timestamp} +{elapsed / 1e9:.6f}s RX {len(data)} bytes")
                    print("\n".join(hex_lines(data, event["offset"])), flush=True)
            else:
                summary["empty_reads"] += 1
            now = time.monotonic()
            if now >= next_status:
                session.event("receive-status", **summary)
                next_status = now + 2
    except KeyboardInterrupt:
        reason = "user-stop"
    except Exception as exc:
        reason = "transport-or-recording-error"
        session.event("error", message=str(exc))
        raise
    finally:
        try:
            if receiver is not None:
                receiver.close()
        except Exception as exc:
            reason = "transport-close-error"
            session.event("error", message=str(exc), stage="close")
            raise
        finally:
            session.close(reason, receive_summary=summary)
            print(f"Saved {session.offset} bytes to {args.out}; end={reason}", flush=True)
            if summary["interface_opened"] and not session.offset:
                print(f"Interface opened, but no input bytes arrived ({summary['empty_reads']} empty reads). Timer data remains unverified.", flush=True)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "discover":
            data = inventory()
            data["note"] = args.note
            save_json(args.out, data)
            print(json.dumps(data, indent=2))
        elif args.command == "diff":
            print(json.dumps(difference(json.loads(Path(args.before).read_text()), json.loads(Path(args.after).read_text())), indent=2))
        elif args.command == "inspect-usb":
            data = {"utc": utc_now(), "devices": usb_descriptors(args.vid, args.pid)}
            save_json(args.out, data)
            print(json.dumps(data, indent=2))
        elif args.command == "capture":
            capture(args)
        elif args.command == "inspect-hid":
            from .hid_inspection import inspect_hid
            if Path(args.out).exists():
                raise FileExistsError("Output already exists; choose a new name")
            data = inspect_hid(args.vid, args.pid, args.bus, args.address, args.interface, args.timeout_ms)
            save_json(args.out, data)
            print(json.dumps(data, indent=2))
            if data["status"] != "ok":
                return 1
        elif args.command == "annotate":
            annotate(args.session, args.text, args.at)
        elif args.command == "verify":
            print(json.dumps(validate(args.session), indent=2))
        elif args.command == "replay":
            print((Path(args.session) / "metadata.json").read_text())
            for warning in validate(args.session)["warnings"]:
                print("WARNING: " + warning, file=sys.stderr)
            for event, data in replay(args.session, args.speed):
                print(json.dumps(event))
                if data:
                    print("\n".join(hex_lines(data, event["offset"])))
            for path in sorted((Path(args.session) / "annotations").glob("*.json")):
                print("NOTE " + path.read_text().strip())
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
