# DSAN Display executable

## Running the package on Windows

Extract the package and double-click **DSANDisplay.exe**. Python does not need to
be installed on the operating machine. Keep the `licenses` folder with the
distribution. The executable also embeds those notices. A normal browser is
still required; the first package deliberately uses the existing console setup
and browser renderer, not a new native window framework.

First launch uses guided pairing; no labelled USB ports are needed:

- If dongles are already connected, keep them connected. Choose the next unit's
  role, unplug only that unit when prompted, then reconnect it. The wizard matches
  the disappearance and reappearance while checking that peers remain present.
- If none are connected, add them one at a time when prompted.
- Give each unit a friendly name, repeat for the other role, and finish setup.

Normal startup initializes each paired unit for its assigned role. The role must
match the attached controller and internal hardware configuration; this is guided
assignment, not a firmware-type query. USB IDs and firmware-looking serial strings
cannot identify their roles. Settings
and logs are stored under `%LOCALAPPDATA%\DSANDisplay`; the one-file temporary
extraction directory is never used for persistent state. Later launches reuse
the saved bindings. Missing devices are reported without substituting a peer.

The browser opens the operator view. **Open video output** creates a separate
timer/cue view for HDMI/DisplayPort: move it onto the extended output display and
press **F**. Minimal display hides routine text while keeping connection warnings.
Next is a large green right triangle; Previous is a large red left triangle.
Keep the console open; Ctrl+C stops the server. Unexpected startup errors remain
visible until Enter is pressed when running interactively.

From Command Prompt in the executable folder:

```bat
DSANDisplay.exe --configure
DSANDisplay.exe --advanced-setup
DSANDisplay.exe --self-test
DSANDisplay.exe --host 127.0.0.1
DSANDisplay.exe --data-dir "D:\Show Data\DSAN"
```

`--configure` runs guided pairing again. `--advanced-setup` retains manual HID-path
selection and receive-only startup for diagnostics. The previous configuration is
replaced only after a complete new mapping and fresh enumeration validate.
`--self-test` imports the compiled HID dependency and tests bundled HTML/CSS/JS,
video output and state API over a temporary localhost server. It does not enumerate
USB devices, issue device messages or test hardware. Initialization, when enabled
in setup, sends one reviewed role-specific message to that exact dongle.

## Building on Windows x64

Only the **build machine** needs Python 3.13 x64 with the `py` launcher and Internet
access. From a checkout, run **Build Windows EXE.cmd**. It creates a separate build
environment and installs the pinned requirements. The build runs unit tests,
bundles a single console executable with PyInstaller, then runs the frozen
`--self-test` from a directory outside the checkout to catch missing assets/imports.
Output is produced only after these checks pass:

- `dist/DSANDisplay.exe`
- `dist/DSANDisplay-windows-x64.zip` — executable, dependency notices, this guide
  and build metadata.
- `dist/DSANDisplay.exe.sha256`

The archive records Python/dependency versions, hash and smoke-test outcome.
It excludes vendor installers/DLLs, private captures, saved device paths, user logs
and test fixtures. The source implementation and third-party licenses remain
separate matters; this packaging change does not assign a new application license.

## Building without a local Windows machine

