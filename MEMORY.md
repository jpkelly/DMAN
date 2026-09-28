# DSAN project memory — paused 2026-09-27 (Los Angeles)

The user paused work until tomorrow and explicitly requested that state be saved.
Read this file before resuming. It supersedes historical status and next-action
claims in HANDOFF.md. No physical pairing step or user confirmation is pending.
Do not repeat the completed pairing test without a new reason.

## Current outcome

Windows is the primary deployment target. The main purpose is simultaneous,
independent use of two existing DSAN dongles: one Limitimer and one PerfectCue.
The Mac is the development machine; real USB input currently comes from a Pi 5
over SSH. Direct Mac USB compatibility remains unresolved and is deferred.
Existing firmware and minimal host changes remain user requirements.

The browser device-setup wizard is implemented and wired to real pairing,
persistence, and worker startup, not a mock-up. It reuses `guided_configure`
from the console launcher through structured prompt callbacks. It supports
devices already connected at launch, one-at-a-time connection, friendly names,
review, Save and start, cancellation, and resuming saved inputs. Stale prompt
answers, ambiguous changes, duplicate paths and missing saved inputs do not
silently select another dongle. Pairing enumerates only; explicit Save and start
initializes each assigned dongle once and replaces the running inputs.

### Completed real browser test

Both dongles were connected initially. Through the GUI, the user unplugged and
reconnected Limitimer while the cue dongle remained, then unplugged and
reconnected PerfectCue while Limitimer remained. We named them PRO-2000 and Cue
emulator, reviewed the roles, clicked Save and start, and checked real input.

- PRO-2000: `/dev/hidraw0`, Limitimer, Program 1 stopped at **12:00**.
- Cue emulator: `/dev/hidraw1`, PerfectCue; both Next and Previous received.
- The user explicitly confirmed **12:00 matches the physical controller**.
- In a 23-second post-save observation: 237 additional decoded timer frames,
  six additional recognized cue events, both sources connected without errors.
- Setup and the already-open video output both displayed 12:00. We returned the
  active browser page to the confidence display after confirmation.
- Evidence: [browser setup notes](docs/browser-setup.md) and local ignored
  `inventories/browser-setup-pi/post-save-state.jsonl` (state snapshots, not raw USB).

## Repository and executable

- Workspace: `/Users/jp/Documents/GitHub/DMAN`.
- Private repository: https://github.com/jpkelly/DMAN ; SSH origin, branch main.
- Last application-code commit: `028036e` (browser setup). Documentation commits
  `5d8f7ec` and `c5f2679` record Pi results and the user's controller confirmation.
