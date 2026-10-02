# Raspberry Pi 5 USB investigation

The owner supplied `ssh pi@pi5start.local` after previously preferring to avoid Pi
setup. SSH key authentication and noninteractive sudo work. This Pi is now an
authorized diagnostic host; the eventual Mac/Windows application goal is unchanged.

## Prepared host

- Raspberry Pi 5 Model B Rev 1.0, Debian 13.2 (trixie), aarch64.
- Kernel `6.12.47+rpt-rpi-2712`.
- Investigation directory: `/home/pi/dsan-investigation`.
- Copied only the Python capture modules and requirements, not proprietary
  installers or unrelated workspace contents. Created a separate `.venv` there.
- Installed the pinned pyserial 3.5, hidapi 0.15.0, and pyusb 1.3.1 dependencies.
  Python compilation, dependency checks and disconnected discovery succeeded.
  This is not a successful dongle/decoder or multiple-device test yet.
- Installed tcpdump 4.99.5-2 and loaded `usbmon`; libusb was already available.
  No unrelated package upgrade was performed.

The Pi's external DNS failed. Dependencies were downloaded on the Mac and copied
over SSH, then installed offline. The tcpdump Debian package was verified against
the SHA-256 in the Pi's existing apt metadata. No network/DNS configuration was
changed. Preparation evidence is in [pi5-setup](../../inventories/pi5-setup).

## Runtime quirk

The initial `/sys/module/usbcore/parameters/quirks` value was empty. With the
dongle absent, it was set to **`0483:101a:d`** and read back successfully. This is
a runtime setting only: no boot configuration was edited, and reboot clears it.
The original and requested values are in
[quirk-change.json](../../inventories/pi5-setup/quirk-change.json).

The Raspberry Pi Linux 6.12 branch maps `d` to
`USB_QUIRK_CONFIG_INTF_STRINGS`; the USB core skips configuration-string fetching
when that flag is set. No explicit `101a` entry was found in the inspected quirk
table. Verify the attached device's effective quirk bits and actual traffic after
connection rather than assuming the runtime parameter proves the workaround.
([Kernel quirk source](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/drivers/usb/core/quirks.c),
[USB core source](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/drivers/usb/core/message.c))

Do not run verbose USB utilities that actively fetch every string: a user-space
request for index 92 could defeat a kernel-side workaround. Read cached sysfs
identity/descriptors first, then issue targeted, logged requests.

## Capture currently armed

At preparation, only root hubs were enumerated. A transient systemd service,
`dsan-usbmon-20260927-first-attach`, was started and verified active, recording
`usbmon0` before the dongle is connected. Its output directory is:

```
/home/pi/dsan-investigation/captures/first-attach-20260927
```

The service stops automatically after 900 seconds; tcpdump uses SIGINT for a
normal close and rotates at 16 MB into at most two files. See
[active-usbmon.json](../../inventories/pi5-setup/active-usbmon.json). This is a
preparation-time state, not a guarantee it is still active when work resumes.

Check service status and the log before relying on capture coverage. If its limit
expired before connection, use a new session/service for another connection
capture. Stop this specific unit after the comparison; never use a broad process
name kill that could affect unrelated tasks. Copy the captures back to this
workspace and record the host clock context before analysis.

## Clock mismatch

The Pi reported July 23 while the Mac reported September 27. Its clock was not
changed. A bounded SSH round-trip calibration records the approximate offset in
[clock-and-quirk.json](../../inventories/pi5-setup/clock-and-quirk.json).
Treat Pi wall-clock timestamps as unsynchronized. Use local monotonic capture
offsets and the calibration for correlation; do not compare raw Pi and Mac UTC
fields as though synchronized. Record a fresh calibration for later sessions.

## Next action

**Update: first attachment succeeded.** The records below supersede the
preparation-time pending state. No additional approval is needed for the
previously authorized dongle initialization messages.

### Observed result

- Dongle appeared at USB bus 3/address 2, sysfs `3-1`, with effective quirk
  value **`0x8`**. The kernel loaded `hid-generic` and exposed `/dev/hidraw0`;
  HIDAPI also enumerated the device. There is still no DSAN serial/COM port.
