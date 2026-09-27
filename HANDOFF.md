**Latest Windows build:** Private repository https://github.com/jpkelly/DMAN
is connected as origin. [Run 36349142395](https://github.com/jpkelly/DMAN/actions/runs/36349142395) built
commit `954e8ae`: 74 tests and frozen executable self-test passed on Windows x64.
The unsigned executable/package is downloaded under `dist/windows-build-36349142395`.
SHA-256/PE architecture verified locally. No Windows USB or physical video-output
test has occurred. Older statements saying no Windows executable exists are historical.

**Latest cue evidence:** the user has no PerfectCue controller box, only an
emulator alternating every ten seconds. Next/Previous manual-action captures plus
that clarification establish framed payloads `81 0F 01 00/01 83` on this path.
The decoder and real fixtures now cover that stream; bare serial cue bytes are
not the HID format. Real PerfectCue, Blank and Windows USB are still untested.
All 70 tests pass. **DSAN: mixed dongle preview** runs both Pi HID readers at
localhost:8765 with a live timer and cue overlay. Details supersede older
provisional-parser paragraphs below; see [Windows notes](docs/windows.md).

# Handoff prompt: DSAN display application

You are taking over an in-progress project in `/Users/jp/Documents/GitHub/DMAN`.
Continue the work below. Inspect the workspace and any current project instructions,
preserve existing files, and use the accumulated evidence instead of restarting
hardware discovery or asking questions the user has already resolved.

## Goal and requirements

**Latest direction supersedes earlier Mac-first requirements:** prioritize a
Windows application reading TWO dongles simultaneously: one Limitimer and one
PerfectCue. Their identical USB IDs cannot establish hardware role. Bind each by
exact HID path, name it, store its role and initialization preference, and keep
readers/decoders/state independent. Never send the Limitimer mode to the cue
source. See [Windows setup and verification limits](docs/windows.md). Windows
native execution and real mixed-dongle testing are still outstanding. Mac direct
USB work is deferred. Existing Mac/Pi display and replay remain available.

The Windows launcher supports saved per-device roles and optional `8D 00` or
`8D 01` startup. PerfectCue interpretation is a clearly labelled provisional
mapping from upstream serial notes, not verified HID hardware behavior. Its UI
can overlay cues on the countdown or show the cue source alone. Obtain actual
labelled PerfectCue captures before claiming cue support is verified.

**Latest implementation:** a first browser confidence display now runs on the Mac
at `http://127.0.0.1:8765` via the **DSAN: confidence display** task. See
[display.md](docs/display.md). Its live source is Pi-over-SSH, not direct Mac USB.
It also supports replay and separate source workers. Four real dongle fixtures
cover stopped, running/zero, paused and P1→P2 selection; P2 32:00 was confirmed
while P1 stayed paused at 0:52. The current full suite passed 52 tests. Older
sections saying no UI/verified dongle frames exist are superseded by this update.

Build a cross-platform application that displays a large, readable countdown from
DSAN hardware on a live-event confidence monitor. Develop on macOS; target Apple
Silicon, Intel macOS, and Windows. Linux is optional. Do not claim Windows or Intel
Mac support has been tested from an Apple Silicon-only run.

Multiple dongles are a core requirement. The user reports erratic displays when
several dongles were connected to the existing Windows software. Each source must
have its own physical-device binding, operator label, initialization, reader,
decoder buffer, timer state, freshness clock, capture stream, and reconnect
generation. Each display selects **source + program**, optionally following that
source's active program. Never combine different sources' bytes or substitute a
different dongle after a disconnect.

Eventually provide resizable/fullscreen countdowns, program selection, warning and
overtime colors from verified state or clearly labelled local settings, connection
and stale-data indicators, and capture replay. On disconnect, clearly mark the
last received value stale; do not silently keep counting locally. Keep transport,
HID envelope handling, timer packet decoding, state, and rendering separate.

## Read these first

- [README](README.md): commands and milestone status. Some historical paragraphs
  retain earlier uncertainty; the later user confirmations and research below
  supersede them.
- [Offline dongle research](docs/dongle-research.md): most important technical
  findings, binary identities, call-site addresses, references, and next test.
- [Multi-dongle requirements](docs/multiple-dongles.md).
- [Hardware/capture history](docs/investigation.md) and
  [HID investigation](docs/hid-investigation.md).
- [Third-party obligations](docs/third-party.md).

At the 2026-09-27 handoff inspection, this directory was **not a Git repository**,
and no AGENTS.md was found. Recheck rather than assuming that remains true.

## User-confirmed hardware facts

- Controller: **DSAN PRO-2000**.
- Dongle label: **VC-2000PC**, with one RJ45 port and USB.
- Connection: controller RJ45 directly to dongle RJ45; USB through an **Anker
  USB-C adapter/hub** to the Mac.
- The user has **explicitly confirmed this dongle has worked with a Limitimer**.
  Do not keep treating compatibility as merely a tentative recollection.
- The user reports internal DIP switches or jumpers select Limitimer versus
  PerfectCue purpose. Exact positions have not been inspected/documented. Match
  application configuration to the hardware role; do not assume a software
  message substitutes for the internal setting.
- The user currently has no Windows machine or alternative USB adapter. Do not
  make access to either a prerequisite for the next Mac experiment.
- The user subsequently considered a Raspberry Pi, then explicitly said they
  want to avoid setting one up. Keep work on the Mac; do not make Pi setup a
  dependency or keep requesting Pi/SSH details.
- **Later update superseding that constraint:** the owner supplied a ready Pi 5,
  `ssh pi@pi5start.local`. See [current Pi preparation and capture state](docs/pi5-investigation.md).
  SSH works; a runtime `0483:101a:d` quirk is set, and a 15-minute USB monitor was
  armed pending attachment. Check whether it is still running before use. Pi
  timestamps are unsynchronized; a clock calibration is saved. No boot edits.
- **Pi result update:** the dongle attached successfully with quirk `0x8`,
  exposed `/dev/hidraw0`, answered live GET_STATUS, and supplied its full HID
  report descriptor. The authorized initialization succeeded on the wire; data
  also flowed before it. USB monitoring is now stopped and copied locally.
  See the Pi report for journal-versus-USB-trace loss and the new tmpfs recorder.
  The stopped-at-1:00 state was subsequently confirmed: 110 consecutive frames
  match P1 selected/stopped/60 seconds after three old frames at connection start.
  A real fixture/regression exists; all 44 current tests pass. Next is an armed
  running capture. Checksums on this dongle stream are zero/absent, not validated.
- The last research work was deliberately offline. Hardware availability now is
  unknown; do not assume the dongle is attached.

## Observed USB facts

Previously observed on macOS 15.6.1 / arm64:

- VID/PID **`0483:101A`**; product **VideoClock USB Interface by DSan**.
- Serial-string descriptor **`Ver 0.17 10/03/14`**. This looks like firmware
  information; it has not been established as unique per dongle.
- Device class 0; configuration 1; interface 0, alternate 0; **HID class 3**,
  subclass/protocol 0.
- Interrupt-IN endpoint **`0x81`**, maximum packet size **8 bytes**.
- HID extra descriptor **`09 21 00 01 00 01 22 2F 00`** advertises a **47-byte
  report descriptor**. That is not an input-report length.
- No DSAN serial port appeared, and HIDAPI enumeration did not list the device.
  Direct PyUSB/libusb claim and interrupt reads did work intermittently.
- Standard IN GET_DESCRIPTOR for the HID report descriptor timed out. macOS also
  logged a separate string-descriptor timeout for index 92 during enumeration.
- USB unplug/reconnect identified the physical dongle conclusively. Historical
  bus/address were 1/4; **rediscover them before any future access**.

This is a HID USB connection, even if the controller side carries serial data.
Do not substitute the TP-2000X ASCII protocol or assume a serial/COM port exists.

## Major result from offline installer analysis

The user supplied both original packages, preserved in the workspace:

- [PerfectCue installer](VideoClock_For_PerfectCue/VideoClockForPerfectCueSetup.exe)
  and [ZIP](VideoClock_For_PerfectCue.zip).
- [Limitimer installer](VideoClockForLimitimer/VideoClockForLimitimerSetup.exe)
  and [ZIP](VideoClockForLimitimer.zip).

Both installers exactly match their official DSAN downloads. Static PE/zlib
inspection recovered their application images and USB support library in scratch
storage. **No installer or vendor executable/DLL was run or loaded.**

Verified from the inspected binaries:

1. Both applications open product ID **`0x101A`**; the library also filters vendor
   ID **`0x0483`**. We were targeting the correct USB identity.
2. Both packages contain the same USB library PE image.
3. The DLL creates an overlapped input-reader thread during opening. The
   application then sends a message associated with its selected device type:
   **Limitimer selection → `8D 00`; PerfectCue selection → `8D 01`.**
4. The output helper uses a **65-byte Windows HID buffer**: a zero report-ID slot,
   the two message bytes, and initially zero-initialized remaining storage. The
   helper reuses its buffer; do not assume it clears all padding on every write.
5. Continuous input uses **9-byte Windows `ReadFile` buffers**, not repeated
   feature-report/GET_REPORT polling. The input routine interprets the byte after
   the report-ID slot as a count/tag. For values below `7F`, it copies that many
   following bytes, bounded by received length, into a byte-stream buffer.
6. With the usual unnumbered HID mapping, raw USB reports contain count + up to
   seven payload bytes. This explains the leading `07` in our raw captures.
   HIDAPI's Windows backend removes the extra zero report-ID slot itself: do not
   strip two bytes blindly from HIDAPI or raw libusb reads.
7. Other report tags have separate handling. Keep unknown/status reports separate;
   do not feed every report indiscriminately to a timer decoder.
8. The vendor library has process-global connection/receive state and its
   open-by-ID path stops at the first match. This is a plausible source-selection
   limitation with multiple identical devices, not a proven explanation for the
   user's erratic displays. Globals are per process, not shared across separate
   application processes.

**Our passive captures never sent the application's initialization output.**
Missing initialization is a strong, concrete hypothesis, not yet a demonstrated
fix. Firmware-side effects/persistence of `8D` and the Mac descriptor failures
remain unresolved. The internal switch/jumper role is a separate consideration.

The standards-derived candidate for a direct USB output, given the observed
absence of interrupt-OUT, is HID SET_REPORT on endpoint 0:

```
bmRequestType = 0x21
bRequest      = 0x09
wValue        = 0x0200   # Output report, ID 0; NOT Feature report
wIndex        = 0
data          = 64 bytes: 8D 00 followed by 62 zero bytes
```

This is a mapping from the Windows API behavior and HID specification, **not a
captured or hardware-verified USB transaction**. Do not send it automatically.

Reproducible evidence:

- [Offline audit tool](tools/audit_dsan_installer.py): reads PE/container metadata,
  writes JSON only, no network/hardware access or binary execution.
- [PerfectCue audit](docs/vendor-perfectcue-audit.json) and
  [Limitimer audit](docs/vendor-limitimer-audit.json).
- The research report records hashes, precise RVA checkpoints, and evidence
  boundaries. Use it instead of repeating the whole binary investigation.

## Existing implementation

Minimal Python 3.11+ CLI, developed here with Python 3.14.6. Local environment is
in [.venv](.venv/). Dependencies in [requirements.txt](requirements.txt): pyserial
3.5, hidapi 0.15.0, pyusb 1.3.1. Existing Homebrew libusb was available; no global
USB driver installation was performed.

- [Discovery](dsan_capture/discovery.py): serial/HID/native USB inventories,
  saved comparisons, USB descriptors and port topology where available.
- [Transport](dsan_capture/transport.py): instance-owned serial, HID and explicit
  USB interrupt-IN receivers. USB capture requires exact bus/address/interface
  and inspects only the selected device, even when peers share VID/PID.
- [Session storage/replay](dsan_capture/session.py): lossless returned bytes,
  UTC/monotonic timestamps, read boundaries, integrity hashes, annotations,
  incomplete-session handling, replay with timing. Captures never overwrite.
- [HID descriptor inspection](dsan_capture/hid_inspection.py): bounded standard
  IN descriptor read; logs response/error, does not guess reports.
- [CLI](dsan_capture/__main__.py): `discover`, `diff`, `inspect-usb`, `inspect-hid`,
  `capture`, `annotate`, `verify`, `replay`. It records periodic receive-loop
  liveness and distinguishes opened-with-no-data from opening failure.
- [Tests](tests/): **23 tests** at handoff, with the last full run passing. These
  cover infrastructure, descriptor handling and synthetic two-device isolation;
  they do not prove DSAN timer decoding or real simultaneous hardware operation.

No initialization output has been implemented. No verified timer decoder,
multi-source manager/registry, reconnect routing, or main display UI exists yet.
The CLI records one explicitly selected device per invocation.

Useful checks from the workspace root:

```sh
.venv/bin/python -m compileall -q dsan_capture tests tools
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m dsan_capture --help
```

## Capture history and cautions

Preserve [captures](captures/) and [inventories](inventories/). They are locally
ignored by the existing ignore file and contain valuable real observations.

Several short captures returned no bytes. A few produced one eight-byte report,
then silence, including:

```
00 00 00 00 00 00 00 00
07 81 10 83 00 00 81 00
07 81 00 21 6F 07 00 00
07 81 00 21 6F 09 00 01
```

These are genuine raw reports, not complete verified timer packets. Labels and
their uncertainty are in each session. Some user actions happened between or
near the end of captures. Do not claim exact button/zero-crossing timing.

One interactive tool-PTY capture terminated without an end record and is
explicitly incomplete. A later detached, file-backed two-minute capture completed
with 120 empty reads and liveness records. Do not assume a tool PTY survives
across conversation turns; confirm that recording is actually active before
asking the user to manipulate hardware.

Ultraleap Hand Tracking was found probing the device. With explicit user/admin
approval it was temporarily unloaded and tested, including a full dongle power
cycle. The same one-report-then-silence behavior persisted. **Ultraleap was
restored and verified running afterward.** Do not blame it or stop it again
without a new reason. A background-shell restoration fallback did not restore
it as promised; do not rely on that mechanism. Explicit restoration ultimately
succeeded after the user corrected an accidentally canceled admin prompt.

## Source reuse and reference implementations

The user explicitly reminds us that these repositories contain actual Limitimer
and PerfectCue decoding/state/display implementations, not just documentation:

- [Clock-8001](https://gitlab.com/clock-8001/clock-8001)
- [Depili Limitimer](https://gitlab.com/Depili/limitimer)
- [Go documentation](https://pkg.go.dev/gitlab.com/Depili/limitimer)
- [PerfectCue notes](https://gitlab.com/sytem/clock-8001/-/blob/master/perfectcue.md?ref_type=heads)
- [clock8002 Limitimer notes](https://github.com/jpkelly/clock8002/blob/master/limitimer.md)
- [clock8002 repository](https://github.com/jpkelly/clock8002)

Use the actual implementations as references for payload decoding, state and
rendering. Their direct serial adapters do not implement our HID bridge.
The familiar RS-485 19200/8N1, framing and Modbus-polynomial CRC information is
a source lead to verify against complete captures, not a USB-port setting.
PerfectCue cue bytes are not Limitimer state. The TP-2000X ASCII interface is
different. Some PerfectCue wire-color examples conflict internally; do not
recommend rewiring from those examples or invent jumper positions.

Inspected upstream licenses carry GPL-2.0-or-later notices. Explain applicable
reuse/distribution obligations before incorporating code. No upstream code has
been incorporated so far. No license granting incorporation/redistribution of
DSAN's proprietary DLL or application was established; keep vendor binaries out
of the app and do not copy their artwork or implementation. A draft
[DSAN inquiry](docs/dsan-compatibility-brief.md) exists; **nothing has been sent**.

## Authorization and next work

**Latest user instructions, 2026-09-27:** the owner explicitly approved sending
dongle messages and said not to ask again. This supersedes the original
receive-only/per-test approval restrictions described historically below for
ordinary dongle communication during this investigation. Record all output and
use targeted, bounded diagnostics. It is not an instruction to send messages to
third parties. Opt-in initialization is now implemented. A current probe at
17:02 UTC found bus 0/address 4, GET_STATUS timeout, one 8-byte input fragment,
and a timeout sending the reviewed `8D 00` output. No sustained input followed.
Use the current README and HID investigation for updates beyond this original
handoff, including the enumeration captures, decoder work and Ultraleap removal.

The user's original instruction (superseded as described above) was receive-only hardware access: **no protocol
commands, firmware changes or automatic baud scanning**. The user has not yet
authorized the newly identified initialization output. Researching/documenting
it is not authorization to send it. The agreed next procedure is:

1. When hardware is available, rediscover the exact target and confirm its
   Limitimer hardware setting. Do not assume old USB addresses are current.
2. Prepare a small, reviewable, opt-in initialization test. Show the exact output
   and ask permission to send that one message, explaining that it changes the
   original receive-only scope. Keep default capture receive-only.
3. Arm recording/read processing before the output, matching the vendor reader
   startup order. Record the exact outbound request, result, raw input, source
   identity and timestamps. Never broadcast to all matching devices.
4. Check for sustained input before more timer exercises. If initialization
   stalls or fails, inspect that failure; do not scan arbitrary commands.
5. Guide one state capture at a time: stopped at 1:00, running, paused,
   approaching/crossing zero, program changes. Clearly distinguish observed
   states, static-source interpretations and genuinely verified decoded fields.
6. Implement/test the streaming decoder with real labelled fixtures, including
   partial/multiple packets, corruption, lengths, checksums and resynchronization.
   Preserve unknown fields explicitly. Then build the display and multi-source
   orchestration, validating disconnect/staleness and independent device routing.

If hardware remains unavailable, progress on useful offline infrastructure,
source isolation, fixture inspection or reference-code analysis. Never invent
sample packets and label them hardware-verified. Ask only when missing hardware
information or a material design decision actually blocks progress. Keep changes
reviewable, run relevant checks, and communicate concisely: verified findings,
remaining uncertainty, and the next concrete action.