- Latest successful Windows build: [36372085666](https://github.com/jpkelly/DMAN/actions/runs/36372085666),
  application commit `028036e`. 109 Python tests and nine Node window-helper
  tests passed on CI; bundled imports, setup/display assets and APIs, and
  confirmed shutdown passed the frozen executable self-test.
- Local package: `dist/windows-build-36372085666/DSANDisplay-windows-x64.zip`.
  The EXE SHA-256 was verified against the manifest and accompanying checksum.
  The registered package artifact id is `7df7b6fa-84ae-47ab-bebe-28f5527a5e7c`.
- Portable unsigned Windows x64 EXE, not an installer. Bundles Python/runtime
  dependencies, needs a normal browser, uses built-in Windows HID support.
- Default Windows launcher opens browser setup. Existing valid bindings restore;
  missing-device errors appear there. `--advanced-setup` retains console manual
  path/receive-only setup. The console remains visible for diagnostics; it has
  NOT yet been replaced with a fully windowless launcher.
- Config/logs on Windows: `%LOCALAPPDATA%\DSANDisplay`. Pi development bindings
  are local ignored `pi-sources.json`; both entries have initialize=true.
- No physical Windows USB test, physical multi-monitor Windows test, or code
  signing has occurred. CI success is not hardware verification.
- No uncommitted implementation changes were present before this memory update.

## Runtime at pause

The display was left running; pausing work did not request application shutdown.
Do not assume the process or SSH connection survives overnight.

- Operator: http://127.0.0.1:8765/
- Setup: http://127.0.0.1:8765/setup
- Video: http://127.0.0.1:8765/output
- Shared operator page id: `d2caa002-551b-46e1-88da-ccf7198a55ac`.
- Shared output page id: `253065f2-2b6f-4cb4-bf7f-9be3f7a7e6c4`.
- Timer source id `9bbda23fc143`; cue source id `78e9d68d6dfc`.
- VS Code task **DSAN: mixed dongle preview**, tool id
  `shell: DSAN: mixed dongle preview`, runs the Mac server with `--setup-pi
  pi@pi5start.local`, two Pi input paths, and a recorded replay. Saving the GUI
  assignments replaced those initial workers with the two chosen live inputs.
- The Pi development task still has explicit startup paths; it does not
  automatically restore `pi-sources.json`. Recheck actual devices after reboot
  or repatching. The GUI can Resume saved inputs or re-pair as needed.
- SSH: `pi@pi5start.local`; remote root `/home/pi/dsan-investigation`, venv
  `.venv`. Updated `tools/pi_inventory.py` and `tools/pi_stream.py` were deployed
  there. Sysfs discovery is receive-only. Stream initialization is opt-in and
  validated against the known HID identity/descriptor.
- The Pi runtime quirk `0483:101a:d` (effective 0x8) avoids invalid USB string
  descriptor 92. No persistent boot change was made. Recheck after a Pi reboot.
- Pi wall clock is unsynchronized; do not infer event timing from its dates.
- HTTP listens on LAN interfaces by default. Host/Origin checks protect mutations;
  trusted LAN users can view, change shared presentation/setup, and quit the app.
  No Internet publication or router forwarding was configured.

## UI behavior and established preferences

- Confidence keeps its standard layout. Video layout (timer/cues/both), timer
  size, cue size, warning threshold and video overtime apply to video output
  and update open outputs through shared server settings.
- Confidence has a separate **Show overtime past zero** checkbox.
- Next is a large green right triangle; Previous is a large red left triangle.
- Clean/minimal video hides routine explanatory text, retaining stale warnings.
- Choose display / Open video output uses browser screen-selection support when
  available; manual positioning remains the fallback. Escape closes app-opened
  output windows. Real multi-monitor placement is not hardware-tested yet.
- Quit application is at top right of the operator page and in setup. It asks
  for confirmation, stops workers/server, and closes reachable app-opened output
  windows. Closing only a browser tab does not stop the server. Manually opened
  or suspended tabs may require manual closure. Normal network loss marks data
  stale and never silently extrapolates the countdown or closes the output.

## Hardware and protocol limits

- Timer controller is PRO-2000, directly cabled to the dongle. Cue input is an
  emulator, NOT a real PerfectCue controller, historically alternating every 10s.
- Dongles share VID/PID 0483:101A and serial string `Ver 0.17 10/03/14`.
  Descriptors/serial cannot identify role. Internal DIP/jumper role is user-set.
- USB is HID, not a serial port. Reviewed role initialization is report ID 0,
  bytes `8D 00` (Limitimer) or `8D 01` (PerfectCue), zero-padded to 65-byte HID
  writes. No firmware changes or baud scanning. Native Windows handles remain
  physically untested; Pi initialization and simultaneous reception are tested.
- Real Limitimer fixtures cover stopped/running/zero/paused/program switch.
  Zero checksum fields mean absent, not CRC-validated. Framed emulator cues are
  `81 0F 01 00 83` Next and `81 0F 01 01 83` Previous. Real PerfectCue and Blank
  remain unverified. Keep timer and cue streams independent.
- User already authorized ordinary targeted dongle messages; don't repeatedly
  request approval for reviewed initialization. This is not authorization to
  send email/messages to other people or flash firmware.
- Preserve raw captures/inventories/vendor installers. They are ignored locally;
  do not commit vendor binaries. No vendor DLL is loaded or bundled. Check
  [third-party notes](docs/third-party.md) before incorporating upstream GPL code.
- Ultraleap was restored after earlier diagnostics; do not stop it without new
  evidence. Do not apply the experimental Mac kernel-extension work.

## Resume

The requested GUI setup and real Pi pairing check are complete. No pending
unplug/reconnect request remains. Ask for the user's next priority rather than
restarting investigation. The main remaining deployment milestone is a real
Windows run with both dongles, followed by external monitor/output checks.

Useful entry points: [setup bridge](dsan_display/setup.py),
[Windows launcher](dsan_display/windows.py), [Pi adapter](dsan_display/pi_setup.py),
[setup UI](dsan_display/web/setup.js), [server](dsan_display/__main__.py),
[workers](dsan_display/workers.py), [setup tests](tests/test_setup.py),
[Windows package instructions](docs/windows-exe.md).
