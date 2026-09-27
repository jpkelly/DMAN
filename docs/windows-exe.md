# DSAN Display executable

## Running the package on Windows

Extract the package and double-click **DSANDisplay.exe**. Python does not need to
be installed on the operating machine. Keep the `licenses` folder with the
distribution. The executable also embeds those notices. A normal browser is
still required; the first package deliberately uses the existing console setup
and browser renderer, not a new native window framework.

On first launch select the exact dongles, name them, assign Limitimer or PerfectCue
to match their internal hardware configuration, and select each startup mode.
USB IDs and firmware-looking serial strings cannot identify their roles. Settings
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
DSANDisplay.exe --self-test
DSANDisplay.exe --data-dir "D:\Show Data\DSAN"
```

`--configure` replaces source selection after the complete new selection validates.
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
