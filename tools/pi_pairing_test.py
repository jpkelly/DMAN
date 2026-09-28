"""Exercise the production pairing wizard with Linux sysfs and durable prompts.

No device handles, initialization outputs, or display configuration changes.
An SSH operator answers each numbered prompt by creating answers/NNNN.txt.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dsan_display.windows as launcher


def devices():
    found = []
    for node in sorted(Path('/sys/class/hidraw').glob('*')):
        path = (node / 'device').resolve()
        try:
            identity = dict(line.split('=', 1) for line in (path / 'uevent').read_text().splitlines() if '=' in line)
        except OSError:
            continue
        if identity.get('HID_ID', '').upper() == '0003:00000483:0000101A':
            found.append({'path_hex': ('/dev/' + node.name).encode().hex(),
                          'node': '/dev/' + node.name, 'sysfs_path': str(path),
                          'serial_number': identity.get('HID_UNIQ'),
                          'physical_path': identity.get('HID_PHYS')})
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    args = parser.parse_args()
    args.session.mkdir(parents=True, exist_ok=False)
    (args.session / 'answers').mkdir()
    origin = time.monotonic()
    sequence = 0

    def save(name, data):
        temporary = args.session / (name + '.tmp')
        temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        temporary.replace(args.session / name)

    def event(kind, **fields):
        with (args.session / 'events.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps({'kind': kind, 'elapsed_seconds': time.monotonic() - origin, **fields}) + '\n')

    def enumerate_devices():
        result = devices()
        event('inventory', devices=result)
        return result

    def answer(prompt):
        nonlocal sequence
        number = sequence
        sequence += 1
        event('prompt', number=number, text=prompt)
        save('status.json', {'state': 'waiting', 'number': number, 'prompt': prompt})
        file = args.session / 'answers' / f'{number:04d}.txt'
        while not file.exists():
            if time.monotonic() - origin > 1800:
                raise TimeoutError('Pairing test exceeded 30 minutes; no live configuration changed')
            time.sleep(0.2)
        response = file.read_text(encoding='utf-8').rstrip('\r\n')
        event('answer', number=number, text=response)
        return response

    save('metadata.json', {'test': 'Real Pi enumeration with production guided_configure',
                          'launcher_sha256': hashlib.sha256(Path(launcher.__file__).read_bytes()).hexdigest(),
                          'windows_driver_test': False, 'device_outputs_sent': False})
    try:
        config = launcher.guided_configure(read=answer, enumerate_devices=enumerate_devices)
        current = enumerate_devices()
        launcher.launch_arguments(config, current)  # Validate bindings, never execute.
        save('paired-config.json', config)
        save('status.json', {'state': 'complete', 'config': config, 'devices': current,
                             'device_outputs_sent': False, 'live_config_changed': False})
    except BaseException as exc:
        save('status.json', {'state': 'error', 'error': str(exc), 'live_config_changed': False})
        raise


if __name__ == '__main__':
    main()
