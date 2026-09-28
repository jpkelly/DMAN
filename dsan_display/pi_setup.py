"""Development adapter: real Pi sysfs discovery and separately selected streams."""
import hashlib
import json
import re
import shlex
import subprocess

from .model import Source
from .setup import Setup
from .workers import Worker


def attach(server, host, remote_root, config_path):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*', host):
        raise ValueError('Invalid Pi SSH host')

    def inventory():
        command = shlex.join([remote_root.rstrip('/') + '/.venv/bin/python',
                              remote_root.rstrip('/') + '/tools/pi_inventory.py'])
        result = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                                 host, command], capture_output=True, text=True, timeout=10, check=True)
        return json.loads(result.stdout)

    def worker(source):
        node = bytes.fromhex(source['path_hex']).decode('utf-8')
        if not re.fullmatch(r'/dev/hidraw[0-9]+', node):
            raise ValueError('Invalid Pi HID node')
        target = host + ':' + node
        identity = hashlib.sha256(('pi:' + target).encode()).hexdigest()[:12]
        return identity, Worker(Source(identity, source['label'], 'pi', target, role=source['role']),
                                remote_root, initialize_hid=source['initialize'])

    server.setup = Setup(server, config_path, inventory, worker, target='Pi · ' + host)
