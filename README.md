# DSAN timer investigation

First milestone: receive-only hardware discovery, raw capture, annotations, and
replay. **No verified timer decoder or confidence-monitor UI yet.**

**Core requirement: multiple dongles at once.** Each display will select an
independent source and timer program, with separate input, decoding, capture and
stale-data status. The owner observed conflicts with multiple dongles in the
existing software. See the [multi-dongle requirements and design](docs/multiple-dongles.md).
The owner also reports internal switches/jumpers select Limitimer versus
PerfectCue operation. Each source's confirmed hardware role must match its
software initialization and decoder; matching USB IDs do not establish that role.
The CLI currently records one explicitly selected device per invocation; a
concurrent manager and display UI are not implemented yet.

**Latest result:** offline analysis of the supplied PerfectCue installer and
DSAN's Limitimer installer recovered the actual HID startup/read path. Both use
`0483:101A` and the same USB library. The Limitimer path sends `8D 00` in a HID
output report after opening, then reads a count-prefixed byte stream. The owner
explicitly confirms this dongle has worked with a Limitimer. See the
[deep research report](docs/dongle-research.md) and
[reproducible installer audit](tools/audit_dsan_installer.py).
No hardware access or device writes occurred during that research; the runtime
capture utility remains receive-only. Mac operation after initialization is
still untested.

## Verified on this Mac

On 2026-09-26, macOS 15.6.1 / Apple Silicon enumerated a device named
`VideoClock USB Interface by DSan`, VID:PID `0483:101A`, serial-string
`Ver 0.17 10/03/14`. Its USB interface is HID class `03`, with interrupt-IN
endpoint `0x81`, maximum packet size 8 bytes. No matching serial port or HIDAPI
entry appeared. Direct libusb input access succeeded and returned one 8-byte
all-zero report during a two-second check. This is **not evidence of Limitimer
compatibility**, nor a verified timer-state fixture.

The user identified the controller as **PRO-2000**, with its RJ45 connected
directly to the **VC-2000PC** dongle's RJ45. Unplugging USB removed exactly the
DSan device and its HID-class interface; serial and HIDAPI inventories did not
change. Reconnection restored that same device/interface, completing USB
attribution. HID report layout and timer payload are still unconfirmed. DSAN's current
two-RJ45 VC-2000-2 documentation does not prove compatibility of that older
single-RJ45 model.

The first user-labelled capture (program 1 stopped at 1:00) received one report,
`07 81 10 83 00 00 81 00`, in 10 seconds. Integrity and replay checks passed;
this is not enough to verify timer framing or fields.
The following 10-second running capture received no bytes, although the dongle
remained visible in the OS USB inventory. The cause is unresolved.
Subsequent captures at a reported 0:00 and after Repeat to 1:00 also received no
bytes; the latter used a longer 1000 ms USB input timeout. Further state captures
are on hold pending investigation of the receive path.
A libusb diagnostic confirmed successful interface access followed by interrupt
read timeouts. The user tentatively recalls prior Windows VideoClock success;
that has not yet been reproduced with the current setup.
No Windows machine is currently available. Legacy DSAN documentation explicitly
distinguishes PerfectCue and Limitimer dongle configurations; see the source links
in the investigation notes. The installed configuration remains unknown.
The only available USB-C adapter is Anker; a hub-bypass comparison is currently
unavailable. No evidence singles out the adapter as the cause. A
[DSAN compatibility brief](docs/dsan-compatibility-brief.md) records the questions
needed to investigate the device configuration and input interface.
A later full dongle power cycle restored one different 8-byte report, followed
by silence. A subsequent detached two-minute recording completed with 120 empty
reads and no received bytes. The user reported 0:00 while it was active; exact
button and zero-crossing timing remains unverified. An earlier interactive PTY
attempt ended unexpectedly and is explicitly preserved as incomplete. Timer
decoding remains blocked on useful input.

HID investigation found a separate Mac process, **Ultraleap Hand Tracking**,
repeatedly attempting to open the DSAN device. This is a potential conflict, not
a proven cause. See [HID investigation](docs/hid-investigation.md). A comparison
with that service stopped was authorized and performed. After a full dongle power
cycle, one 8-byte report arrived, then silence; the descriptor request still timed
out. This did not establish Ultraleap as the cause. **Ultraleap has been restored
and verified running.** The first restoration prompt was accidentally canceled;
the owner authorized a retry, which succeeded. See the investigation for details.