The repository includes a manual **Build Windows executable** GitHub Actions
workflow using a Windows x64 runner. Once this code is in a GitHub repository,
run that workflow from its Actions page and download `DSANDisplay-windows-x64`.
No release is automatically published. The project repository is
[private jpkelly/DMAN](https://github.com/jpkelly/DMAN). Build results and artifacts
are available to authorized repository users from its Actions page.

PyInstaller is not a cross-compiler: a macOS run cannot create the Windows exe.
See its [platform guidance](https://pyinstaller.org/en/stable/usage.html).

## Validation status

A successful build includes `build-info.json`, recording the Windows platform,
Python/dependency versions, executable hash and frozen self-test result. A
source-mode check on macOS does not prove the frozen Windows bundle works.
Consult the workflow run and that metadata for the artifact you download. The
initial build is unsigned; code signing and a graphical installer are not included.

After building, test one Limitimer dongle, then one PerfectCue dongle, then both
simultaneously; verify exact source binding and independent disconnect/stale
handling. Next/Previous cue framing has emulator/dongle evidence; real PerfectCue
controller behavior, Blank and physical Windows video output remain untested.

Local validation completed: 74 unit tests, Python compilation, the source-mode
`--self-test` and editor diagnostics checks passed on macOS. The build script's
non-Windows guard correctly refused to create an incorrectly labelled executable.
The pinned PyInstaller 6.22.3 Windows x64 wheel and runtime wheels were downloaded
successfully; this checks their availability, not Windows installation/execution
or Windows-only transitive dependencies. The [first Windows workflow](https://github.com/jpkelly/DMAN/actions/runs/36349142395) subsequently passed: 74 tests,
PyInstaller build and the frozen self-test succeeded on Windows Server 2022 x64.

## First verified build

[Run 36349142395](https://github.com/jpkelly/DMAN/actions/runs/36349142395) built commit `954e8ae` successfully.
The downloaded Windows x64 PE executable is 9,664,613 bytes. Its SHA-256 matches
both the uploaded checksum and embedded build manifest:

```text
cf27f4aea01e902c88ac61257b3fd1a73c36629f63751fb0cf3b7759b7b00a5a
```

All 74 tests passed on the Windows runner, followed by the frozen executable's
no-hardware smoke check. The executable was downloaded and its hash/PE architecture
verified on the Mac; it was not run on macOS. USB hardware, physical video output
and real PerfectCue remain untested. Download workflow artifacts while retained
(14 days), or run the manual workflow again for a fresh package.

## Access from another device

LAN access is enabled by default. The console prints network URLs such as
`http://192.168.1.20:8765/`; use the actual URL shown on the Windows machine.
Other computers/tablets must be on a reachable network and Windows Firewall must
allow this application on the intended private network. The application does not
change firewall rules. Use `--host 127.0.0.1` to restrict access to the local PC.
There is no login in this trusted-LAN mode and no router/Internet publishing setup.
Display preferences still belong to each browser; they do not remotely change
an already-open output on a different browser.

## Live video-output controls

The presentation controls now apply only to video output. **Video layout** selects
Timer only / Cues only / Both; **Video output settings** changes sizes, minimal
mode, warning threshold and overtime presentation. Open outputs update live from
any operator on the trusted LAN. The confidence view retains its standard
presentation. Appearance is shared across output windows; source/program bindings
remain individual. Settings persist in `video-settings.json` under the app data
folder. This supersedes earlier notes saying appearance changes require reopening
an output or stay local to a browser.

## Choosing the output monitor

Open the local operator URL in a browser supporting the Window Management API
(such as Chrome/Edge). Choose display requests the browser's site permission and
populates Output display with connected monitor labels and dimensions. Select a
monitor and open video output. It opens as a separate popup and attempts fullscreen;
if the browser requires another gesture, click Fullscreen in that output or press
F. Escape closes the app-opened output window. The confidence page stays open.

This selects displays attached to the browser's machine. Plain HTTP LAN pages
and unsupported/denied browsers offer manual placement instead. This is not a
remote host monitor selector. Physical multi-monitor placement on Windows remains
a hardware check. CI runs synthetic browser-window behavior tests in addition to
the Python tests and packaged smoke test.

Guided pairing matches newly appeared paths rather than inventory order or serial
strings. It waits for exactly one new device and requires previously paired devices
to remain present. Ambiguous/duplicate paths are not guessed. Enter `q` to cancel;
no partial configuration is saved and no hardware output is sent during pairing.
After startup, check the displayed timer and an intentional Next cue. Moving ports,
hubs or machines can require pairing again. Actual Windows USB enumeration and
hardware pairing still need testing; automated tests use simulated plug sequences.
