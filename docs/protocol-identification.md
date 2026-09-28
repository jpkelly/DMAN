# Probing dongle role: observed protocol versus hardware identity

The two attached interfaces have identical USB VID/PID, firmware serial string,
product name and report descriptor. Those descriptors do not distinguish the
owner-assigned Limitimer and PerfectCue roles.

## Receive-only experiment

Both existing Pi HID nodes were captured for 25 seconds with their role explicitly
recorded as **unknown**, without sending initialization or changing the existing
stream workers. The analysis ignored the first second to reduce opening-buffer
effects. This settling interval cannot prove that all possible old data is gone.

| Node / physical USB path | Evidence after settling | Observed protocol |
| --- | --- | --- |
| `/dev/hidraw0` / `3-1` | 243 complete, structurally valid timer state frames; absent checksums; no cue frames | Limitimer |
| `/dev/hidraw1` / `1-1` | Two framed cue messages, one Previous and one Next; no timer state frames | PerfectCue-format emulator traffic |

The raw captures are `captures/pi-role-probe-0` (25,000 bytes) and
`captures/pi-role-probe-1` (25,008 bytes); both completed with matching byte counts
and integrity hashes. Results are saved in `inventories/protocol-role-probe-*.json`.
The cue source is the owner's emulator, which alternates every ten seconds, not
a real PerfectCue controller. These paths had already been configured in earlier
work, including a successful `8D 01` command on the cue source. This experiment
does not establish cold-start identification before initialization.

The original [protocol evidence classifier](../dsan_capture/protocol_probe.py)
uses both stream decoders without consulting the recorded role or label:

```sh
.venv/bin/python -m dsan_capture.protocol_probe captures/pi-role-probe-0
```

It returns Limitimer after at least three timer states, or PerfectCue-framed after
at least two known cue frames. These are conservative diagnostic heuristics, not
protocol-specified thresholds. Conflicting evidence is ambiguous; silence,
unsupported traffic and insufficient evidence remain unknown. It does not change
device selection, role assignment, saved bindings or output modes. Real capture
fixtures cover both classifications, silence/insufficient evidence and mixed data.

## One feature-report query per interface

The vendor library's `_usbReadFeature@8` at RVA `2670` requests a feature report
with ID 0 and a 65-byte API buffer (zero report-ID slot plus 64 bytes). The observed
descriptor advertises this feature size. One corresponding Linux HIDIOCGFEATURE
query was made per exact HID node after checking VID/PID and the descriptor.
The ioctl definitions were checked against the Pi's installed Linux headers.

Both queries returned **65 zero bytes**, in approximately 2.1 ms and 1.3 ms.
They provide no distinguishing role information. Requests/results are preserved
in `inventories/feature-role-probe.json`, locally and on the Pi. The getter used
native hidraw with no driver detach or output reports; each query ran under an
eight-second process bound, with no retries. Both live display streams remained
connected afterward. Pi wall-clock timestamps remain unsynchronized.

The library also exports `_usbRequestID@4`. Static inspection at RVA `28A0` shows
it sends command `80` using `_usbWriteCmd` and waits for an ID response. The ID's
relationship to hardware role or switch position is not established, and this
command was not sent. An export's name is not proof of an appropriate type query.

## Practical conclusion

Active traffic can provide a useful role suggestion or configuration check. It
does not identify a unique physical unit, read the internal DIP/jumper setting,
or reliably classify a silent/uninitialized device. Automatic startup should
keep an explicit unknown state, avoid changing modes just to force a match, and
retain operator-confirmed role bindings. It also cannot repair Windows device
enumeration conflicts caused by duplicated hardware identifiers.

## USB port-swap trial

The owner unplugged both USB connections, leaving the controller/emulator cables
and internal settings unchanged, then reconnected the dongles to opposite Pi USB
ports. While unplugged, the OS listed no DSAN HID devices; both display sources
became disconnected/stale and their last values and report counts stayed frozen.

