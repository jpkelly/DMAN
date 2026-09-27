**Current overtime controls:** confidence and video now have separate checkboxes.
Confidence overtime is saved per browser; video overtime remains shared across
video outputs. This supersedes the earlier shared-overtime notes below.

**Current video-control behavior (supersedes older per-window appearance notes):**
presentation controls apply only to video output, and update every open output
live through shared server settings. The confidence view uses its standard layout,
sizes, labels and status text. Source/program bindings remain per output window.
See [shared video settings](#shared-video-settings).

# DSAN confidence display

The display runs on the **Mac**, using a local Python server and browser window.
The currently working live connection reads the dongle on the Pi over SSH:

```
PRO-2000 → VC-2000PC → Pi USB → SSH → Mac server → Mac browser/monitor
```

Direct USB on this Mac remains affected by the enumeration issue. This UI does
not fix that driver/firmware problem. Replay needs no hardware. Windows and Intel
Mac deployment remain untested; no standalone installer has been produced.

**Updated production goal:** Windows direct USB with one Limitimer and one
PerfectCue dongle operating together. See [Windows setup](windows.md). The
Mac/Pi arrangement below remains a development preview. Native Mac USB is deferred.
PerfectCue Next/Previous framing is verified with the owner’s emulator and dongle;
the cue overlay and cue-only view identify real PerfectCue as untested. A local one-second cue hold is a presentation setting, not measured
hardware timing. Cue silence is not treated as a verified heartbeat.

## Run

Use the VS Code task **DSAN: confidence display**, or from the workspace root:

```sh
.venv/bin/python -m dsan_display \
  --pi 'PRO-2000=pi@pi5start.local:/dev/hidraw0' \
  --replay 'Recorded countdown=captures/pi-p1-running-window'
```

Open `http://127.0.0.1:8765` **on the Mac**. The server now listens on all interfaces (IPv4 and IPv6 where supported) by default; see LAN access below.
Move a browser window onto the confidence monitor and click Fullscreen (or F).
Escape exits fullscreen; moving the pointer reveals the controls. Browser windows
can independently choose their source/program. No Internet service is required.

On Windows, use the activated environment's `python -m dsan_display` or
`.venv\Scripts\python.exe`; Python, the requirements and an SSH client are needed
for a Pi source. This is an intended portable entry point, not a tested Windows
release.

Replay-only example:

```sh
.venv/bin/python -m dsan_display --replay 'Recorded countdown=captures/pi-p1-running-window'
```

The replay uses actual capture timing. Replay again restarts it. At the end, it
marks the last value stale instead of silently looping or continuing the timer.
Only HID-report captures are accepted; raw serial streams require a different
normalization path.

## Source choices

Repeat `--pi`, `--hid`, `--perfectcue-hid`, `--perfectcue-pi`, `--replay` or `--perfectcue-replay`
to configure independent sources. Each argument
is `LABEL=TARGET`:

- Pi: `LABEL=USER@HOST:/dev/hidrawN`; `--remote-root` changes the default remote
  project directory `/home/pi/dsan-investigation`.
- Native HID: `LABEL=PATH_HEX` from discovery. The target must identify DSAN
  `0483:101A`. This path has not been hardware-tested on Windows and cannot open
  our current Mac dongle while HIDAPI cannot enumerate it. `--hid` assigns
  Limitimer; `--perfectcue-hid` assigns PerfectCue. The same path cannot be
  assigned to both. Optional `--init-hid PATH_HEX` sends that selected source's
  role-specific startup once; no writes are sent by default.
- Replay: `LABEL=CAPTURE_DIRECTORY`.
  `--perfectcue-replay` applies the framed cue decoder instead of the timer
  decoder. Emulator/dongle Next/Previous captures exist; real PerfectCue is untested.

The Pi needs the transferred capture modules and
[pi_stream.py](../tools/pi_stream.py), with its helper
[pi_hidraw_capture.py](../tools/pi_hidraw_capture.py). The Pi preparation already
installed these. The stream validates the selected HID VID/PID and exact known
report descriptor, then opens the node read-only. It sends JSON reports and
heartbeat messages, not timer commands. The temporary USB quirk must remain
active for this device; it is not persistent across reboot yet.

The source list is configured at startup. Exact duplicate targets are rejected;
these are explicit runtime bindings, not a completed persistent physical-device
registry. Host aliases or changed HID node numbering require operator care.
No automatic reconnect or fallback to the first matching device is implemented.
Restart/reconfigure the server after a disconnect, verifying the target first.
Several source workers are implemented, but real simultaneous dongles have not
been tested. The current preview has one live source and one replay source.

## Display behavior

- Follow controller selects the controller's active program. Selecting Program
  1–4 in the browser changes only what that browser displays; it does not change
  the physical controller.
- Time comes only from decoded packets. There is no local countdown extrapolation.
- No fresh state for two seconds, SSH failure, disconnect, or replay completion
  marks the last value stale. A lost browser/server connection also freezes and
  marks the cached value. Rejected packets do not refresh freshness.
- The first second is labelled Synchronizing to avoid presenting the short old
  state prefixes observed at opening. This settling interval is not proof of the
  age of all possible buffered data.
- Stop-at-zero clamps the displayed countdown to zero when the device's continue
  flag is off. Raw negative remaining values are preserved internally. The owner
  confirmed this behavior on the controller after the one-minute run.
- Amber uses a **local warning threshold**, default 30 seconds. Red at zero is
  also a local presentation rule. The optional overtime checkbox is explicitly a
  local override. Device sum-up/phase-light behavior and optional hardware
  overtime mode have not yet been verified; the UI does not claim those colors
  reproduce them.
- Details identify live versus replay sources, transport errors, frame counts and
  absent checksums. The observed dongle supplies zero checksums; those are never
  described as CRC-validated.

## Implementation and checks

[model.py](../dsan_display/model.py) owns one decoder/freshness state per source.
[workers.py](../dsan_display/workers.py) owns independent transport threads.
[The local server](../dsan_display/__main__.py) serves the UI and snapshots.
[Browser code](../dsan_display/web/app.js) renders the selected received value.
No third-party web framework or vendor DLL was added.

The first Mac browser check showed live P2 at 32:00, switching to P1 at 0:52,
controller-follow selection, and working fullscreen. Replay restart was checked
through the local API. Geometry confirmed the clock fits the current fullscreen
viewport. Unit tests use actual captured reports to check stop-at-zero, frozen
stale values, source isolation, warmup and replay completion. JavaScript syntax
and Python compilation passed. The full suite passed **52 tests** at this stage.

Still needed: physical disconnect tests of the live display, multiple real dongles,
warning/overtime configuration coverage, Windows/Intel Mac tests, persistent source
identity/reconnect management and packaging. The direct-Mac USB issue is separate
from the working Mac display/Pi-reader path.

## Mixed-dongle development preview

Run **DSAN: mixed dongle preview** for the current Pi wiring. It adds
`--perfectcue-pi 'Cue emulator=pi@pi5start.local:/dev/hidraw1'` alongside the
Limitimer source on `/dev/hidraw0`. Select PRO-2000 as the main source and Cue
emulator as the overlay. Both streams are receive-only; the dongle's earlier
PerfectCue initialization is documented in the Pi investigation. The matching
Windows task override opens the native Windows launcher instead of using SSH.

## Standard video output (HDMI / DisplayPort)

The operator page now has **Open video output**. This opens `/output` in a separate
browser view with source, cue source, program and local display settings bound in
its URL. Controls, settings and diagnostics panels are hidden. Connection/stale
warnings remain visible, along with the current emulator-test label. Next is a
large green right-pointing triangle; Previous is a large red left-pointing triangle.
Cue space is reserved so the countdown does not move when a triangle appears.

On Windows, use an extended desktop, connect the monitor or switcher to the PC's
HDMI/DisplayPort output, move this output browser window onto that display, then
press **F** to enter fullscreen (Escape exits). Keep operator controls on the main
screen. The operating system sets output resolution/refresh rate; this app does
not configure the graphics adapter, generate SDI/NDI, or provide genlock. For
another output selection, configure the operator view and open another output.
Existing output windows retain their own selections. If a URL-bound source is
missing, the view reports unavailable rather than switching to another dongle.

Browser checks on macOS confirmed the clean view at 1920×1080 with no overflow,
controls hidden, a 259.2 px green Next triangle, and stable timer position between
idle and active cues. Earlier live checks confirmed Previous is red. Changing the
operator program left the output program unchanged. A missing source URL displayed
SOURCE UNAVAILABLE without a fallback. These are browser checks, not a physical
Windows HDMI/switcher or refresh-rate test.

### Minimal display

Enable **Display settings → Minimal display — timer and cues only** to hide source
labels, routine running/paused text, explanatory captions and idle “WAITING FOR CUE”
text. The countdown and active green/right or red/left triangles remain. Cue space
is preserved while idle. Connection loss, stale-data, missing-source and replay
indicators remain visible. The preference is saved locally and included as
`minimal=1` (or `minimal=0`) in newly opened video-output URLs. Existing output
windows retain their own settings; open a new output to apply a different preset.

Browser verification: routine text and idle cue text were hidden, a live Next
triangle remained visible, and injected stale-timer/disconnected-cue snapshots
still displayed their warnings. The temporary browser response override was
removed afterward. JavaScript syntax and editor checks passed.

### Layout and size controls

The **Display** selector offers **Timer only**, **Cues only**, or **Both**. Timer
and cue sources are selected separately; controls for a hidden component are
inactive. Cue-only replay restarts the selected cue source. A missing required
source is reported explicitly instead of displaying a different source.

**Display settings** includes independent **Timer size** and **Cue size** sliders
from 50% to 150% of the default layout. Percentages are saved locally. Output URLs
include `display=timer|cue|both`, `timerSize` and `cueSize`, so existing output
windows retain their layout and sizes. Open a new video output to apply a new
preset. Oversized fullscreen/video combinations are scaled down proportionally
to fit the viewport; relative timer/cue sizing is retained. The cue's reserved
space scales along with its triangle, keeping the countdown steady between cues.

Browser checks covered all three layouts, disabled irrelevant controls, persisted
sliders, independent output URL values and the 150%/150% combination fitting at
1920×1080. JavaScript syntax and editor diagnostics checks passed.

### Connection details show all sources

Connection details lists every configured live source, regardless of display
layout, followed by a separate replay section. Each entry includes its hardware
role, transport, exact device/source path, connection state, report/error counts,
last timer state or cue, and transport errors. Both Pi dongles were verified
connected with independent increasing counters in this view. Cue idle time is
reported as time since the last cue, not as an assumed lost heartbeat.

## LAN access

The app now defaults to `--host 0.0.0.0 --port 8765`. The local operator URL stays
`http://127.0.0.1:8765`; startup also prints detected network addresses. Open
`http://COMPUTER-LAN-IP:8765/` on another computer/tablet on the same reachable
network. Output URLs use that same host. The current development Mac is
`http://10.65.1.56:8765/`; its DHCP address can change. Local machine names are
accepted too when the client's network resolves them (for example Sapporo.local).

Use `--host 127.0.0.1` for local-only mode, or bind a specific IP interface with
`--host ADDRESS`. The Windows executable accepts the same `--host` and `--port`
options. A firewall must permit the app on the intended private network; the app
does not alter firewall rules, router forwarding, or security settings. No Internet
hosting or public URL is configured. This mode has no login and is intended for
a trusted LAN; reachable clients can view state and restart replays. Requests with
unrecognized Host values and cross-origin replay commands are rejected.

Display settings remain per browser. A remote operator can view live sources and
open a video view, but changing its sliders/layout does not remotely reconfigure
an already-open output window on the host. That requires shared output-control
state, which is not implemented by this network-access change.

LAN validation: all 79 tests passed on macOS, including real HTTP requests,
IPv4/IPv6 dual-stack access, accepted LAN origins, and rejected foreign origins
and unknown hosts. The Pi independently fetched `/`, `/output`, JavaScript, CSS
and live state from the Mac over the existing **wired IPv6 connection**, all
HTTP 200, with both dongles connected. No network addresses/routes, firewall
settings or router settings were changed. The Pi has no IPv4 route to the Mac's
Wi-Fi address, so that was not used as the cross-device test path. Ethernet and
Wi-Fi are both supported when the client has a route to the server.

## Shared video settings

**Video layout** and **Video output settings** control output appearance only:
Timer only / Cues only / Both, minimal display, timer/cue sizes, warning threshold
and overtime presentation. The confidence display keeps a standard readable view
of its selected timer and cue inputs; these presentation controls do not resize,
hide or recolor it. Its default warning threshold remains 30 seconds. **Show overtime past zero**
is the shared exception: it uses received raw time in both confidence and video
views, overriding stop-at-zero presentation when enabled.

Settings are shared by the application server and saved in `video-settings.json`
(in the Windows user-data directory for the packaged app). All open `/output`
views update on their next poll, including when controls are changed from another
computer over LAN. Other operator pages synchronize as well. The settings panel
shows whether an update was saved or is waiting to retry. Invalid changes are
rejected; a failed disk save does not change the running settings.

Output windows still retain their own timer/cue source and program bindings.
Appearance is now one shared profile across them; older appearance parameters in
output URLs no longer override it. Use Open video output to create another view
with the currently selected sources/program. No hardware commands are sent when
presentation settings change. LAN clients have this control access on the trusted
network; cross-origin requests remain rejected.

Verification of separation: changing timer size to 50% and cue size to 150%
changed the already-open video output, while the confidence timer font stayed
151.5 px and its labels stayed visible. Selecting Cues only switched the output
to the cue view while confidence still displayed its timer and cue overlay.
The checks used the existing output URL, demonstrating that its older appearance
parameters no longer override shared settings. Test presentation changes were
restored afterward. All 83 tests and Python/JavaScript syntax checks passed locally.

UI simplification: the explanatory banner, routine synchronization message and
Minimal display checkbox have been removed from the settings panel. Clean video
presentation is the default. The underlying saved minimal preference remains
compatible with existing settings, while save errors appear only when needed.

Overtime correction: Show overtime past zero now applies to confidence as well as
video, and remains available even when the video layout is Cues only. Both live
views were observed at −2:00 with the option enabled. This renders received raw
time; it does not simulate elapsed time. Size, layout, minimal presentation and
the adjustable warning threshold remain video-only. JavaScript syntax and editor
checks passed.

## Independent overtime controls

**Confidence settings → Show overtime past zero** affects only that confidence
browser and is stored in its local preferences. **Video output settings → Show
overtime past zero** affects video outputs through the shared server setting.
On the first use of the new confidence control, its initial value is copied once
from the previous shared setting to preserve the current appearance; afterward
the controls are independent. Both still use received raw timer data, and neither
continues counting on a stale/disconnected source.

Browser verification covered confidence off/video on (0:00 versus negative time),
then confidence on/video off (negative time versus 0:00), with confidence changes
leaving the server's video-settings revision unchanged. Both original enabled
settings were restored. Confidence persistence survived a page reload. JavaScript
syntax and editor checks passed.
