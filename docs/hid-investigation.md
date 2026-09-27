# VC-2000PC HID investigation

**Later finding:** [offline installer research](dongle-research.md) recovered
the actual application/library code path. It confirms VID/PID selection, a mode
output (`8D 00` for the Limitimer path), Windows input/output buffer lengths and
count-prefixed stream handling. The owner explicitly confirms successful prior
Limitimer use with this dongle. Earlier uncertainties below are historical where
superseded; actual Mac startup and complete timer packets remain unverified.

## What is established

The physically identified DSAN USB device is `0483:101A`. Its sole observed
interface is HID class `03`, with interrupt-IN endpoint `81` and maximum packet
size 8 bytes. Those facts identify the USB transport class, not the HID report
layout or the correct application-level read procedure.

The USB HID extra descriptor is `09 21 00 01 00 01 22 2F 00`. Its descriptor table
advertises a 47-byte HID report descriptor. This is not evidence that input
reports are 47 bytes long. No report ID, count prefix, padding, timer packet
mapping or initialization sequence is currently verified.

## Standard descriptor-read probe

[hid_inspection.py](../dsan_capture/hid_inspection.py) implements a bounded,
targeted standard IN GET_DESCRIPTOR request. It validates the advertised length
table, confirms HID class, and saves the request, exact response bytes or error.
It does not issue GET_REPORT, SET_REPORT, feature/output reports, SET_IDLE,
configuration changes, or driver detachments. Any such later step would need a
justified scope and evidence; it is not silently attempted as a fallback.

The baseline [saved probe](../inventories/hid-report-before-ultraleap-comparison.json)
used `bmRequestType=81`, `bRequest=06`, `wValue=2200`, `wIndex=0`, `wLength=47`,
with a 1000 ms timeout. It timed out and returned no descriptor. Its JSON status
is `error`; the report-descriptor field is null, not invented data.

Four focused tests check the genuinely observed extra descriptor's length,
malformed tables, the IN-only request, preservation of short responses, and
failure recording. Synthetic response bytes test plumbing only. All 20 project
tests and the syntax check passed after adding the command.

## New Mac-side evidence

Read-only inspection of [kernel USB logs](../inventories/dsan-usb-kernel-investigation.log)
found repeated attempts by `libtrack_server` to open the DSAN device. The process
was identified as:

```
/Applications/Ultraleap Hand Tracking.app/Contents/bin/libtrack_server
```

It runs as root via `/Library/LaunchDaemons/com.ultraleap.tracking.service.plist`,
with label `com.ultraleap.tracking.service` and KeepAlive enabled. Ordinary process
termination may cause it to restart, so simply killing a PID would not establish
a controlled comparison. The subsequently authorized stop and restoration are
documented below.

The captured historical log contains 167 Ultraleap open failures during the
selected window, including attempts while the system composite driver or our
Python process had exclusive access. A fresh descriptor probe reproduced two
such attempts in [the recent log](../inventories/dsan-ultraleap-recent.log).

This proves another application is probing the same USB device. It does **not**
prove that it successfully claimed the device during capture or caused missing
data: the logged attempts are failures. Its behavior before capture opens is
not yet isolated. Avoid presenting this as a confirmed conflict.

Separately, macOS logged a standard **string descriptor** request (type `03`,
index 92, length 2) timing out during enumeration, and failure to enable remote
wake. The string-descriptor error is distinct from our report-descriptor request
(type `22`). These are evidence of enumeration problems; their causes and their
relationship to HIDAPI's missing entry remain unproven. The operating system's
configuration activity must not be attributed to our receive-only application.

## Vendor package inspection

The official PerfectCue and Limitimer ZIP packages were read in a scratch
directory. The supplied QuickStart guide was text-extracted and visually checked.
It reiterates matching the dongle's configured product and software, but does not
document HID reports or initialization. Static inspection identified the setup
program as a Gammadyne installer; no installer was executed, no application USB
procedure was recovered, and no proprietary code was added to this project.

Sources are linked in [the main investigation](investigation.md). The installer
metadata alone is not a reason to guess a HID request or packet format.

## Controlled comparison: Ultraleap stopped

The owner authorized temporarily stopping Ultraleap. macOS administrator
authorization succeeded; the service was unloaded with launchctl and verified
absent at 23:24:22 UTC. A root-owned background restoration check was scheduled
for five minutes later as a fallback. The service definition was not changed.

Before power-cycling the dongle, the
[new descriptor probe](../inventories/hid-report-ultraleap-stopped.json) still
timed out. HIDAPI's [inventory](../inventories/ultraleap-stopped.json) still lacked
the DSAN device. A [ten-second capture](../captures/ultraleap-stopped-no-power-cycle/)
opened successfully but returned ten empty reads and no bytes. Storage validation
passed. Ultraleap was verified unloaded before and after these tests. Stopping
the service alone did not restore reception; this does not exclude device state
left over from earlier enumeration.

The owner subsequently confirmed the full dongle power cycle. At 23:40:39 UTC,
Ultraleap was still unloaded: the scheduled restoration fallback had not restored
it by this check. Its failure mechanism has not been established.

The [fresh-enumeration capture](../captures/ultraleap-stopped-after-power-cycle/)
received one report, `07 81 00 21 6F 09 00 01`, then ten empty reads during its
ten-second window. Integrity and replay checks passed. Capture was performed
before the new descriptor request to avoid adding that request before acquisition.
The [HID descriptor request](../inventories/hid-report-ultraleap-stopped-after-power-cycle.json)
still timed out; HIDAPI still had no DSAN entry. Ultraleap was verified unloaded
both before and after the comparison. This reproduces the one-report-then-silence
pattern seen with Ultraleap running and does not establish it as the cause.

Explicit restoration via launchctl bootstrap was attempted immediately afterward.
macOS administrator authorization was canceled (`-128`), so that command did not
run. The [post-attempt service check](../inventories/ultraleap-restoration-status.json)
confirmed the service was still unloaded at that point. No permanent disable flag
or service-file edit was made. The owner then explained the cancellation was
accidental and explicitly authorized a retry. The retry succeeded;
[independent verification](../inventories/ultraleap-restored-verified.json) confirms
the service is loaded and running again (PID 64604 at verification). Restoration
is complete. The fallback failure remains unexplained; do not rely on that
background shell mechanism for future service restoration.

If the report descriptor becomes available, decode its item structure and derive
input report lengths/IDs before stripping any payload bytes. Only then determine
whether a different read method is needed. Preserve the existing raw captures.
