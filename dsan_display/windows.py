"""Windows operator launcher; exact-path bindings, no first-device fallback."""
import argparse
from datetime import datetime, timezone
import json
import logging
import os
import sys
from pathlib import Path

from dsan_capture.discovery import hid_devices
from .__main__ import main as display_main


def dsan_devices():
    return [d for d in hid_devices()
            if (d.get('vendor_id'), d.get('product_id')) == (0x0483, 0x101A)]


def default_data_directory():
    """Frozen one-file apps must never save configuration in their temp bundle."""
    if getattr(sys, 'frozen', False):
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'DSANDisplay'
    return Path.cwd()


def validate_config(config):
    if not isinstance(config, dict) or config.get('schema') != 1:
        raise ValueError('Expected source configuration schema 1')
    sources = config.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('Select at least one dongle')
    paths, labels = set(), set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError('Invalid source entry')
        if source.get('role') not in ('limitimer', 'perfectcue'):
            raise ValueError('Each source needs an explicit limitimer or perfectcue role')
        if type(source.get('initialize')) is not bool:
            raise ValueError('Each source initialize setting must be true or false')
        label, path = source.get('label'), source.get('path_hex')
        if not isinstance(label, str) or not label.strip() or '=' in label:
            raise ValueError('Source labels must be nonempty and cannot contain =')
        if not isinstance(path, str):
            raise ValueError('Source requires a path_hex from HID discovery')
        path = bytes.fromhex(path).hex()
        if not path or path in paths or label.casefold() in labels:
            raise ValueError('Source paths and labels must be nonempty and unique')
        paths.add(path)
        labels.add(label.casefold())
        source['path_hex'] = path
    return config


def launch_arguments(config, devices):
    config = validate_config(config)
    present = {d['path_hex'] for d in devices}
    missing = [s['label'] for s in config['sources'] if s['path_hex'] not in present]
    if missing:
        raise ValueError('Saved dongle(s) missing: ' + ', '.join(missing) +
                         '. Reconnect to the same USB ports or relaunch with --configure. '
                         'No other dongle will be substituted.')
    args = ['--open-browser']
    for source in config['sources']:
        flag = '--perfectcue-hid' if source['role'] == 'perfectcue' else '--hid'
        args += [flag, source['label'] + '=' + source['path_hex']]
        if source['initialize']:
            args += ['--init-hid', source['path_hex']]
    return args


def configure(devices, read=input):
    if not devices:
        raise ValueError('No DSAN 0483:101A HID devices found. Connect the dongle and retry. '
                         'Keep the Windows HID driver; do not replace it with WinUSB.')
    print('Assign each dongle its actual internal hardware role: Limitimer or PerfectCue.')
    print('Identify identical dongles by connecting one at a time during setup.')
    print('The firmware serial string is not a reliable unique identity.')
    for index, device in enumerate(devices, 1):
        path = bytes.fromhex(device['path_hex']).decode('utf-8', errors='replace')
        print(f"{index}. {device.get('product_string', 'DSAN')} | serial: {device.get('serial_number')}")
        print(f'   {path}')
    selection = read('Device numbers, comma separated: ')
    indices = [int(part.strip()) - 1 for part in selection.split(',')]
    if len(set(indices)) != len(indices) or any(i < 0 or i >= len(devices) for i in indices):
        raise ValueError('Select each listed device at most once')
    sources = []
    for index in indices:
        label = read(f'Name for device {index + 1} [Dongle {index + 1}]: ').strip() or f'Dongle {index + 1}'
        role_choice = read('Hardware role: [1] Limitimer, [2] PerfectCue: ').strip()
        if role_choice not in ('1', '2'):
            raise ValueError('Choose hardware role 1 or 2; USB IDs cannot determine the role')
        role = 'limitimer' if role_choice == '1' else 'perfectcue'
        print(f'Startup can send the vendor {role} selection output once to this dongle.')
        print('This does not change firmware or replace the internal hardware role setting.')
        mode = read('Startup: [1] Initialize configured role, [2] Receive only (default): ').strip() or '2'
        if mode not in ('1', '2'):
            raise ValueError('Choose startup mode 1 or 2')
        sources.append({'label': label, 'path_hex': devices[index]['path_hex'],
                        'role': role, 'initialize': mode == '1'})
    return validate_config({'schema': 1, 'sources': sources})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure', action='store_true', help='Choose, name and assign dongle roles again')
    parser.add_argument('--data-dir', type=Path, default=default_data_directory(), help='Folder for saved sources and logs')
    parser.add_argument('--config', type=Path, help='Override the saved source configuration path')
    parser.add_argument('--self-test', action='store_true', help='Check bundled imports and web assets without accessing hardware')
    args = parser.parse_args(argv)
    if args.self_test:
        from .packaging_check import self_test
        self_test()
        return
    args.config = args.config or args.data_dir / 'windows-sources.json'
    logdir = args.data_dir / 'logs'
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / (datetime.now(timezone.utc).strftime('windows-%Y%m%dT%H%M%S-%fZ') + '.log')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(logfile, encoding='utf-8'), logging.StreamHandler()])
    try:
        devices = dsan_devices()
        logging.info('DSAN HID inventory: %s', json.dumps(devices))
        if args.configure or not args.config.exists():
            config = configure(devices)
            # Validate the whole selection before replacing the previous configuration.
            args.config.parent.mkdir(parents=True, exist_ok=True)
            args.config.with_suffix('.tmp').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
            args.config.with_suffix('.tmp').replace(args.config)
        else:
            config = json.loads(args.config.read_text(encoding='utf-8'))
        arguments = launch_arguments(config, devices)
        logging.info('Source configuration: %s', json.dumps(config))
        print('Keep this console open. Ctrl+C stops the display. Diagnostics: ' + str(logfile))
        display_main(arguments)
    except (ValueError, OSError, EOFError) as exc:
        logging.error('%s', exc)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
