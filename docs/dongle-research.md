# VC-2000PC application interface: offline research

Research date: 2026-09-26. No dongle access, device commands, installer execution,
or Windows execution was performed for this research.

## Main finding

The Windows application does more than passively listen: after opening the HID
device, it sends a device-mode selection message. In the inspected Limitimer
path, that message is **`8D 00`**, packaged as a HID output report. The PerfectCue
path selects **`8D 01`**. The application then reads a byte stream reconstructed
from HID input reports.

The owner now explicitly confirms that **this dongle has worked with a Limitimer**.
That supersedes the earlier tentative compatibility recollection. Successful
operation with our Mac implementation remains to be demonstrated.

The owner additionally reports that the dongles can serve **Limitimer or
PerfectCue**, with internal DIP switches or jumpers selecting their purpose.
Treat that as user-provided hardware-configuration evidence. The specific switch/
jumper layout, positions, and effects have not been inspected here. The `8D`
messages are application-side startup behavior associated with the selected
device type; they must not be described as replacing or changing those physical
settings. A test must match the intended software mode to the dongle's hardware
configuration.

Missing initialization is now a concrete explanation to test for our earlier
one-report-then-silence results. It is an inference, not a proven diagnosis:
macOS's descriptor timeouts are a separate unresolved issue.

## Evidence and provenance