- Live standard GET_STATUS succeeded with `00 00`.
- The complete report descriptor was recovered from cached kernel sysfs:

  ```text
  06 a0 ff 09 01 a1 01 09 03 15 00 26 ff 00 75 08 95 08 81 02
  09 04 15 00 26 ff 00 75 08 95 40 91 02
  09 05 15 00 26 ff 00 75 08 95 40 b1 02 c0
  ```

  It describes vendor usage page `FFA0`, application usage 1, eight-byte input
  reports, 64-byte output reports and 64-byte feature reports, with no report-ID
  item. These lengths are now descriptor-backed, not just inferred from binaries.
- A 12-second native Linux hidraw capture received **1,356 eight-byte reports
  (10,848 bytes)**. It already received 1,880 bytes before initialization; 8,968
  followed it. One authorized HID output was sent after the two-second baseline.
  `write()` returned 65 bytes including the required userspace zero ID slot.
- USBmon independently confirms the exact wire request:
  `21 09 0200 0000`, length 64, `8D 00` followed by zeros, completed successfully
  with 64 bytes. No string-index-92 request appears in the captured enumeration.
  SET_CONFIGURATION, SET_IDLE and the HID report descriptor request succeeded.
- The USB monitor was explicitly stopped. It reported 3,087 packets captured,
  zero kernel capture drops. The trace and session were copied back to the Mac;
  raw capture length/hash validation passed.

Evidence: [descriptor/status/control trace analysis](../../inventories/pi5-first-attach),
[raw USB monitor capture](../../inventories/pi5-first-attach/usbmon/usbmon.pcap0),
[first application capture](../../captures/pi-hidraw-init-first).

### Acquisition quality and decoding limits

The USB trace has 1,509 successful interrupt input reports, more than the
application journal's 1,356. The journal preserves all bytes returned to it but
does not represent every report seen in the trace. Per-read disk fsync delays
are a plausible cause of read-buffer loss, not yet independently proven.

Offline decoding of the USB trace found 133 expected-length state frames and
139 short frames, all with **zero/absent checksums**. The application journal
also contains incomplete-length frames. No checksum integrity or timer-field
accuracy is claimed from this unlabelled run. The apparent decoded time changes
have not yet been compared with known physical states.

[pi_hidraw_capture.py](../../tools/pi_hidraw_capture.py) now records to Linux tmpfs
during bounded acquisition and copies/verifies the session on storage afterward.
It leaves the kernel HID driver attached and offers only the reviewed output,
opt-in. The default is receive-only. Its active RAM-backed data does not survive
power loss; copy failures preserve recovery files rather than deleting them.
A three-second [throughput check](../../captures/pi-tmpfs-throughput-check) received
376 reports and yielded 35 expected-length state frames with no length rejection
(only an initial partial-frame discard). This supports improved acquisition but
is not yet proof of zero report loss. The tool compiled on both hosts and the
saved capture's integrity check passed.

The owner confirmed program 1 stopped at exactly 1:00. The subsequent
[ten-second capture](../../captures/pi-p1-stopped-0100) received 1,251 reports
(10,008 bytes), containing 113 complete state frames and 115 short frames. Three
initial state frames showed an older running 30-minute state; then **110
consecutive state frames** matched P1 selected, stopped, total 60, elapsed 0,
remaining 60. The first matching frame arrived at elapsed 0.367 seconds. Preserve
this initial old data; it is evidence that opening a connection does not by
itself guarantee the first value is current. The buffering location is not yet
established.

There were no rejected state lengths in this run and no FF terminators. All
checksums were zero/absent, so field agreement is not CRC validation. The raw
reports were promoted to a [real test fixture](../../tests/fixtures/dongle/pi-p1-stopped-0100.bin)
with [provenance](../../tests/fixtures/dongle/pi-p1-stopped-0100.json). The regression
test verifies the old prefix is preserved and all 110 later states match the
user's observation, even when normalized payloads are split across feed calls.
All **44 current unit tests** pass. Running, pause, zero-crossing and program
selection still need their own labelled captures.

The recorder now publishes metadata for annotations during acquisition and a
periodic status file, while raw/journal writes remain on tmpfs. The next recording
will be armed before asking the user to start P1, using a bounded systemd service
so it survives a chat turn. Keep the quirk active for these tests.

### Running, zero and paused observations

The [90-second running recording](../../captures/pi-p1-running-window) completed
normally with 11,251 reports and 976 state frames, with no rejected state lengths.
P1 changed from stopped to running at elapsed 19.162 s, and the elapsed field
progressed through every integer 0–71. Remaining reached zero at 78.404 s and
then became negative. The owner confirmed the physical display stayed at 0:00.
The configuration's `continue_after_zero` bit was false throughout. Rendering
must therefore clamp countdown display to zero for this behavior rather than
show negative arithmetic as visible overtime. Optional continue-after-zero mode
is not yet verified.

