# User guide

This software shows a Limitimer countdown and PerfectCue Next/Previous cues as a
full-screen video output for confidence monitors and stage displays. It reads a
VC-2000-LT (Limitimer) and a VC-2000PC (PerfectCue) at the same time on one PC.

## Requirements

- Windows 10 or 11, x64
- A web browser (Chrome or Edge recommended)
- A DSAN VC-2000-LT for Limitimer and/or a VC-2000PC for PerfectCue. You can use either or both.

Each dongle is set to Limitimer or PerfectCue by DIP switches inside it. Open the
dongle to reach them; the correct positions for each role are marked inside. Set one
dongle for each controller before you start. See the
[DSAN VideoClock documentation](https://www.dsan.com/video-clock-software/) for more.

Tested with a VC-2000-LT and a VC-2000PC, a Limitimer PRO-2000 controller, and
PerfectCue Next/Previous from a PerfectCue emulator. Both report firmware `Ver 0.17 10/03/14`.

No vendor software or extra drivers are needed. Close DSAN VideoClock and any
other software that uses the dongles before starting.

## First launch

1. Extract **DSANDisplay-windows-x64.zip** and run **DSANDisplay.exe**. Keep the
   `licenses` folder with it. A console window and a browser page open; keep the
   console open while you use the app.
2. Follow the pairing wizard:
   - If the dongles are already connected, choose a role (Limitimer or
     PerfectCue), then unplug and reconnect that dongle when asked.
   - If none are connected, plug them in one at a time when asked.
   - Give each dongle a name, then select **Review paired devices** and
     **Save and start inputs**.
3. The last page shows the timer and cues being received. Check them against
   your controllers, then select **Open confidence display**.

The role you choose in the wizard must match the dongle's DIP switch setting.
The app can't read the switches, so make sure you choose the right role.

Your setup is saved. Later launches start the paired inputs automatically.
To pair again, select **Device setup** in the page header.

## Confidence display

The operator page shows the selected timer and cues.

- **Timer source** chooses the Limitimer input. **Program** follows the controller's
  active program, or shows Program 1–4. This only changes what's displayed; it
  never changes the controller.
- **Cue source** adds PerfectCue cues to the display.
- Each browser window can show a different source and program.

## Video output

1. Select **Open video output**. A clean output window opens with only the timer
   and cues.
2. Move it to your monitor, projector, or switcher output, then press **F** for
   fullscreen.
3. Press **Escape** to close the output window. The operator page stays open.

To place the output on a specific monitor, select **Choose display** before opening
it, allow the browser permission, and pick the monitor from **Output display**.
This works in Chrome or Edge on the computer running the app.

You can open several output windows. Each keeps the source and program that were
selected when it opened.

### Output settings

These apply live to every open output window:

- **Video layout**: Timer only, Cues only, or Both.
- **Timer size** and **Cue size**: 50% to 150%.
- **Warning threshold**: when the timer turns amber (default 30 seconds). It turns
  red at zero.
- **Show overtime past zero**: show negative time after zero instead of stopping
  at 0:00.

The confidence display has its own **Show overtime past zero** setting.

Next appears as a green right-pointing triangle and Previous as a red left-pointing
triangle. Each cue shows for about one second.

## Using other devices on your network

The console prints a network address, such as `http://192.168.1.20:8765/`. Open
it on another computer or tablet on the same network. If it doesn't connect,
allow DSANDisplay.exe through Windows Firewall for your private network.

There is no login. Anyone who can reach the address can change settings,
change device setup, or quit the app. Use a trusted network, or limit access to
the host PC:

```bat
DSANDisplay.exe --host 127.0.0.1
```

## If an input disconnects

The display never counts down on its own. If a dongle disconnects or stops sending
data, the display freezes on the last value and marks it as stale or disconnected.
The other input keeps working.

Reconnect the dongle and restart the app. If you move dongles to different USB
ports or hubs, you may need to pair them again.

## Quitting

Select **Quit application** at the top right of the operator page, or press
**Ctrl+C** in the console. This closes the output windows and stops the app.
Closing a browser tab doesn't stop the app, and quitting doesn't affect your
controllers.

## Command-line options

Run these from Command Prompt in the folder containing DSANDisplay.exe:

| Option | Effect |
| --- | --- |
| `--configure` | Open the pairing wizard again |
| `--host 127.0.0.1` | Allow access from this PC only |
| `--port 8765` | Use a different port |
| `--data-dir "D:\Show Data\DSAN"` | Store settings and logs in another folder |
| `--self-test` | Check the app without using any hardware |

## Settings and logs

Settings and logs are stored in `%LOCALAPPDATA%\DSANDisplay`. Logs may include
local device identifiers; review them before sharing.

## Known limitations

- PerfectCue Blank is not supported.
- The executable is unsigned, so Windows may warn you the first time you run it.
- The app shows whatever the browser window shows. It doesn't set display
  resolution or produce SDI or NDI output.

## Trademarks

This software is an independent project and is not affiliated with, endorsed by,
or sponsored by DSAN Corporation. DSAN, Limitimer, PerfectCue, and VideoClock are
trademarks of DSAN Corporation. Product names and model numbers are used only to
identify compatible hardware.
