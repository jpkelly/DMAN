"""Independent transport workers. Closing one source never closes its peers."""
import json
import logging
import shlex
import subprocess
import threading
from pathlib import Path
from dsan_capture.session import replay
from dsan_capture.transport import HidReceiver
from dsan_capture.init_output import send_hid

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, source, remote_root='/home/pi/dsan-investigation', initialize_hid=False):
        self.source, self.remote_root = source, remote_root
        self.initialize_hid = initialize_hid
        self.cancel = threading.Event()
        self.thread = None
        self.process = None

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.cancel.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.thread:
            self.thread.join(timeout=3)
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=3)

    def restart_replay(self):
        if self.source.kind != 'replay':
            raise ValueError('Only replay sources can restart here')
        self.stop()
        if self.thread and self.thread.is_alive():
            raise RuntimeError('Previous replay has not stopped')
        self.cancel = threading.Event()
        self.source.reset()
        self.start()

    def run(self):
        try:
            if self.source.kind == 'replay':
                self.run_replay()
            elif self.source.kind == 'pi':
                self.run_pi()
            else:
                self.run_hid()
        except Exception as exc:
            log.error('%s (%s): %s', self.source.label, self.source.target, exc)
            self.source.end('disconnected', str(exc))

    def run_replay(self):
        # Validation happens before the replay yields any data.
        metadata = json.loads((Path(self.source.target) / 'metadata.json').read_text())
        transport = metadata.get('transport') or metadata.get('requested_settings', {}).get('transport')
        if transport not in ('linux-hidraw', 'hid', 'usb-interrupt'):
            raise ValueError('Display replay requires a HID-report capture, not a raw serial stream')
        events = replay(Path(self.source.target), speed=1, sleep=self.cancel.wait)
        self.source.connected()
        for event, data in events:
            if self.cancel.is_set():
                return
            if event['kind'] == 'rx':
                self.source.receive(data)
        self.source.end('ended')

    def run_hid(self):
        receiver = HidReceiver(self.source.target, 64)
        try:
            if (receiver.info.get('vendor_id'), receiver.info.get('product_id')) != (0x0483, 0x101A):
                raise ValueError('Display source must be DSAN 0483:101A')
            log.info('%s: opened HID %s', self.source.label, receiver.info)
            if self.initialize_hid:
                log.info('%s: sending %s initialization once', self.source.label, self.source.role)
                written = send_hid(receiver, self.source.role)
                log.info('%s: initialization returned %d bytes', self.source.label, written)
            self.source.connected()
            while not self.cancel.is_set():
                data = receiver.read()
                if data:
                    self.source.receive(data)
        finally:
            receiver.close()

    def run_pi(self):
        host, device = self.source.target.split(':', 1)
        root = self.remote_root.rstrip('/')
        command = shlex.join(['sudo', '-n', root + '/.venv/bin/python', '-u',
                              root + '/tools/pi_stream.py', '--device', device])
        self.process = subprocess.Popen(
            ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
             '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2', host, command],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        try:
            for line in self.process.stdout:
                if self.cancel.is_set():
                    return
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    # SSH diagnostics are surfaced, never interpreted as reports.
                    raise RuntimeError(line.strip()[:300])
                if message.get('kind') == 'connected':
                    self.source.connected()
                elif message.get('kind') == 'report':
                    self.source.receive(bytes.fromhex(message['hex']))
                elif message.get('kind') == 'error':
                    raise RuntimeError(message['message'])
            self.source.end('disconnected', 'Pi stream closed')
        finally:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process.stdout.close()