The owner then reported paused at 0:52. Since the earlier run had expired,
intervening reset/start actions were not inferred. A separate
[paused capture](../../captures/pi-p1-paused-0052) received 1,251 reports and 112
state frames: three old running frames first, then 109 consecutive states with
P1 selected, run false, total 60, elapsed 8 and remaining 52. Both captures have
zero/absent checksums and no FF terminators. Raw fixtures and provenance are in
[dongle fixtures](../../tests/fixtures/dongle); all **46 current tests** pass.

The next capture, `pi-program-switch`, is armed under the bounded
`dsan-program-switch-20260927` systemd unit for 90 seconds, pending the owner
selecting P2 and reporting its displayed time. Check actual service state before
relying on coverage in a later turn. That recording has now completed normally.
It received 11,251 reports with 984 state frames. Selection changed from P1 to
P2 at elapsed 18.008 s. P1 remained paused at 52 seconds; P2 remained stopped,
total/remaining 1,920 seconds. The owner corrected the initially reported 0:32
to **32:00**, which matches the data. The raw reports and provenance are saved
as the fourth real dongle fixture, and its regression verifies source-program
state separation.

The Mac [confidence display](display.md) now reads a live JSON report stream from
the Pi using read-only `/dev/hidraw0` access. No diagnostic recording service is
left active. The application server's SSH reader remains active while the display
task runs. Its heartbeat lets a closed SSH connection terminate the remote reader.

### Interpretation of the USB workaround

The Linux host with the interface-string quirk remains responsive and streams
data, unlike the earlier Mac enumeration. This is strong evidence for the
workaround's usefulness on the Pi, not proof of the exact firmware defect or of
a working Mac override. Input existed before the initialization write, so the
earlier missing-initialization hypothesis does not explain all prior failures.
The reviewed output mapping is now observed successfully on the wire.

### Original attachment procedure

The owner should fully remove dongle power by disconnecting USB and RJ45, wait ten
seconds, reconnect RJ45 to the PRO-2000, then connect USB to the Pi. On confirmation:

1. Confirm active USB recording and exact device identity/topology/quirk bits.
2. Inspect the enumeration trace for index-92 requests and successful HID report
   descriptor completion. Determine whether HIDAPI now exposes a usable device.
3. Try a short logged receive-only baseline, then the already-authorized reviewed
   Limitimer initialization if the device is responsive. Match the chosen
   transport's report-ID convention. Do not use the old Mac bus/address.
4. If sustained input appears, collect labelled timer states one at a time and
   validate decoding. If not, diagnose the trace before more button changes.

After testing, stop the capture service. The temporary quirk can be restored to
its recorded empty value with the dongle unplugged, or cleared by a reboot. Do
not change boot files unless a persistent setup is subsequently wanted.

## Second dongle: owner-identified PerfectCue

With the original Limitimer still at USB port `3-1`, `/dev/hidraw0`, the owner
attached a second dongle identified as PerfectCue. It appeared at USB port `1-1`,
bus 1/address 2, `/dev/hidraw1`. Both report `0483:101A`, serial
`Ver 0.17 10/03/14`, the same 47-byte HID descriptor and effective quirk `0x8`.
The firmware serial string therefore cannot distinguish these two physical units.
The connected inventory is saved in `inventories/second-dongle-connected.json`.

The receive-only baseline `captures/pi-perfectcue-idle-first` contains 1,251
eight-byte reports (10,008 bytes) over ten seconds, all eight zero bytes. Capture
integrity validated both on the Pi and after copying to the Mac. These are empty
count-envelope reports, not cue events and not proof the PerfectCue controller
is connected. No initialization or other application output was sent, and the
Limitimer reader was left alone. Controller model and physical controller cable
connection remain unconfirmed. Pi wall-clock timestamps remain unsynchronized.

The capture helper now accepts hardware role, controller model and signal path
so PerfectCue sessions are not incorrectly labelled PRO-2000. It rejects the
Limitimer output flag when a PerfectCue role is selected. Syntax compilation and
editor checks passed. The next capture is armed for one owner-confirmed Next
press; do not treat its anticipated event as verified until the capture and
owner's action confirmation are inspected together.

### Mixed-button capture and PerfectCue initialization

