"""Build and smoke-test a Windows x64 single-file exe on a Windows host."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def collect_notices(destination):
    destination.mkdir(parents=True)
    for name in ('hidapi-native-bsd.txt', 'hidapi-python-bsd.txt', 'pyserial.txt', 'pyusb.txt'):
        shutil.copy2(ROOT / 'docs/licenses' / name, destination / name)
    python_license = next((p for p in (Path(sys.base_prefix) / 'LICENSE.txt',
                                      Path(sys.base_prefix) / 'LICENSE') if p.is_file()), None)
    if python_license is None:
        raise RuntimeError('Python distribution license not found; cannot package without its notices')
    shutil.copy2(python_license, destination / 'python-LICENSE.txt')
    versions = {name: importlib.metadata.version(name)
                for name in ('hidapi', 'pyserial', 'pyusb', 'pyinstaller')}
    notice = ('DSAN Display: third-party notices\n\n'
              'Bundled Python: ' + sys.version + '\n' +
              '\n'.join(f'{name}: {version}' for name, version in versions.items()) +
              '\n\nThe accompanying Python, HIDAPI, pySerial and PyUSB license files\n'
              'are part of this distribution and must be retained. HIDAPI uses its\n'
              'BSD license alternatives. No DSAN installer, USBIF.dll, upstream GPL\n'
              'capture fixtures or separately installed libusb runtime is included.\n'
              'PyInstaller permits executable distribution under its bundling\n'
              'exception: https://pyinstaller.org/en/stable/license.html\n'
              'Windows hardware validation and code signing remain outstanding.\n')
    (destination / 'THIRD_PARTY_NOTICES.txt').write_text(notice, encoding='utf-8')
    return versions


def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Build on Windows x64; PyInstaller does not cross-compile a Windows exe from macOS.')
    if sys.version_info[:2] != (3, 13) or sys.maxsize <= 2**32:
        raise SystemExit('Use Python 3.13 x64 for this build configuration.')
    # No artifact is published unless tests and the frozen smoke check succeed.
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
                   cwd=ROOT, check=True)
    (ROOT / 'build').mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='windows-', dir=ROOT / 'build'))
    notices = staging / 'licenses'
    versions = collect_notices(notices)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
               '--console', '--noupx', '--name', 'DSANDisplay', '--paths', str(ROOT),
               '--distpath', str(staging / 'dist'), '--workpath', str(staging / 'work'),
               '--specpath', str(staging), '--hidden-import', 'hid',
               '--collect-submodules', 'serial.tools',
               '--add-data', str(ROOT / 'dsan_display/web') + ':dsan_display/web',
               '--add-data', str(notices) + ':licenses', str(ROOT / 'tools/windows_entry.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    exe = staging / 'dist/DSANDisplay.exe'
    # Test from outside the project: local source/assets must not mask omissions.
    with tempfile.TemporaryDirectory(prefix='dsan-exe-smoke-') as smoke_dir:
        result = subprocess.run([str(exe), '--self-test'], cwd=smoke_dir, check=True,
                                capture_output=True, text=True, timeout=90)
    if '"frozen": true' not in result.stdout or '"self_test": "passed"' not in result.stdout:
        raise RuntimeError('Frozen self-test did not report success: ' + result.stdout + result.stderr)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    manifest = {'artifact': exe.name, 'sha256': digest, 'platform': platform.platform(),
                'python': sys.version, 'dependencies': versions,
                'frozen_self_test': json.loads(result.stdout.strip()),
                'usb_hardware_tested': False, 'signed': False}
    (staging / 'build-info.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / 'DSANDisplay-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        output.write(exe, exe.name)
        output.write(ROOT / 'docs/user-guide.md', 'START-HERE.md')
        output.write(staging / 'build-info.json', 'build-info.json')
        for notice in sorted(notices.iterdir()):
            output.write(notice, 'licenses/' + notice.name)
    shutil.copy2(exe, dist / exe.name)
    (dist / 'DSANDisplay.exe.sha256').write_text(digest + '  DSANDisplay.exe\n', encoding='ascii')
    print('Built and smoke-tested:', archive)
    print('No USB hardware test or code signing was performed.')


if __name__ == '__main__':
    main()
