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
from .network import listen_address


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


def guided_configure(read=input, enumerate_devices=None, *, prompt_callback=None, notify=None):
    """Assign roles by an observed plug-in sequence, without trusting serial IDs.

    Enumeration only: no streaming handles are opened and no initialization is
    sent until the complete configuration validates and the display starts.
    """
    enumerate_devices = enumerate_devices or dsan_devices

    notify = notify or print

    def ask(prompt, kind='continue', default=''):
        answer = (prompt_callback({'text': prompt, 'kind': kind, 'default': default})
                  if prompt_callback else read(prompt)).strip()
        if answer.lower() == 'q':
            raise ValueError('Setup cancelled; previous source configuration kept')
        return answer

    def inventory_by_path():
        devices = enumerate_devices()
        paths = [device['path_hex'] for device in devices]
        if len(paths) != len(set(paths)):
            raise ValueError('Windows returned duplicate HID paths; cannot pair these devices reliably')
        return {device['path_hex']: device for device in devices}

    notify('Guided dongle setup. No labelled USB ports or serial numbers are required.')
    notify('Connect each dongle to its intended controller; keep those cables unchanged.')
    notify("Choose the role matching the controller and the dongle's internal hardware setting.")
    notify('Cancel setup to keep previous assignments.' if prompt_callback else
           'Enter q at any prompt to cancel without replacing the saved setup.')
    connected_setup = bool(inventory_by_path())
    if connected_setup:
        notify('Dongles are already connected. Keep them connected; we will identify one at a time by unplugging and reconnecting it.')
    else:
        while True:
            ask('With all DSAN dongles unplugged from USB, press Enter: ')
            if not inventory_by_path():
                break
            notify('DSAN devices are still connected. Unplug them before continuing.')

    sources = []
    paired = set()
    while True:
        choice = ask('Choose the next dongle to identify, or review the paired devices.' if prompt_callback else
                     'Add dongle: [1] Limitimer, [2] PerfectCue, [Enter] Finish: ', 'role')
        if not choice:
            if not sources:
                notify('Pair at least one dongle before finishing.')
                continue
            if set(inventory_by_path()) != paired:
                notify('Connections changed. Keep paired devices connected and pair or disconnect any extra dongles.')
                continue
            notify('Setup complete. Normal startup initializes each dongle for its assigned role.')
            notify('Confirm the displayed timer and a Next cue before using the outputs.')
            return validate_config({'schema': 1, 'sources': sources})
        if choice not in ('1', '2'):
            notify('Choose 1 or 2, or press Enter to finish.')
            continue
        role = 'limitimer' if choice == '1' else 'perfectcue'
        role_name = 'Limitimer' if choice == '1' else 'PerfectCue'
        if connected_setup:
            before = set(inventory_by_path())
            if paired - before:
                raise ValueError('A paired dongle is missing; setup stopped without replacing the saved configuration')
            if not before - paired:
                notify('All connected dongles are paired. Connect an additional dongle or finish setup.')
                continue
            while True:
                ask(f'Unplug ONLY the next {role_name} USB dongle. Leave all others connected, then press Enter: ')
                remaining = set(inventory_by_path())
                removed, added = before - remaining, remaining - before
                if added or len(removed) > 1 or removed & paired:
                    raise ValueError('Unexpected USB change or an already-paired dongle was removed; setup stopped without guessing')
                if not removed:
                    notify('No dongle disappeared yet. Unplug only the requested unit and retry.')
                    continue
                break
            while True:
                ask(f'Reconnect that SAME {role_name} dongle, preferably to the same USB port, then press Enter: ')
                current = set(inventory_by_path())
                added = current - remaining
                if remaining - current or len(added) > 1:
                    raise ValueError('Other USB connections changed during reconnect; setup stopped without guessing')
                if not added:
                    notify('The dongle has not reappeared as a separate HID device yet. Check the connection and retry.')
                    continue
                path = added.pop()
                break
        while True:
            if connected_setup:
                break
            ask(f'Plug in ONLY the next {role_name} dongle. Leave paired dongles connected, then press Enter: ')
            current = inventory_by_path()
            if paired - current.keys():
                notify('A previously paired dongle is missing. Reconnect it to the same port before continuing.')
                continue
            added = current.keys() - paired
            if len(added) == 0:
                notify('No new DSAN HID device appeared. Check USB connection/driver; do not replace the HID driver with WinUSB.')
                continue
            if len(added) != 1:
                notify('More than one new dongle appeared. Leave only the requested new dongle connected.')
                continue
            path = added.pop()
            break
        default_label = f'{role_name} {1 + sum(s["role"] == role for s in sources)}'
        while True:
            label = ask('Name this input' if prompt_callback else f'Name [{default_label}]: ', 'name', default_label) or default_label
            if '=' in label or any(s['label'].casefold() == label.casefold() for s in sources):
                notify('Use a unique name without an equals sign.')
                continue
            break
        sources.append({'label': label, 'path_hex': path, 'role': role, 'initialize': True})
        paired.add(path)
        logging.info('Paired %s as %s using new HID path %s', label, role, path)
        notify(f'Paired {label}.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure', action='store_true', help='Choose, name and assign dongle roles again')
    parser.add_argument('--advanced-setup', action='store_true', help='Select existing HID paths manually, with optional receive-only startup')
    parser.add_argument('--data-dir', type=Path, default=default_data_directory(), help='Folder for saved sources and logs')
    parser.add_argument('--config', type=Path, help='Override the saved source configuration path')
    parser.add_argument('--self-test', action='store_true', help='Check bundled imports and web assets without accessing hardware')
    parser.add_argument('--host', type=listen_address, default='0.0.0.0', help='LAN access by default; use 127.0.0.1 for local-only access')
    parser.add_argument('--port', type=int, default=8765)
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
    if not args.advanced_setup:
        from .setup import launch_gui
        launch_gui(args, dsan_devices)
        return
    try:
        devices = dsan_devices()
        logging.info('DSAN HID inventory: %s', json.dumps(devices))
        if args.configure or args.advanced_setup or not args.config.exists():
            config = configure(devices) if args.advanced_setup else guided_configure()
            # Re-enumerate after the physical pairing steps, then preflight before
            # replacing the old file. Device writes happen only in display_main.
            devices = dsan_devices()
            arguments = launch_arguments(config, devices)
            # Validate the whole selection before replacing the previous configuration.
            args.config.parent.mkdir(parents=True, exist_ok=True)
            args.config.with_suffix('.tmp').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
            args.config.with_suffix('.tmp').replace(args.config)
        else:
            config = json.loads(args.config.read_text(encoding='utf-8'))
            arguments = launch_arguments(config, devices)
        arguments += ['--host', args.host, '--port', str(args.port)]
        arguments += ['--video-settings', str(args.data_dir / 'video-settings.json')]
        logging.info('Source configuration: %s', json.dumps(config))
        print('Keep this console open. Use Quit application in the operator page or Ctrl+C to stop. Diagnostics: ' + str(logfile))
        display_main(arguments)
    except (ValueError, OSError, EOFError) as exc:
        logging.error('%s', exc)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
