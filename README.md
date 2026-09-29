# DSAN Display

Browser-based confidence displays for DSAN Limitimer timers and PerfectCue cues.
Connect your controllers through their USB dongles, pair each input, and show timers
and cues on local monitors or devices on your LAN.

- Use Limitimer and PerfectCue inputs simultaneously, with independent source status.
- Choose timer programs and cue sources per display.
- Open dedicated video outputs with timer-only, cues-only, or combined layouts.
- Adjust output size, warning threshold, and overtime presentation live.
- Replay recorded captures without connected hardware.

## Quick start — Windows

1. Download **DSANDisplay-windows-x64.zip** from [Releases](https://github.com/jpkelly/DMAN/releases),
   extract it, and run **DSANDisplay.exe**. Keep the included `licenses` folder.
   Python is bundled; you only need a browser.
2. Close other software using the dongles. Connect each controller to a dongle
   configured for its **Limitimer** or **PerfectCue** role.
3. Follow the browser pairing wizard. Choose each dongle's role and name, then
   unplug/reconnect it when prompted. Select **Review paired devices**, then
   **Save and start inputs**.
4. Compare the received timer and cues with your controllers, then select
   **Open confidence display**.

Later launches reuse your saved configuration. **Device setup** reopens pairing.
The selected role must match the dongle's internal hardware configuration; USB
identifiers cannot distinguish the roles.

## Using the display

Choose a Limitimer source and program, then add a PerfectCue overlay if needed.
Separate browser windows can use different source/program selections.

**Open video output** opens a dedicated presentation window. Move it to your
extended display and press **F** for fullscreen. On supported local Chrome/Edge
browsers, **Choose display** lets you select a monitor first. **Escape** closes
an app-opened output window.

**Video layout** and **Video output settings** control presentation across open
video outputs. Source and program selections remain individual to each output.
Next appears as a green right triangle; Previous as a red left triangle.

Keep the application console open. Use **Quit application** in the operator page
or **Ctrl+C** in the console to stop the app; closing a browser tab leaves it running.

### LAN access

Open a network URL printed in the console on another computer or tablet.
Allow the app through Windows Firewall on your intended private network if needed.

LAN access is enabled by default and has no login. Connected users can view data,
change video settings, configure inputs, and quit the application. Use a trusted
network, or restrict access to the host PC:

```bat
DSANDisplay.exe --host 127.0.0.1
```

### Disconnected inputs

Lost timer input freezes the last received value and marks it stale/disconnected;
the display does not continue a local countdown. Reconnect the dongle and restart.
Changing USB ports or hubs may require pairing again. Check source assignments
after reconnecting or moving hardware.

Settings and logs are stored in `%LOCALAPPDATA%\DSANDisplay`.

## Compatibility

The packaged app targets **Windows 10/11 x64**. It uses native HID access and
requires no vendor DLL or replacement USB driver. The initial release is unsigned.

Live Limitimer data and simultaneous timer/cue inputs have been verified through
the Raspberry Pi path. Next/Previous cues have been verified with a cue emulator
and dongle. Windows builds pass automated tests and a packaged-app smoke test;
physical Windows USB/video output and a real PerfectCue controller still need
validation. PerfectCue Blank is not supported by the verified mapping.

macOS/Linux are useful for capture replay and Pi-based input. Direct macOS USB
has unresolved compatibility issues. See the [display guide](docs/display.md)
for these configurations.

## Run from source

On Windows, install **Python 3.13 x64** with the `py` launcher, then run
[Setup Windows.cmd](Setup%20Windows.cmd) followed by
[Start DSAN.cmd](Start%20DSAN.cmd). See [Windows setup](docs/windows.md) for details.

For replay on macOS/Linux, use Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m dsan_display --replay "Timer=/path/to/capture" --open-browser
```

Supply a recorded capture directory. Raw capture, annotation, and verification
commands are documented in the [capture reference](docs/development-reference.md#capture).

## Documentation

- [Windows executable guide](docs/windows-exe.md) — options, packaging, and builds
- [Display guide](docs/display.md) — sources, replay, LAN access, and output controls
- [Device pairing](docs/browser-setup.md) — setup behavior and validation
- [Multiple dongles](docs/multiple-dongles.md) — source identity and reconnect limits
- [Development reference](docs/development-reference.md) — capture CLI and investigation history
- [Protocol notes](docs/limitimer-protocol.md) and [dongle research](docs/dongle-research.md)
- [Third-party notices](docs/third-party.md)

For bug reports, include the app version, OS, controller/dongle models, and steps
to reproduce. Review logs before sharing: device paths and inventories can contain
local identifiers.
