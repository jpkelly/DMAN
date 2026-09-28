"""Offline smoke check, runnable from the bundled executable without dongles."""
import json
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen


def self_test():
    import hid  # Load the compiled HID extension; do not enumerate or open USB.
    import serial.tools.list_ports
    import usb.core
    from .__main__ import Handler, Server

    if not callable(hid.enumerate) or not callable(serial.tools.list_ports.comports):
        raise RuntimeError('Missing transport entry points')
    if not callable(usb.core.find):
        raise RuntimeError('Missing PyUSB entry point')
    if getattr(sys, 'frozen', False):
        notices = Path(__file__).resolve().parent.parent / 'licenses' / 'THIRD_PARTY_NOTICES.txt'
        if not notices.is_file():
            raise RuntimeError('Bundled third-party notices missing')
    server = Server(('127.0.0.1', 0), Handler)
    server.workers, server.control_lock = {}, threading.Lock()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        expected = {'/': b'Open video output', '/output': b'<body class="output">',
                    '/app.js': b'function render()', '/style.css': b'--video-cue-size',
                    '/display-windows.js': b'installOutputExit',
                    '/api/state': b'"sources": []'}
        for route, marker in expected.items():
            with urlopen(f'http://127.0.0.1:{server.server_port}{route}', timeout=5) as response:
                if response.status != 200 or marker not in response.read():
                    raise RuntimeError(f'Packaged resource check failed: {route}')
        origin = f'http://127.0.0.1:{server.server_port}'
        request = Request(origin + '/api/quit', data=b'{"confirm":true}',
                          headers={'Origin': origin, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            if json.loads(response.read()).get('status') != 'stopping':
                raise RuntimeError('Packaged shutdown request failed')
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError('Packaged server did not stop after Quit')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print(json.dumps({'self_test': 'passed', 'frozen': bool(getattr(sys, 'frozen', False)),
                      'hardware_accessed': False, 'checks': ['native imports', 'HTTP assets', 'video output', 'state API', 'confirmed shutdown']}))
