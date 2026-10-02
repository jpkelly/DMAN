# DSAN VC-2000PC / PRO-2000 compatibility inquiry

Prepared for the owner to review or send. No message has been sent to DSAN.

Subject: VC-2000PC with PRO-2000 — model compatibility and USB HID input

I am developing a receive-only timer display on macOS and need to confirm the
correct interface for an older VideoClock dongle before implementing decoding.

My hardware is a PRO-2000 controller connected directly by RJ45 to a single-RJ45
VC-2000PC dongle. Its USB connects to an Apple Silicon Mac through an Anker USB-C
adapter. macOS reports a USB hub on this path. I confirm this dongle has been
tested successfully with a Limitimer. I cannot currently reproduce a Windows
comparison because I have no Windows machine or alternate USB adapter available.
The dongles have internal DIP switches or jumpers that select Limitimer versus
PerfectCue purpose; the exact position mapping has not been documented in this
investigation.

Your [legacy software page](https://www.dsan.com/video-clock-software/) lists
VC-2000-LT for Limitimer and VC-2000PC for PerfectCue. The associated software
ReadMe files distinguish product-specific dongle configurations. I do not want
to assume the current VC-2000-2's capabilities apply to this older unit.

Could you clarify:

1. Offline analysis of the supplied applications finds the same USB library and
   PID `101A`, with `8D 00` sent through a HID output report for the Limitimer
   selection and `8D 01` for PerfectCue. What exactly do these modes change, are
   they volatile, how do they interact with the internal DIP switches/jumpers,
   and are there firmware-version-specific requirements?
2. Is the complete startup sequence and HID report descriptor available? The
   inspected Windows library requests nine-byte input buffers and writes
   65-byte output buffers including the report-ID slot. Are these the expected
   sizes for the USB identity below? Which bytes are framing versus payload?
3. Does this generation support macOS or have known USB descriptor/host
   compatibility issues? Is the advertised HID report descriptor length below
   expected for this unit?

Observed USB identity on macOS 15.6.1 / arm64:

- VID:PID `0483:101A`; product `VideoClock USB Interface by DSan`, vendor `DSan`.
- Serial-string descriptor `Ver 0.17 10/03/14` (not independently verified as a
  firmware version or unique serial number).
- Configuration 1, interface 0, alternate 0, HID class `03`, subclass/protocol 0.
- Interrupt-IN endpoint `0x81`, maximum packet 8 bytes, interval value 10.
- HID descriptor advertises a 47-byte report descriptor. One standard IN
  GET_DESCRIPTOR attempt for it timed out.

Unplugging and reconnecting USB removes/restores this device and interface.
No corresponding serial port appears, and HIDAPI does not enumerate it on this
Mac. libusb can claim interface 0 and submit interrupt reads.

Read-only capture results:

- An initial two-second access check received one eight-byte all-zero report.
- With program 1 reported stopped at 1:00, a ten-second capture received one
  report: `07 81 10 83 00 00 81 00`.
- Subsequent ten-second running, displayed-zero, and Repeat-to-1:00 captures
  received no bytes. Run/pause status was unconfirmed for the latter two.
- Host input timeouts of 100 and 1000 ms have been tried. A libusb diagnostic
  shows successful interface claim followed by interrupt-read timeouts.
- After a requested full power cycle with both USB and RJ45 disconnected, one
  ten-second capture received `07 81 00 21 6F 07 00 00`, then no further bytes.
  USB identity and endpoint descriptors were unchanged. The timer's exact state
  during that capture was unconfirmed.
- A later continuous two-minute recording completed normally with 120 empty
  reads and no input. Periodic journal entries confirm the receive loop remained
  active; the owner reported 0:00 during that window. Precise button/zero-crossing
  timing was not established. An earlier interactive recording ended unexpectedly
  and is excluded from conclusions about input around a button press.

The library's count-prefix handling is now understood from static analysis, but
no complete timer field, checksum, or packet framing is hardware-verified. Raw
bytes, host timestamps, connection settings and observations have
been preserved; integrity checks pass. No protocol writes, configuration changes,
driver replacements or firmware changes have been performed.

A later Mac log review found Ultraleap Hand Tracking repeatedly attempting to
open the DSAN device; logged attempts during our capture failed because Python
held exclusive access. This is an untested possible interaction, not an
established cause. With Ultraleap confirmed stopped and the dongle fully
power-cycled, one report (`07 81 00 21 6F 09 00 01`) arrived, then silence. The
report-descriptor request still timed out. This reproduces the earlier behavior
and does not establish Ultraleap as the cause. macOS also
logged a string-descriptor timeout during enumeration; the HID report descriptor
remains unavailable. See the [HID investigation](hid-investigation.md).

## Local evidence for follow-up

- [Detailed investigation and source references](investigation.md)
- [USB descriptors after reconnection](../../inventories/direct-path-reconnected-descriptors.json)
- [Stopped-at-1:00 capture](../../captures/pro2000-p1-stopped-0100)
- [USB diagnostic log](../../captures/usb-receive-diagnostic-libusb.log)

The local links are for the owner's use. Full inventories include other attached
devices; the relevant DSAN identity is summarized above so those inventories do
not need to be shared by default.