See [investigation notes](docs/investigation.md) for source evidence and the next
hardware steps, and [third-party notices](docs/third-party.md) before code reuse.

## Stack and setup

Python 3.11+ keeps transport and file handling small and portable. pySerial
covers serial adapters, HIDAPI covers OS-exposed HID devices, and PyUSB/libusb
provides descriptor inspection and explicit interrupt-IN access when needed.
Only the Python standard library is used for storage, replay, and tests. A UI
stack will be selected after decoding is verified; these modules have no UI
dependency. Windows and Intel macOS are targets, **not tested platforms**.

macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\Activate.ps1
```

If activation is unavailable, run the environment's Python executable directly.
All subsequent examples use `python` from that environment. Native USB inventory
does not require libusb. PyUSB inspection/direct capture does require it; this
Mac already had Homebrew libusb. The utility never installs or replaces device
drivers. Windows access through HIDAPI or libusb must be evaluated on Windows;
do not assume a driver change is required. Linux support is best effort.

## Discover and compare

```sh
python -m dsan_capture discover --out inventories/before.json --note "Dongle disconnected"
# Connect only the dongle USB after recording the disconnected inventory.
python -m dsan_capture discover --out inventories/after.json --note "Dongle connected"
python -m dsan_capture diff inventories/before.json inventories/after.json
python -m dsan_capture inspect-usb --vid 0x0483 --pid 0x101a --out inventories/descriptors.json
```

Use truthful notes matching the connection state. Outputs never overwrite an
existing file. Inventories include all visible serial/HID/USB devices, identifiers,
and collection errors. `diff` compares records; reconnecting may change paths or
USB addresses. An added device does not establish its electrical compatibility.

The actual initial snapshots are under the ignored [inventories directory](inventories/).
The connected/disconnected/reconnected comparison and refreshed descriptors are saved.

To inspect the advertised HID report descriptor after refreshing the device's
bus/address:

```sh
python -m dsan_capture inspect-hid --vid 0x0483 --pid 0x101a --bus 1 --address 4 --interface 0 --out inventories/hid-report.json
```

This uses standard device-to-host GET_DESCRIPTOR for the report descriptor. It
does not issue HID feature/output reports or device initialization commands. The
exact request, advertised length, returned bytes (if any), and errors are saved.
It exits nonzero on a timeout or short read. PyUSB may claim the selected
interface for this read, then releases it; it never detaches a driver.

## Capture

Choose exactly one transport. No autodetection-based opening, baud scanning,
protocol commands, feature reports, firmware writes, kernel-driver detachment,
or USB configuration changes are implemented.

For the currently observed USB device, refresh descriptors first; bus/address
can change. This example must be filled with the **observed** model and path:

```sh
python -m dsan_capture capture --out captures/stopped-0100 --label "Stopped at 1:00; program recorded in notes" --timer-model "ACTUAL MODEL" --signal-path "ACTUAL controller port -> cable -> VC-2000PC -> USB" --seconds 10 usb-interrupt --vid 0x0483 --pid 0x101a --bus 1 --address 4 --interface 0 --endpoint 0x81
```

Capture options must precede the transport name. `--seconds 0` runs until Ctrl-C.
`--quiet` suppresses live hex output. A read error ends the session with an error;
it does not reconnect or substitute data. No received bytes simply means no
observed input, not a stopped timer. Opening a USB interface may fail if another
application owns it; the utility leaves drivers alone.

The USB transport accepts `--read-timeout-ms` after `usb-interrupt` (default 100,
range 1–5000). This changes only how long a host input read waits. The capture can
exceed its requested duration by the final read's timeout. Applied settings are
saved in the session; there is no automatic timeout or baud scanning.

For an OS-exposed HID device, select its exact `path_hex` from discovery:

```sh
python -m dsan_capture capture --out captures/hid-check --label "State unknown" --timer-model unknown --signal-path unknown hid --path-hex HEX_FROM_DISCOVERY --read-size MAX_INPUT_REPORT_SIZE
```

Determine `MAX_INPUT_REPORT_SIZE` from the HID report descriptor, including a
report ID where present. A USB endpoint packet size alone does not establish a
HID report's length. HIDAPI input bytes are preserved verbatim; no IDs or padding
are stripped. This transport could not be exercised with the connected dongle.

For a **separately established serial interface**, supply all line settings:

```sh
python -m dsan_capture capture --out captures/serial-check --label "State unknown" --timer-model unknown --signal-path unknown serial --port ACTUAL_PORT --baud CONFIRMED_BAUD --data-bits 8 --parity N --stop-bits 1
```

19200/8N1 is an upstream Limitimer lead, not a setting verified for this dongle.
Serial flow control is disabled; RTS/DTR are set inactive before opening.
OS/driver open/close operations can still toggle lines or discard pre-open input.
Application receive-only behavior does not guarantee electrical isolation.

## Annotations and replay

During or after recording, use another terminal:

```sh
python -m dsan_capture annotate captures/stopped-0100 "Controller shows P1, stopped, 1:00" --at 0
python -m dsan_capture verify captures/stopped-0100
python -m dsan_capture replay captures/stopped-0100
python -m dsan_capture replay captures/stopped-0100 --speed 1
```

`--at` is the observation time in seconds from session creation. Omit it when
unknown; the annotation still records its creation time. Replay defaults to
immediate output; `--speed 1` uses recorded timing, `--speed 2` doubles speed.
Replay never accesses hardware. It includes saved notes and unmodified read
boundaries, suitable for a future streaming decoder.

Each new session stores:

- `metadata.json`: observed-state label, model/path, UTC start, host monotonic
  origin, inventory, and requested settings.
- `connection.json`: selected device descriptors/identity and applied transport
  settings, when opening succeeds.
- `raw.bin`: exactly the bytes returned by reads, including zeros and any HID
  report IDs/padding. USB captures contain endpoint payloads, not USB bus headers.
- `events.jsonl`: UTC and monotonic timestamps, offset/length for each read,
  connection/errors, and an end record with total bytes and SHA-256. New captures
  also record whether the interface opened, reads with data, and empty reads.
  Empty reads are not interpreted as timer state. The CLI explicitly reports
  an opened interface with zero input; close errors end with an error reason.
  Periodic `receive-status` records document that the receive loop is alive,
  including when no bytes arrive. They are not timer-state updates.
- `annotations/`: separate append-only note files; annotation never rewrites raw
  data or races with the acquisition journal.

Timestamps represent host read completion, not individual bytes arriving on the
wire. Bytes are saved before journaling, and both files are flushed/fsynced on
each read. An interrupted process can leave untimestamped trailing bytes; those
remain in the raw file, and replay warns and uses only fully journaled reads.
A complete record means storage integrity, not valid protocol or successful
hardware operation. Software cannot detect every loss in hardware/OS buffers.
Back up real captures before promoting selected captures into test fixtures.
Captures and inventories are ignored by Git because they contain local device
identifiers. No invented data is labelled as a real timer capture.

## Validation and next stage

```sh
python -m compileall -q dsan_capture tests
python -m unittest discover -s tests -v
```

VS Code tasks for these checks are in [tasks.json](.vscode/tasks.json).
Twenty-three infrastructure tests cover byte preservation, read boundaries,
corruption/truncation, interrupted sessions, timing, annotations, and transport
failure. They do not verify DSAN parsing. The actual USB access check can be
replayed from [its session directory](captures/initial-access-check/).
The tests include two synthetic same-product USB sources and isolated close/
missing-target behavior. USB inventories include port topology where available;
it is a reconnect hint, not proof of unique physical identity.

Module boundaries: [discovery](dsan_capture/discovery.py) inventories devices;
[transport](dsan_capture/transport.py) returns bytes;
[session](dsan_capture/session.py) records and replays them;
[CLI](dsan_capture/__main__.py) coordinates user actions. Add framing/decoding,
timer-state mapping, and rendering as separate layers after verified captures.
The eventual display must mark the last value stale on disconnect or data timeout
and never silently continue a local countdown. Fullscreen, program selection,
warning/overtime colors, and GUI replay remain later milestones.
