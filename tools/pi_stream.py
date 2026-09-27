"""Read-only JSON-lines stream from one explicitly selected DSAN Linux HID node."""
import argparse
import json
import os
import re
import select
import sys
import time
from pathlib import Path
from pi_hidraw_capture import EXPECTED_DESCRIPTOR


def emit(message):
    print(json.dumps(message), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'/dev/hidraw[0-9]+', args.device):
        raise ValueError('Select an exact HID node')
    path = (Path('/sys/class/hidraw') / Path(args.device).name / 'device').resolve()
    info = dict(line.split('=', 1) for line in (path / 'uevent').read_text().splitlines() if '=' in line)
    if info.get('HID_ID', '').upper() != '0003:00000483:0000101A':
        raise ValueError('Selected device is not DSAN 0483:101A')
    if (path / 'report_descriptor').read_bytes() != EXPECTED_DESCRIPTOR:
        raise ValueError('Unexpected report descriptor')
    fd = os.open(args.device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        emit({'kind': 'connected', 'device': args.device})
        heartbeat = time.monotonic()
        while True:
            ready, _, _ = select.select([fd], [], [], 0.5)
            if ready:
                data = os.read(fd, 64)
                if not data:
                    raise OSError('HID disconnected')
                emit({'kind': 'report', 'hex': data.hex()})
            if time.monotonic() - heartbeat >= 1:
                emit({'kind': 'heartbeat'})
                heartbeat = time.monotonic()
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:
        # Avoid a second flush error at interpreter exit after SSH closes.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        try:
            emit({'kind': 'error', 'message': str(exc)})
        except BrokenPipeError:
            pass
        raise SystemExit(1)
