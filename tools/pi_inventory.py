"""Read DSAN HID identity from sysfs without opening devices or sending outputs."""
import json
from pathlib import Path


def devices():
    found = []
    for node in sorted(Path('/sys/class/hidraw').glob('*')):
        path = (node / 'device').resolve()
        try:
            info = dict(line.split('=', 1) for line in (path / 'uevent').read_text().splitlines() if '=' in line)
        except OSError:
            continue
        if info.get('HID_ID', '').upper() == '0003:00000483:0000101A':
            found.append({'path_hex': ('/dev/' + node.name).encode().hex(),
                          'serial_number': info.get('HID_UNIQ'), 'physical_path': info.get('HID_PHYS')})
    return found


if __name__ == '__main__':
    print(json.dumps(devices()))
