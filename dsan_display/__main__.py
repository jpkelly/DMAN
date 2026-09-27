import argparse
import hashlib
import json
import re
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .model import Source
from .workers import Worker
from dsan_capture.discovery import hid_devices
from .network import host_allowed, listen_address, local_hostnames, network_addresses
from .video_settings import VideoSettings


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, *, dual_stack=False):
        self.address_family = socket.AF_INET6 if ':' in address[0] else socket.AF_INET
        self.dual_stack = dual_stack
        super().__init__(address, handler)
        self.allowed_hostnames = local_hostnames()
        self.video_settings = VideoSettings()

    def server_bind(self):
        if self.address_family == socket.AF_INET6 and self.dual_stack:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def create_server(host, port):
    if host in ('0.0.0.0', '::') and socket.has_dualstack_ipv6():
        return Server(('::', port), Handler, dual_stack=True)
    return Server((host, port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, data, content_type='application/json', status=200):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.valid_host():
            self.reply({'error': 'Unrecognized server address'}, status=403)
            return
        path = urlparse(self.path).path
        if path == '/api/state':
            self.reply({'sources': [w.source.snapshot() for w in self.server.workers.values()],
                        'video': self.server.video_settings.snapshot()})
            return
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/output': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/display-windows.js': ('display-windows.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in files:
            self.reply({'error': 'Not found'}, status=404)
            return
        name, content_type = files[path]
        content = (Path(__file__).parent / 'web' / name).read_bytes()
        if path == '/output':
            content = content.replace(b'<body>', b'<body class="output">', 1)
        self.reply(content, content_type)

    def valid_host(self):
        return host_allowed(self.headers.get('Host', ''), self.server.server_port,
                            self.connection.getsockname()[0], self.server.allowed_hostnames)

    def do_POST(self):
        expected = f'http://{self.headers.get("Host", "")}'
        if not self.valid_host() or self.headers.get('Origin') != expected:
            self.reply({'error': 'Same-origin request to this server required'}, status=403)
            return
        if self.path not in ('/api/restart-replay', '/api/video-settings'):
            self.reply({'error': 'Not found'}, status=404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(length))
            if self.path == '/api/video-settings':
                self.reply(self.server.video_settings.update(data))
                return
            with self.server.control_lock:
                worker = self.server.workers[data['id']]
                worker.restart_replay()
            self.reply({'ok': True})
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            self.reply({'error': str(exc)}, status=400)
        except OSError:
            self.reply({'error': 'Could not save video settings'}, status=500)


def main(argv=None):
    parser = argparse.ArgumentParser(description='DSAN LAN display. Receive-only unless initialization is explicitly enabled.')
    for flag in ('replay', 'pi', 'hid', 'perfectcue-hid', 'perfectcue-replay', 'perfectcue-pi'):
        parser.add_argument('--' + flag, action='append', default=[], metavar='LABEL=TARGET')
    parser.add_argument('--remote-root', default='/home/pi/dsan-investigation')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--video-settings', type=Path, default=Path('video-settings.json'), help='Persistent shared video presentation settings')
    parser.add_argument('--host', type=listen_address, default='0.0.0.0',
                        help='Listen address; default all interfaces (IPv4 and IPv6 where available). Use 127.0.0.1 for local-only access.')
    parser.add_argument('--list-hid', action='store_true', help='List DSAN HID paths as JSON, without opening a stream')
    parser.add_argument('--send-limitimer-init', action='store_true', help='Send one reviewed 8D 00 output to EACH selected native HID source; requires Limitimer hardware configuration')
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--init-hid', action='append', default=[], metavar='PATH_HEX',
                        help='Initialize this selected HID path once using its configured role')
    args = parser.parse_args(argv)
    if args.list_hid:
        print(json.dumps([d for d in hid_devices() if (d.get('vendor_id'), d.get('product_id')) == (0x0483, 0x101A)], indent=2))
        return
    if args.send_limitimer_init and not args.hid:
        parser.error('--send-limitimer-init requires at least one --hid source')
    workers = {}
    targets = set()
    init_paths = set()
    try:
        init_paths = {bytes.fromhex(p).hex() for p in args.init_hid}
    except ValueError:
        parser.error('--init-hid requires an enumerated path_hex')
    for option in ('pi', 'hid', 'replay', 'perfectcue_hid', 'perfectcue_replay', 'perfectcue_pi'):
        role = 'perfectcue' if option.startswith('perfectcue_') else 'limitimer'
        kind = option.removeprefix('perfectcue_')
        for item in getattr(args, option):
            label, sep, target = item.partition('=')
            if not sep or not label.strip() or not target:
                parser.error('Use LABEL=TARGET')
            if kind == 'pi' and not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*:/dev/hidraw[0-9]+', target):
                parser.error('Pi target must be USER@HOST:/dev/hidrawN')
            if kind == 'replay':
                target = str(Path(target).resolve())
            if kind == 'hid':
                try:
                    target = bytes.fromhex(target).hex()
                    if not target:
                        raise ValueError('Empty HID path')
                except ValueError:
                    parser.error('HID target must be an enumerated path_hex')
            key = kind + ':' + target
            if key in targets:
                parser.error('The same target cannot be opened twice')
            targets.add(key)
            identity = hashlib.sha256(key.encode()).hexdigest()[:12]
            workers[identity] = Worker(Source(identity, label, kind, target, role=role), args.remote_root,
                                       initialize_hid=kind == 'hid' and (target in init_paths or
                                           (args.send_limitimer_init and role == 'limitimer')))
    if any('hid:' + p not in targets for p in init_paths):
        parser.error('--init-hid must identify a selected native HID source')
    if not workers:
        parser.error('Add at least one --replay, --pi or --hid source')
    video_settings = VideoSettings(args.video_settings)
    server = create_server(args.host, args.port)
    server.video_settings = video_settings
    server.workers, server.control_lock = workers, threading.Lock()
    for worker in workers.values():
        worker.start()
    browser_host = '127.0.0.1' if args.host in ('0.0.0.0', '::') and server.dual_stack else args.host
    if browser_host == '0.0.0.0':
        browser_host = '127.0.0.1'
    if browser_host == '::':
        browser_host = '::1'
    if ':' in browser_host:
        browser_host = '[' + browser_host + ']'
    print(f'DSAN display: http://{browser_host}:{server.server_port}', flush=True)
    if args.host == '0.0.0.0' or server.dual_stack:
        for address in network_addresses():
            print(f'Network display: http://{address}:{server.server_port}', flush=True)
        local_name = socket.gethostname().split('.')[0].lower() + '.local'
        print(f'Local-network name: http://{local_name}:{server.server_port} (where local name resolution is available)', flush=True)
    if args.host != '127.0.0.1':
        print('LAN access enabled. Devices on this network can view data, change video settings and restart replay.', flush=True)
    if args.open_browser:
        webbrowser.open(f'http://{browser_host}:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        for worker in workers.values():
            worker.stop()


if __name__ == '__main__':
    main()