The owner supplied [the PerfectCue installer](../VideoClock_For_PerfectCue/VideoClockForPerfectCueSetup.exe)
and [its ZIP package](../VideoClock_For_PerfectCue.zip). The supplied executable
is byte-for-byte identical to the executable in DSAN's official
[PerfectCue download](https://www.dsan.com/wp-content/uploads/2021/11/VideoClock_For_PerfectCue.zip).
It was compared with the official
[Limitimer download](https://www.dsan.com/wp-content/uploads/2021/11/VideoClockForLimitimer.zip).

The owner subsequently supplied [the Limitimer installer](../VideoClockForLimitimer/VideoClockForLimitimerSetup.exe)
and [its ZIP](../VideoClockForLimitimer.zip). A fresh offline audit confirms the
installer is byte-for-byte identical to the researched official version; both
embedded PE image hashes are unchanged. The ZIP's installer also matches the
extracted file. Its configuration identifies version 0.75 and device type 1.
The Limitimer audit now points to this reproducible workspace input and retains
the earlier source path as provenance. No installer was run.

Both installers contain a Gammadyne `.setup` section with independently
decompressible zlib blocks. Static decompression recovered application images,
configuration text and the shared USB support library. No executable or DLL was
run or loaded. PE import/export inspection and focused x86 disassembly established
the call paths below. Proprietary binaries remained in scratch storage.

| Item | SHA-256 |
| --- | --- |
| Supplied PerfectCue installer, 7,546,880 bytes | `ebc6df7eca35821f23f18704ce6d1795c4249df8fc862efd8ed5051973430b71` |
| Supplied Limitimer installer, 10,160,640 bytes; matches DSAN download | `69f23a1ce3c9df04de31589717313bcb01866a2129810cc5dcaaa713b3897212` |
| PerfectCue application PE section span | `60ab9cc122b0a96e68e80a12993a4ae51bc1840c79390cd853490b294d72872d` |
| Limitimer application PE section span | `55da7d25edecdd351bd56828814c5f693cc67abca83993af43619c8108cad9b8` |
| USB library PE section span, identical in both packages | `6a9e004a2ec543a27d351425e5a4aa99099fc5e80e24ac705eb64586f1f87ba6` |

Embedded hashes deliberately cover PE headers through the last raw section,
excluding possible overlays/installer metadata. They must not be confused with
the enclosing installer hash. The shared USB image span is 69,632 bytes; each
application image span is 344,064 bytes.

[PerfectCue audit](vendor-perfectcue-audit.json) and
[Limitimer audit](vendor-limitimer-audit.json) preserve block offsets, identities,
imports and exports. The original [offline audit script](../tools/audit_dsan_installer.py)
reproduces that metadata without extracting files into the project or accessing
hardware:

```sh
.venv/bin/python tools/audit_dsan_installer.py VideoClock_For_PerfectCue/VideoClockForPerfectCueSetup.exe
.venv/bin/python tools/audit_dsan_installer.py VideoClockForLimitimer/VideoClockForLimitimerSetup.exe
```

It supports the two inspected installer layouts, not arbitrary Windows installers.
Unknown container fields are not assigned invented meanings. Both packages were
processed successfully: 79 records/12 zlib blocks for PerfectCue, 80 records/9
blocks for Limitimer. The extracted PE hashes match the independently inspected
images. Seven important machine-code checkpoints were also checked against the
images. The research script passed Python syntax checking. No Windows build or
hardware test is implied by these checks.

## How the application communicates

```mermaid
flowchart LR
    T[PRO-2000 controller] -->|RJ45 data link| D[VC-2000PC dongle]
    A[Windows VideoClock] -->|select device mode| U[USB support library]
    U -->|HID output report| D
    D -->|HID input reports| U
    U -->|payload byte stream| A
    A --> P[Timer packet parsing and display]
```

### Device selection is confirmed in the binaries

The application imports the USB library's open-by-ID, close, connection-status,
read-data and write-message functions. Both application builds pass **`0x101A`**
to open-by-ID. The library's enumeration callback additionally compares the
vendor ID with **`0x0483`**. These match the device identified by our physical
disconnect/reconnect experiment.

The configuration's COM-port value `255` selects the application's HID branch;
it is not evidence of a real serial port numbered 255. The normal USB receive
path calls the library's read-data function, which drains its input ring buffer.

### A mode-selection output follows opening

The two defaults use different device-type values: Limitimer uses `1`, PerfectCue
uses `3`. On a successful open, the application's branch for type `1` invokes a
helper with argument `0`; type `3` invokes it with argument `1`. That helper builds
the two-byte message `8D <argument>` and calls the USB write-message function.

| Application selection | Configuration type | Message passed to USB helper |
| --- | --- | --- |
| Limitimer | `1` | `8D 00` |
| PerfectCue | `3` | `8D 01` |

Another branch emits `8D 02`; assigning its purpose is unnecessary for our
Limitimer test. This research does not establish what firmware settings the
messages change, their persistence, or whether a message is acknowledged.

The library places the message after a zero report-ID slot and calls Windows
`WriteFile` with **65 bytes**. On first use, the remaining static buffer storage
is zero-initialized. Thus a first Limitimer selection is represented at that API
boundary by `00 8D 00` followed by 62 zero bytes. The helper reuses its output
buffer, so do not assume every later write clears all unused bytes.

Microsoft defines Windows HID buffer lengths to include the report-ID position,
including a zero slot when reports are unnumbered. That explains why an API
buffer length is not automatically the USB wire payload length.
([HIDP_CAPS](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/hidpi/ns-hidpi-_hidp_caps))

### Continuous input uses reads, not repeated feature requests

The library opens a Windows HID collection with overlapped I/O and runs an input
thread issuing **9-byte `ReadFile` calls**. It waits for completion and reads
again. The reader thread is created during open, before the application sends
its mode-selection message; a future experiment should arm input before sending
that one output. Although the DLL exports feature-reading and many writing helpers, those
exports do not establish that VideoClock uses them. The traced normal input path
uses `ReadFile`, not a loop of HID feature or input-report control requests.

This is consistent with Microsoft's recommendation to use reads for continuous
input. Microsoft specifically warns that repeated `HidD_GetInputReport` calls
can lose reports and can make unsupported devices unresponsive.
([Obtaining HID reports](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/obtaining-hid-reports))

### Input reports wrap a byte stream

The library ignores the first Windows report slot and interprets the next byte:

| Byte at Windows offset 1 | Library behavior |
| --- | --- |
| Below `7F` | Payload byte count; copy that many following bytes, bounded by received length |
| `7F` | The next byte provides the count; payload begins one byte later |
| `80` | Separate internal status handling; not normal timer-stream data |
| Above `80` | Separate message queue; not automatically appended to the byte stream |

For the ordinary 9-byte Windows input buffer, there are seven bytes after the
report-ID slot and count. Under the usual unnumbered-report mapping, a raw USB
interrupt transfer contains eight bytes: count plus up to seven payload bytes.
The repeated leading `07` in our captures is therefore strongly explained by
the vendor receiver's count handling.

For example, our saved raw report:

```text
07 81 00 21 6F 09 00 01
```

corresponds under this interpretation to seven stream bytes:

```text
81 00 21 6F 09 00 01
```

This is a fragment, not a complete timer packet. The original captures remain
unchanged. No countdown, program selection, warning state or CRC has been
verified from those fragments.

HIDAPI's Windows backend already removes the extra zero report-ID slot from
unnumbered reads. Therefore a future HIDAPI-based receiver must not blindly strip
two bytes as though it were consuming Windows `ReadFile` buffers. Explicitly
identify each transport's buffer convention.
([HIDAPI Windows source, v0.15.0](https://github.com/libusb/hidapi/blob/hidapi-0.15.0/windows/hid.c))

### Auditable locations

Addresses below are RVAs, before adding the preferred image base. The applications
use base `00400000`; the USB library uses `10000000` in the inspected images.

| Evidence | PerfectCue app RVA | Limitimer app RVA / library RVA |
| --- | --- | --- |
| Open PID `101A` | `CC8E` | `CC96` |
| Open and device-type branch | `CC84` | `CC8C` |
| Build `8D <mode>` helper | `D1CA` | `D1E2` |
| Call USB write-message | `D1EA` | `D202` |
| Vendor `0483` filter | shared library | `1C00` |
| 9-byte input read | shared library | `1E64`–`1E68` |
| Count/type handling | shared library | `1EC8`–`1F76` |
| 65-byte output write | shared library | `1A32`–`1A3C` |
| Zero report-ID initialization | shared library | `1AA5` |
| App read-data import slot | `173AC` | `173AC` |

For Limitimer, the host stream parser recognizes start `81` and marker `83`, and
accepts lengths 52 or 55 at that marker in this build (`C173`–`C198`). This is
not identical to a claim that every wire packet is 55 bytes including CRC and
trailing `FF`. It is another reason to verify complete captures before importing
the Depili library's framing rules unchanged. Do not copy the vendor parser's
permissive behavior as a substitute for meaningful checksum validation.

## Model names and documentation traps

DSAN's [legacy software page](https://www.dsan.com/video-clock-software/) names
separate VC-2000PC/PerfectCue and VC-2000-LT/Limitimer packages. Their ReadMe files
warn to match dongle configuration and software. The shared VID/PID and library
show a common application-facing USB interface; they do not prove that every
physical variant is interchangeable. For this particular unit, the owner's
explicit successful Limitimer test resolves the compatibility question at the
user-observation level. The subsequent report of internal role-selection switches/
jumpers also explains why DSAN instructs users to match dongle configuration and
software. VID/PID alone cannot identify the current physical role.

The [current VC-2000-2 page](https://www.dsan.com/product/video-clock-for-limitimer/)
describes two RJ45 ports and embedded software storage, unlike this single-port
HID unit. DSAN's
[PerfectCue Remote document](https://www.dsan.com/perfectcue/files/PerfectCueRemote.pdf)
also describes serial/COM access for newer equipment. Those details cannot be
silently applied to this older HID device. Likewise, DSAN's description of a
PerfectCue cue light as a USB keyboard is about the cue light's native computer
connection, not evidence that the VideoClock dongle emits keyboard reports.

## What this changes about our diagnosis

- We selected the correct VID/PID. The installer confirms it.
- Passive interrupt reading is a valid kind of HID input transport, but our
  receive-only experiments did **not** reproduce the application's mode-selection
  output. Their silence is not evidence against Limitimer compatibility.
- Switching to repeated GET_REPORT polling is not the default fix suggested by
  either the application or the HID guidance.
- The leading count byte can now be investigated with a software-derived format,
  rather than guessed from one eight-byte sample.
- The 47-byte report descriptor remains unavailable on the tested Mac. Its
  advertised length is unrelated to the 9/65-byte Windows API buffers.
- The Mac enumeration string-descriptor timeout and missing HIDAPI entry may
  still block a native HID implementation even after the mode is understood.
- Temporarily stopping Ultraleap did not establish it as the cause. It has been
  restored and verified running; no service changes occurred during this research.

## How we can use this

### Additional references supplied by the owner

Inspected the [sytem/clock-8001 PerfectCue notes](https://gitlab.com/sytem/clock-8001/-/blob/8ac59272b6dbe2fba40890a2adc3a98d2451affa/perfectcue.md)
and [jpkelly/clock8002 Limitimer notes](https://github.com/jpkelly/clock8002/blob/6d48e7003ba86e5b75d95e34874bfb1a0f37c553/limitimer.md).
These describe direct serial/RS-485 adapters, not the VideoClock USB HID wrapper.
The [clock8002 listener](https://github.com/jpkelly/clock8002/blob/6d48e7003ba86e5b75d95e34874bfb1a0f37c553/app/clock/limitimer.go)
opens a serial port at 19200 baud and passes received bytes into Depili's decoder.
It does not supply the missing HID startup/envelope layer for our dongle.

The Limitimer notes map four programs plus a view following the selected program.
That supports offering a per-source “follow active program” display option.
The PerfectCue notes and
[listener](https://github.com/jpkelly/clock8002/blob/6d48e7003ba86e5b75d95e34874bfb1a0f37c553/app/clock/perfectcue.go)
describe cue bytes `0F`, `1F`, `2F`, `3F`; these are distinct from timer-state
packets. Neither document provides the dongle's internal jumper map.

The PerfectCue document reports electrical differences on the tested unit and
contains inconsistent color assignments: its color examples assign some of the
same conductors to different signals. Do not turn those examples into build
instructions without checking numbered pins, the actual model and wiring. The
documents also identify power on RJ45; these are not ordinary Ethernet links.
No rewiring is proposed or performed here.

Both repository licenses carry GPL-2.0-or-later project notices. No code from
either fork was incorporated. They are payload/protocol references to validate
against our captures, not proof of settings for the USB HID transport.

**Multiple dongles are a required use case.** The owner reports erratic behavior
with the existing application when several are connected. Further inspection
shows process-global device/receive state in the vendor DLL and first-match
selection by VID/PID. That makes its single-context interface unsuitable as our
multi-source design. See [the source-isolation requirements](multiple-dongles.md)
for evidence, identity/reconnect handling, and the planned hardware tests. This
is not a proven diagnosis of the reported erratic behavior.

Keep the existing Python capture/replay foundation and separate four layers:
transport-specific report representation, HID envelope removal, Limitimer stream
framing/checksums, and timer state/rendering. One HID report need not equal one
timer packet. Preserve both the raw report and the normalized payload with
provenance; do not overwrite raw captures.

The next hardware experiment should reproduce **one reviewed mode-selection
output**, after confirming the dongle is physically configured for Limitimer,
then keep reading input. The original receive-only instruction remains
in force: no write was implemented or sent here. When hardware returns, obtain
explicit authorization for this limited output before attempting it, retain the
exact outbound bytes and result in the session, and leave all unrelated commands
disabled. There is no reason to scan baud rates or change firmware.

For a native HID path, HIDAPI's output-report method accepts a buffer with a
leading report-ID slot. If the interface still cannot be enumerated as HID, the
existing libusb transport is a candidate for direct report I/O. Since the saved
descriptor lists no interrupt-OUT endpoint, a standard HID output report over
endpoint 0 is the route to evaluate. The candidate USB setup would be
`bmRequestType=21`, `bRequest=09` (SET_REPORT), `wValue=0200` (Output, report ID 0),
`wIndex=0`, with a 64-byte data payload beginning `8D 00`. This is a
**standards-derived mapping of the observed Windows write**, not a captured or
hardware-verified USB transaction. It is an Output report, not a Feature report.
([USB HID specification, §§4.4 and 7.2](https://www.usb.org/sites/default/files/documents/hid1_11.pdf),
[HIDAPI libusb implementation](https://github.com/libusb/hidapi/blob/hidapi-0.15.0/libusb/hid.c))

If that control transfer stalls, do not issue guessed fallback commands. A
Windows USB trace of the same startup or manufacturer confirmation would then
be the most direct missing evidence. An output report may change device state;
its persistence and other firmware effects have not been determined here.

After sustained input is established, repeat the labelled stopped/running/paused/
zero-crossing/program-switch captures. Only then implement and validate complete
timer packets, unknown fields, resynchronization, warning/overtime state, and
stale-on-disconnect behavior. No Mac or Windows display compatibility is claimed
from static analysis alone.

## Reuse boundaries and remaining unknowns

No license granting redistribution or incorporation of DSAN's DLL/application
code was established. None was linked, copied into the app, or redistributed as
a deliverable. The audit script is original PE/container-inspection tooling;
the report records behavior and evidence. Future implementation should use the
documented interface behavior without copying vendor code or artwork. The
existing GPL obligations for any reuse of Depili/Clock-8001 remain in
[third-party notes](third-party.md).

Still unknown: the actual report descriptor; the complete startup USB exchange;
firmware-side meaning/persistence of `8D`; why macOS enumeration times out; and
whether that Mac can sustain input after correct initialization. The report
does not claim any of those questions has been solved without hardware.
