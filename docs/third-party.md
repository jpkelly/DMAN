# Third-party sources and distribution obligations

The first milestone is original discovery/capture/replay infrastructure. No code
from Clock-8001 or Depili/limitimer was copied, translated, vendored or imported.
Later decoding work and upstream-derived test fixtures are covered below.

Later offline research statically inspected DSAN's supplied PerfectCue installer
and its official Limitimer package. No redistribution/incorporation license for
the proprietary application or USB DLL was established; none was executed,
linked into the application, or added as a deliverable. Extracted images stayed
in scratch storage. The user-supplied installer files were preserved as provided.
The original audit tool reads PE/container metadata and produces JSON evidence;
the [research report](dongle-research.md) documents interface behavior. Future
implementation must not copy vendor implementation or artwork into the project.

## Upstream timer implementations

Both inspected LICENSE files contain GPL version 2 and project-specific notices
allowing version 2 **or any later version**:

- [Depili/limitimer license](https://gitlab.com/Depili/limitimer/-/blob/1cec6f97c27022905da7b05c6e4ae9837368596c/LICENSE),
  copyright 2021 Vesa-Pekka Palmu.
- [Clock-8001 license](https://gitlab.com/clock-8001/clock-8001/-/blob/master/LICENSE),
  copyright 2019 Vesa-Pekka Palmu.

Copying/adapting their implementation, including translation into another
language, or linking the GPL library into a distributed application brings GPL
obligations. Preserve copyright/license/warranty notices, include the license,
mark modifications and dates, license the derived combined work compatibly, and
provide corresponding source including build scripts using a compliant source
supply method. Merely reading documentation or investigating protocol behavior
does not incorporate the implementation.

**Owner decision (2026-09-27):** embedding GPL-2.0-or-later content is acceptable
where needed, which means distributing the application under compatible GPL terms.
Prefer original code where we can do better; upstream concepts and reverse
engineering may be used freely. Consequently:

- [limitimer.py](../dsan_capture/limitimer.py) and
  [hid_stream.py](../dsan_capture/hid_stream.py) are original implementations.
  They use the frame layout and field positions documented by Depili/limitimer
  (credited in [the protocol notes](limitimer-protocol.md)); no code was copied.
- [Upstream capture excerpts](../tests/fixtures/upstream-limitimer/README.md) are
  unmodified byte ranges from Depili/limitimer's captures, used as test fixtures
  under GPL-2.0-or-later with [its license](licenses/depili-limitimer-LICENSE.txt).
- If upstream code is later copied or translated, keep its notices, mark changes
  with dates, and record it here.

A formal application license file has not been added yet.

The Windows pivot adds an original candidate PerfectCue byte mapping from the
protocol facts in clock8002's `perfectcue.md`. No upstream implementation or
vendor DLL was copied. Its HID interpretation remains unverified with hardware;
see [Windows implementation limits](windows.md). No new dependencies were added.

The additional owner-supplied forks
[sytem/clock-8001](https://gitlab.com/sytem/clock-8001) and
[jpkelly/clock8002](https://github.com/jpkelly/clock8002) were also inspected. Their
LICENSE files retain GPL-2.0-or-later project notices. The clock8002 serial
listeners were read for comparison; no code from these forks was incorporated.

## Dependencies used in this milestone

- pySerial 3.5: BSD-style terms; retain [license and notices](licenses/pyserial.txt).
- cython-hidapi 0.15.0: offers license alternatives; use its BSD-style option and
  retain [wrapper notices](licenses/hidapi-python-bsd.txt). Native HIDAPI also
  offers a BSD option: [native notices](licenses/hidapi-native-bsd.txt).
- PyUSB 1.3.1: BSD-3-Clause; retain [license and notices](licenses/pyusb.txt).

These licenses require preservation of their notices/disclaimers in redistributed
source and accompanying binary documentation/materials. Do not use contributor
names for endorsement. The exact dependencies are pinned in
[requirements](../requirements.txt); installed wheel metadata is retained in the
local environment. This repository currently distributes neither wheels nor
standalone application binaries.

PyUSB uses a separately installed libusb runtime. This Mac already had it at
`/opt/homebrew/lib/libusb-1.0.dylib`; no runtime or driver was installed globally.
[libusb](https://github.com/libusb/libusb) is LGPL-2.1-or-later. If packaging that
runtime later, audit the exact binary's license/source notices and satisfy LGPL
source and relinking/replacement requirements. Native packaging, code signing,
and per-platform dependency license audits remain future work.

## Windows executable build

The [Windows build](windows-exe.md) pins PyInstaller 6.22.3 as a build-only
dependency. Its [bundling exception](https://pyinstaller.org/en/stable/license.html)
permits distributing generated executables under terms compatible with the
application's dependencies; it does not require licensing the application under
GPL merely because PyInstaller bundled it. PyInstaller itself is not modified.

The build embeds the existing HIDAPI, pySerial and PyUSB notices and the license
file from the actual Python installation. It also places these in the output ZIP
with dependency versions and build metadata. Keep the notices with distributed
packages. Native Windows HID does not require the separately installed libusb
runtime; this build does not intentionally bundle it. Proprietary vendor binaries,
GPL test fixtures, private captures, device configurations and logs are excluded.
No Windows binary or distribution has yet been produced or audited in this session;
the frozen smoke test and actual dependency collection must run on Windows.
