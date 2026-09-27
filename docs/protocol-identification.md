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