After reconnecting, `/dev/hidraw0` was at port `1-1` and `/dev/hidraw1` at `3-1`,
the reverse physical-port mapping from before. In this insertion sequence the
hidraw numbers happened to remain associated with the same roles; this does not
establish stable numbering after other reconnection orders or reboot.

Receive-only 25-second captures, labelled unknown and analyzed after ignoring the
first second, gave:

- `captures/pi-swap-probe-0`: 257 Limitimer state frames with absent checksums,
  no cue frames; classified Limitimer without a new initialization command.
- `captures/pi-swap-probe-1`: 3,008 empty reports in the analyzed interval,
  no recognized payload; correctly classified unknown.

The second unit's expected role came from the owner's physical swap record, not
from the empty stream. One previously verified `8D 01` output was then sent only
to `/dev/hidraw1`, recorded in `captures/pi-swap-cue-init`. The write returned all
65 API bytes. That capture subsequently contained one Next and one Previous
message after settling, allowing PerfectCue-framed classification again. No
Limitimer initialization was sent. All three capture integrity checks passed.

The display workers were explicitly restarted after checking the assignments;
both sources are connected and receiving independently again. This is not an
automatic reconnect implementation. The trial confirms that traffic identification
alone cannot reliably choose the cue startup mode while its stream is empty.
Keep explicit roles for initialization and use protocol evidence to check them.
Windows and same-hub behavior remain separate, untested hardware cases.

## First run on a new machine

Ports do not need existing labels. The Windows launcher now guides one-at-a-time
pairing: disconnect DSAN USB devices, choose the intended role, connect that unit,
and bind the single newly appeared HID path. Repeat for the other unit. Pairing
uses connection changes and operator knowledge of the attached system; it does not
claim to query the hardware role. Startup initialization follows only after the
complete mapping validates. This avoids relying on serial strings or arbitrary
list ordering. The RequestID investigation was paused before sending that query;
no ID query or SetID command was used for this setup change.

## Live guided-pairing test with both devices already connected

The production `guided_configure` function was exercised on the Pi through
`tools/pi_pairing_test.py`, with a real Linux sysfs inventory callback. The Windows
HID driver was not involved. A staged copy kept the existing capture/display
installation untouched; the session records the exact launcher SHA-256, monotonic
prompt/answer events and inventories. Pi wall-clock skew remains irrelevant to
these monotonic step offsets.

Both units were present initially. The owner unplugged only Limitimer; the wizard
observed that device disappear while cue remained present. The running display
also showed Limitimer disconnected with frozen values, while cue reports continued
increasing. Reconnecting the same unit bound `/dev/hidraw0` as PRO-2000/Limitimer.
The owner then unplugged only PerfectCue; the paired Limitimer stayed present.
Reconnecting that unit bound `/dev/hidraw1` as Cue emulator/PerfectCue. The wizard
completed and validated both assignments with no output reports during pairing
and no replacement of the live configuration.

Evidence is preserved under `inventories/pi-guided-pairing/connected-session` and
on the Pi under `/home/pi/dsan-investigation/pairing-harness/connected-session`.
These Linux test paths are not Windows HID paths and must not be copied into a
Windows source configuration.

A separate startup check then used the wizard's assigned roles: one `8D 00`
output to the Limitimer path, one `8D 01` output to the cue path. Both writes
returned all 65 API bytes. Each capture contains 25,008 raw bytes and passed
integrity validation. After discarding the opening second, the timer capture
contained 252 complete state frames (absent checksums), and the cue capture
contained two events (Next and Previous), with no cross-protocol classifications.
Both live readers were restarted using the validated assignments and are receiving
independently again.

This validates the connected-at-launch pairing workflow with these Pi devices,
including the emulator cue path. It does not validate Windows enumeration, real
PerfectCue hardware, same-hub operation, or automatic reconnect. The automated
suite also covers multiple unexpected removals, removal of an already-paired
peer, duplicate paths and a changed path on reconnect.