The owner reported pressing both Next and Previous twice each, and confirmed
those button identities. Order and hold duration were not specified. The
originally named `pi-perfectcue-next-first` session is therefore annotated as a
mixed-button capture, not an isolated Next fixture. It was gracefully stopped and
saved: 12,790 reports / 102,320 bytes, all zero, with validated integrity. No cue
payload was observed during those reported actions.

`captures/pi-perfectcue-init-first` then recorded one role-specific `8D 01`
output to `/dev/hidraw1` after a two-second receive-only baseline. The hidraw API
returned 65 bytes written (zero report-ID slot plus 64-byte output); this is an
API result, not a new USB wire trace. The ten-second session contains 1,250 zero
reports and one report `05 81 0F 01 00 83 00 00`. Integrity passed locally and on
the Pi. The payload `81 0F 01 00 83` is associated with initialization; its meaning
is unknown and it must not be called a verified Next event just because it
contains `0F`. No new user button action was requested during initialization.

The provisional decoder now rejects entire cue payloads containing unknown bytes,
rather than extracting apparent cue bytes from such messages. A regression checks
this actual observed report. Thirteen focused tests, syntax compilation and editor
checks passed. The Pi helper supports explicitly requested PerfectCue startup,
records the exact output/result, and rejects either role's output flag when the
other role is selected. CLI rejection checks passed before hardware access.

A new receive-only isolated-Next capture is armed after initialization; its result
and the owner's next action must still be checked. The Limitimer source was not
initialized, stopped or rebound during these operations.

### Isolated Next after initialization

The owner confirmed one Next/right-arrow press and release. The resulting
`captures/pi-perfectcue-next-isolated` session was gracefully stopped, copied to
the Mac and integrity-checked: 8,005 reports / 64,040 bytes. Of those, 7,996 are
empty reports and nine contain stream payload. The payload is framed, not simply
the raw serial cue bytes assumed by the provisional UI mapping. One USB report
contains a complete message plus the beginning of the next, with the remainder
in the following report, confirming that USB boundaries are not message boundaries.

After an opening prefix, `81 0F 01 00 83` occurs at 5.215, 25.216 and 45.217 s;
`81 0F 01 01 83` occurs at 15.216, 35.216 and 55.218 s. There is also an
off-schedule `81 0F 01 00 83` at 38.657 s. The owner did not supply an exact
press timestamp, so this is a candidate correlation, not a verified field/event
mapping. The periodic traffic means `0F` alone cannot establish a new Next press.
The existing conservative decoder leaves these payloads unknown. An isolated
Previous capture is the next comparison. No new initialization was sent.

### Emulator clarification and Previous comparison (supersedes assumptions above)

The owner clarified there is **no PerfectCue controller box**, only an emulator
which triggers alternately every ten seconds. All five cue capture sessions now
carry provenance-correction annotations; original metadata/raw bytes are retained.
The periodic messages are emulator triggers, not a demonstrated dongle heartbeat.

The Previous capture has 8,246 reports / 65,968 bytes: 8,238 empty and eight framed
messages. The off-schedule `81 0F 01 01 83` at 40.903 s accompanies the confirmed
manual Previous action; the earlier manual Next capture has the off-schedule
`81 0F 01 00 83` at 38.657 s. Together with the user's alternating-emulator
confirmation, these establish Next=00 and Previous=01 **for this emulator/dongle
path**. Exact press timestamps were not measured. Real PerfectCue behavior, Blank,
release semantics and the emulator model/cable path remain unverified.

The original parser now handles the observed five-byte framed stream rather than
extracting individual serial cue bytes. Raw fixtures preserve both entire sessions,
with source scope and hashes. Unknown values stay unknown; no checksum is claimed.
All 70 tests pass. The mixed-dongle preview reads Limitimer `/dev/hidraw0` and cue
emulator `/dev/hidraw1` simultaneously over independent SSH readers; a live Next
cue was observed in the browser while the timer continued updating. Startup data
is suppressed for one second before cue display; this does not prove that every
possible buffer has drained. The shared serial string is still not an identity.

Static vendor inspection provides additional context, not new copied code: the
PerfectCue application's serial path at RVA C4CB–C50D constructs five-byte messages
by placing a serial byte's low nibble at offset 1, literal 01 at offset 2, high
nibble at offset 3, with configured delimiters. Its type-3 branch at RVA D062–D07E
checks offset 2 equals 01 and consumes offset 3. This agrees with the captured
00/01 mapping and explains why the bare serial bytes and USB stream differ. It
does not verify this emulator against a real controller. No vendor code was executed.
