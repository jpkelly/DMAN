# Windows deployment milestone

Windows is now the primary production target, specifically **one Limitimer dongle
and one PerfectCue dongle operating simultaneously**. Development can continue on the
Mac using the real capture fixtures and the existing Pi preview. Native Mac USB
remains unresolved and is no longer a release prerequisite for Windows.

The intended production path is:

```
PRO-2000 → VC-2000PC configured for Limitimer → Windows USB/HID
        → Python decoder and localhost server → browser / confidence monitor
PerfectCue → second dongle configured for PerfectCue → separate Windows HID reader
           → cue state → same display overlay, or a separate browser window
```

Each selected dongle has its own HID handle, decoder and stale-data state. The
app opens the exact enumerated device path, never the first matching VID/PID.
The firmware-looking serial string is not used as a unique identifier. No vendor
DLL, Pi, USB serial adapter, WinUSB replacement or libusb runtime is required by
this native HID path. Python plus a browser keeps the existing verified decoder
and display small and portable; there is no new UI framework.

**Status:** [Windows build and automated checks passed](https://github.com/jpkelly/DMAN/actions/runs/36349142395), including
74 tests and the frozen executable smoke check. Physical Windows USB testing
remains outstanding. The owner confirms prior vendor-software
operation with this Limitimer dongle. That does not verify our Windows backend.
The initial setup targets Windows 10/11 x64 with Python 3.13 x64; Windows ARM64
and standalone executable packaging are not covered by this milestone.

## Setup and launch

1. Copy/clone this workspace to a writable folder on Windows. Install
   [Python 3.13 for Windows](https://www.python.org/downloads/windows/) including
   the `py` launcher. Internet is needed to install the pinned dependencies.
2. Run [Setup Windows.cmd](../Setup%20Windows.cmd). It creates a separate
   `.venv-windows` environment and installs prebuilt dependency wheels.
   No administrator terminal or PowerShell execution-policy change is needed.
3. Close DSAN VideoClock and any other reader of these dongles. Connect each
   controller to its own dongle with the correct internal **Limitimer/PerfectCue**
   hardware setting. USB IDs alone cannot determine that setting.
4. Run [Start DSAN.cmd](../Start%20DSAN.cmd). On first launch, select the numbered
   device(s), give each a stage/source name, assign its hardware role, and choose
   its startup mode. Option 1 sends that role's reviewed initialization;
   option 2/default is receive-only.
   This choice is saved and reused on later launches, without repeated prompts.
5. The browser opens `http://127.0.0.1:8765`. Keep the console running. Select a
   Limitimer source/program and PerfectCue overlay, move the browser to the
   monitor and click Fullscreen. Selecting the PerfectCue source as the main
   source shows cues alone. Separate browser windows can display different
   sources/programs. Ctrl+C in the console
   stops the server; the browser marks its last value stale.

Startup option 1 sends exactly one 65-byte HIDAPI output per selected device:
zero report-ID slot, `8D 00` for Limitimer or `8D 01` for PerfectCue, then 62 zero
bytes. The native worker logs the role, attempt
and returned byte count; a short write or exception disconnects that source with
no retry. These are the vendor software's mode messages, not a firmware
update or controller start/stop command. It does not replace physical DIP/jumper
configuration. Only Limitimer decoding has been verified with this hardware.

`windows-sources.json` stores labels, exact paths, roles and per-device startup modes locally;
it is ignored by Git. `logs/windows-*.log` records device inventory, configured
bindings, initialization results and errors. These diagnostic logs do not record
the raw timer stream. Raw capture remains a separate CLI operation below.

To change source bindings, run this from Command Prompt in the project folder:

```bat
"Start DSAN.cmd" --configure
```

For identical dongles, identify the paths by attaching them one at a time, then
connect all of them and configure the complete selection. Keep USB ports/hub
positions consistent and label the physical dongles. A missing saved path stops
startup instead of substituting a peer. During operation, a timer source becomes
stale independently; cue read errors mark that source disconnected. Cue silence
does not prove disconnection because no heartbeat has been verified. There is no
automatic reconnect. After replugging, restart
and verify each source before use. Exact paths identify current OS endpoints;
they cannot prove physical identity after swapping indistinguishable dongles.

## First Windows hardware check

Start with **one** dongle and Program 1 stopped at 1:00. Confirm the displayed
time, selected program and fresh-data status. Then compare running, pause,
zero-crossing and program switching against the physical controller. Unplug USB:
the last value must freeze and clearly become stale/disconnected. Reconnect and
restart. Then identify the PerfectCue dongle alone and capture labelled Next,
Previous and Blank presses, holds and releases, one action at a time. Preserve
raw reports and compare their count-wrapped payload to the upstream serial notes.
Only after both individual paths are verified, connect both dongles and verify
that cue presses never change the timer, timer program changes never produce
cues, and unplugging either source leaves the other operating normally. Repeat
with swapped attachment order; revalidate source bindings after changing USB ports.
Warning colors are local settings; enabled hardware overtime remains unverified.

To list device paths without starting a stream:

```bat
.venv-windows\Scripts\python.exe -m dsan_display --list-hid
```

To capture a short, labelled receive-only session, close the display and substitute
the enumerated `path_hex` for `PATH_HEX`:

```bat
.venv-windows\Scripts\python.exe -m dsan_capture capture --out captures\windows-p1-stopped-0100 --label "P1 stopped at 1:00" --timer-model PRO-2000 --signal-path "Controller RJ45 to VC-2000PC to Windows USB" --seconds 10 hid --path-hex PATH_HEX --read-size 64
.venv-windows\Scripts\python.exe -m dsan_capture verify captures\windows-p1-stopped-0100
.venv-windows\Scripts\python.exe -m dsan_display --replay "Windows capture=captures\windows-p1-stopped-0100" --open-browser
```

The capture command shown sends no initialization. Record whether the device was
previously initialized by the display; do not run simultaneous readers. For
PerfectCue, use the actual controller model/signal path and observed button state
in those fields, then replay with `--perfectcue-replay` instead of `--replay`. Its raw
bytes, read boundaries, timestamps and metadata are preserved for repeat decoding.
If Windows exposes no DSAN HID path, collect a `dsan_capture discover` inventory
and Device Manager status before changing anything. Do not use Zadig to replace
the HID driver for this implementation.

## Implementation evidence and limits

### PerfectCue: emulator/dongle evidence

The source used here is an **emulator**, not a real PerfectCue controller. The
owner confirms it alternates triggers every ten seconds and also supplied an
isolated manual Next and Previous press. Actual captures establish a framed HID
payload stream: `81 0F 01 00 83` for Next and `81 0F 01 01 83` for Previous.
These periodic messages are emulator triggers, not a device heartbeat. Emulator
implementation and exact cable path remain unspecified. The first message after
initialization is not established as an acknowledgment; it matches the same cue
format and could have come from the running emulator.

The [streaming decoder](../dsan_capture/perfectcue.py) assembles the five-byte
messages across HID reads, handles multiple messages in one read, resynchronizes
at `81`, validates the observed fixed bytes, and retains unknown values without
assigning a cue. These messages have no observed checksum; structurally valid
bit changes cannot be detected as corruption. The meaning of the fixed `0F 01`
fields is not claimed beyond this observed format. Blank and release behavior
remain unverified. The earlier bare-byte interpretation from the
[upstream serial notes](https://github.com/jpkelly/clock8002/blob/master/perfectcue.md)
is not used for HID input.

The UI says **Emulator tested · Real PerfectCue untested**. It holds each cue for
one local second, then waits for another event; this is a presentation rule, not
hardware release timing. Opening data within the one-second synchronization
interval is not flashed afterward. Disconnect and browser/server loss clear the
active cue when detected. No event is not evidence of a heartbeat failure. Raw
captures remain intact; fixtures preserve their bytes and explicitly identify
the emulator source. No keyboard injection or slide control is implemented.

The **DSAN: mixed dongle preview** task now reads both Pi HID nodes independently
and displays the live Limitimer timer with an emulator cue overlay. This is useful
multi-dongle evidence on Linux via SSH, not a Windows compatibility test. The
Windows launcher continues to use separate native HID paths and per-role startup.

### HID and checks

The [HIDAPI 0.15 Windows backend](https://github.com/libusb/hidapi/blob/hidapi-0.15.0/windows/hid.c)
uses native Windows HID access and removes the dummy zero report-ID byte from
unnumbered input. Our decoder receives the eight actual device bytes, retaining
their count prefix. Its output API requires the leading report-ID slot, as
documented in the [HIDAPI header](https://github.com/libusb/hidapi/blob/hidapi-0.15.0/hidapi/hidapi.h).
The existing [installer research](dongle-research.md) and
[Pi captures](pi5-investigation.md) establish the DSAN-side message and framing.
No upstream or proprietary implementation was copied for this change. Existing
[dependency license notices](third-party.md) still apply; packaging binaries
later must carry them.

New tests mock the native HID boundary and use actual captured timer reports to
check independent paths, disconnect isolation, input normalization, exact output,
short-write handling and saved-configuration errors. Those tests exercise our
logic on macOS; they do not simulate Windows enumeration, driver timing, USB
hardware or real simultaneous dongles. Windows launch scripts also need execution
on the target machine. A signed standalone installer is future work after the
native hardware path is validated.

Validation for this milestone: all **64 tests passed on macOS**, Python compilation
and JavaScript syntax passed, and the editor reported no diagnostics in the changed
Python/JavaScript modules. A temporary localhost browser check displayed a real
Limitimer replay alongside an explicitly synthetic cue overlay, switched to cue-only
view, and confirmed that a synthetic disconnect removed the active arrow. The mock
route and temporary server were removed afterward; no synthetic capture fixture
was created. All pinned Windows x64/Python 3.13 wheels were successfully downloaded
for availability checking, not installed or executed on this Mac. Windows batch
scripts, USB enumeration and simultaneous physical dongles remain untested.

Latest validation after emulator clarification: **70 tests passed on macOS**,
including real emulator/dongle fixtures, every tested chunk size, corrupt-stream
resynchronization, unknown values, opening-buffer suppression and mixed-role state
isolation. Python compilation, JavaScript syntax and editor checks passed. Both
Pi streams were read simultaneously and the browser showed a live Next overlay
while the Limitimer countdown updated. No Windows hardware claim follows from
that preview.

## Standard video output

The requested output is standard PC video (HDMI/DisplayPort). Use **Open video
output**, move the separate browser view onto the extended output display and
press **F** for fullscreen. The operator page remains on the main display. The
clean view is bound to its own selected sources/program and keeps stale warnings
visible. See [video output details and validation](display.md#standard-video-output-hdmi--displayport).
The large cues are green/right for Next and red/left for Previous. No NDI/SDI
sender or special video hardware driver was added.

## Standalone executable packaging

A single-file Windows x64 build is now prepared. Run
[Build Windows EXE.cmd](../Build%20Windows%20EXE.cmd) on a Windows build machine,
then distribute the generated ZIP with `DSANDisplay.exe` and license notices.
The operating machine needs a browser but no Python installation. The packaged
app keeps settings/logs under `%LOCALAPPDATA%\DSANDisplay`. A manual GitHub Actions
workflow can also build on a Windows runner after the project is uploaded.
See [executable build and validation status](windows-exe.md). The first executable has now been built on Windows Server 2022 x64;
74 tests and the frozen smoke check passed there, with its downloaded SHA-256 verified. The existing source-mode launch scripts remain available.

## LAN browser access

The server and Windows launcher now default to listening on all interfaces (IPv4 and IPv6 where supported).
Use the network URL printed in the console from another laptop/tablet. The local
URL continues to work. `DSANDisplay.exe --host 127.0.0.1` restricts the app to the
local PC. See [LAN access and current scope](display.md#lan-access): no login or
router forwarding is configured, and display settings remain per browser.
