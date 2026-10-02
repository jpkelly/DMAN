# Hardware and protocol evidence

Inspected 2026-09-26. No upstream implementation was copied or linked.

**Current finding:** the owner explicitly confirms this dongle works with a
Limitimer. [Offline analysis of the installers](dongle-research.md) now identifies
the actual HID library and a Limitimer-mode output (`8D 00`) that our passive
tests did not send. Both application variants use the observed `0483:101A` ID.
Treat older uncertainty about prior compatibility as superseded by that user
confirmation, while retaining the raw observations. No device write has been
implemented or sent, and successful initialization on this Mac is not yet tested.

## Source leads, not hardware verification

- [Depili/limitimer](https://gitlab.com/Depili/limitimer), inspected revision
  `1cec6f97c27022905da7b05c6e4ae9837368596c`:
  [README](https://gitlab.com/Depili/limitimer/-/blob/1cec6f97c27022905da7b05c6e4ae9837368596c/README.md),
  [decoder](https://gitlab.com/Depili/limitimer/-/blob/1cec6f97c27022905da7b05c6e4ae9837368596c/decode.go),
  [packet definitions](https://gitlab.com/Depili/limitimer/-/blob/1cec6f97c27022905da7b05c6e4ae9837368596c/packet.go).
  README specifies RS-485 19200/8N1, start `81`, 7-bit payload bytes, checksum
  marker `83`, two CRC bytes, and end `FF`. It reports 55-byte type `00` state
  and 6-byte type `10` messages. The purpose of `10` is speculative upstream.
  The source uses CRC16_MODBUS over start through checksum marker inclusive,
  and reads the transmitted CRC **high byte first**. It also accepts zero CRC;
  that exception must not become a default without evidence. Modbus polynomial
  does not mean Modbus RTU framing or usual Modbus checksum byte order.
  Upstream maps four programs, configuration, total/sum-up/elapsed time, and
  state bits, while retaining an explicitly unknown byte in each program block.
  Names/comments are not a substitute for observed field behavior.
- [Go package docs](https://pkg.go.dev/gitlab.com/Depili/limitimer) reflect the
  same reverse-engineering project, not independent hardware confirmation.
- [Clock-8001](https://gitlab.com/clock-8001/clock-8001), inspected master docs;
  repository API reported latest commit `ce5b8db13e0bea719615ac682e68682bc411f9bb`.
  [Limitimer notes](https://gitlab.com/clock-8001/clock-8001/-/blob/master/limitimer.md)
  require RS-485 and suitable wiring. Its
  [PerfectCue notes](https://gitlab.com/clock-8001/clock-8001/-/blob/master/perfectcue.md)
  describe short cue events (`0F`, `1F`, `2F`, `3F`) and electrical caveats.
  Cue-light/button events are not timer state packets. No cue commands were sent.
- [DSAN VideoClock](https://www.dsan.com/product/video-clock-for-limitimer/)
  currently describes SKU VC-2000-2, **two** RJ45 ports, Windows software and
  embedded storage. This differs from the user's VC-2000PC with one RJ45 port.
  The observed device descriptors also do not show a storage interface.
  Neither a shared name nor connector establishes model compatibility.
- Newly located [DSAN legacy software page](https://www.dsan.com/video-clock-software/)
  explicitly lists VC-2000-LT for Limitimer and VC-2000PC for PerfectCue. The
  ReadMe files in its official
  [PerfectCue v74 package](https://www.dsan.com/wp-content/uploads/2021/11/VideoClock_For_PerfectCue.zip)
  and [Limitimer v75 package](https://www.dsan.com/wp-content/uploads/2021/11/VideoClockForLimitimer.zip)
  say the older dongles are configured for a specific product and require the
  corresponding software. This is stronger evidence of model/configuration
  differences than the current two-port product page. It does not identify the
  configuration inside this particular unit or prove the cause of USB silence.
  The Limitimer ReadMe also says supplied configurations can show a network-fed
  timer by default, so recalling a countdown in the application alone would not
  prove local USB input. The user's recollection has not been reinterpreted as
  evidence of network use. Archives were inspected in memory; no installer was
  run and no vendor code was incorporated.

Limitimer RJ45 wiring documentation includes power as well as data. It is not
Ethernet. No rewiring, adapter substitutions, or electrical assumptions were made.
The TP-2000X ASCII protocol is a distinct interface and is not implemented here.

## Actual observations on this Mac

- User identified the timer controller as **PRO-2000** after the initial access
  check, then confirmed its RJ45 connects directly to the **VC-2000PC** RJ45.
  This establishes the user-reported physical path, not timer-data compatibility
  or the earlier report's timer state.
- User tentatively recalls this exact dongle previously displaying timer data in
  the Windows software ("i think it has displayed in the Win software previously").
  This is useful history, not a confirmed compatibility test; software version,
  prior wiring, and prior controller identity have not been independently checked.
- Later clarification: the user explicitly confirms the dongle has been tested
  successfully with a Limitimer. This is accepted as user-confirmed compatibility;
  it is distinct from protocol validation or a successful run of our Mac software.
- Further clarification: the owner reports the dongles can serve Limitimer or
  PerfectCue, selected by internal DIP switches or jumpers. Exact switch positions
  have not been inspected. Record the hardware role separately for each dongle;
  do not assume the application's startup output changes that physical setting.
- User currently has no Windows machine. A Windows comparison is unavailable;
  continue with Mac-side diagnosis without requiring that platform.
- User's Mac has no USB-A port and the only available USB-C adapter is Anker
  (exact model not provided). The observed path includes a USB hub. Bypassing
  that hub is not currently available; its brand does not establish causation.
- A fresh [connected baseline](../../inventories/direct-path-connected.json) after
  that clarification still shows `0483:101A`, interface class `03`, with no DSAN
  serial port or HIDAPI entry. Inventory collection reported no errors.
- After the user unplugged only USB, the
  [disconnected inventory](../../inventories/direct-path-disconnected.json) shows
  exactly the DSan `0483:101A` device and its HID-class interface removed.
  Serial and HIDAPI inventories are unchanged, with no collection errors.
  This ties the observed USB identity to the physical dongle.
- After USB reconnection, the same device and HID-class interface returned in
  the [reconnected inventory](../../inventories/direct-path-reconnected.json), with
  serial and HIDAPI inventories still unchanged and no collection errors.
  [Refreshed descriptors](../../inventories/direct-path-reconnected-descriptors.json)
  show bus 1, address 4, interface 0, interrupt-IN `81`, maximum packet 8 bytes.
  Disconnect/reconnect attribution is complete; timer-data compatibility remains
  unverified.
- macOS 15.6.1, arm64, Python 3.14.6.
- USB product: `VideoClock USB Interface by DSan`, vendor `DSan`, `0483:101A`.
- Serial string `Ver 0.17 10/03/14`; this is a descriptor string, not a proven
  unique serial number or independently verified firmware revision.
- Device class `00` (class specified per interface); configuration 1, interface 0,
  alternate 0, class `03` HID, subclass/protocol 0.
- Interrupt-IN `81`, max packet 8 bytes, interval descriptor 10.
- HID extra descriptor `09 21 00 01 00 01 22 2F 00` advertises a report descriptor
  length of 47 bytes. A standard IN GET_DESCRIPTOR request for those 47 bytes
  timed out after one second. The report descriptor itself remains unavailable;
  this timeout does not establish why HIDAPI enumeration lacks the device.
- No DSAN serial port; HIDAPI enumeration did not include this device. Reason is
  unresolved. No permissions or drivers were changed to force HIDAPI access.
- Existing libusb allowed claim/read/release of interface 0. A two-second check
  received exactly eight zero bytes in one read. There is no assigned meaning.
  USB descriptors and this report do not establish the RJ45-side protocol.
- Raw capture, journal, device/settings and unknown-state label saved to
  [initial access check](../../captures/initial-access-check). Hash validation and
  replay succeeded. Inventory stored in [initial snapshot](../../inventories/initial-connected.json)
  and [descriptors](../../inventories/initial-usb-descriptors.json).

## Labelled timer captures

- [Program 1 stopped at 1:00](../../captures/pro2000-p1-stopped-0100): user confirmed
  readiness in that requested state before a 10-second receive-only capture.
  Received one 8-byte report, `07 81 10 83 00 00 81 00`, at approximately
  0.019 seconds after session creation; no further bytes arrived during the
  capture. Indicator lights were not reported. SHA-256/length validation and
  offline replay passed. The label is a user-observed state, not a decoded state.
  Some bytes resemble upstream Limitimer markers, but there is no complete
  upstream-format frame here. The leading `07`, report layout, missing framing
  bytes, and reason for receiving only one report are unresolved. Preserve all
  eight bytes; do not infer a count prefix or strip any bytes yet.
- [Program 1 running from 1:00](../../captures/pro2000-p1-running-from-0100): user
  reported running before a 10-second capture. Exact displayed time at the start
  was not reported. The interface opened, but zero input bytes arrived; capture
  ended normally at the duration limit. Empty-file integrity and replay checks
  passed. A subsequent OS inventory still showed the DSan device/interface with
  no inventory errors. There is no running-state payload to decode or compare.
  Silence does not establish whether the cause is the dongle, timer signal,
  USB receive behavior, or another issue, and does not mean the timer stopped.
- [Displayed 0:00](../../captures/pro2000-p1-displayed-zero): user reported 0:00
  rather than confirming a paused state. A 10-second capture received no bytes;
  storage validation and replay passed. The user subsequently reported pressing
  Repeat and seeing 1:00. Its physical timing is unknown, so an annotation records
  that stable 0:00 throughout the capture is not confirmed. This is not a paused
  fixture or a recorded zero-crossing transition.
- [Repeat, displayed 1:00, longer USB timeout](../../captures/pro2000-p1-repeat-0100-timeout1000):
  after that report, a 10-second capture used a 1000 ms input timeout instead of
  100 ms. It again received zero bytes and ended at the duration limit. Integrity
  verification passed. Run/pause state was not confirmed. Changing this host read
  timeout sent no device configuration or protocol command. No conclusion about
  dongle compatibility or the cause of missing reports follows from silence.
- [USB receive diagnostic](../../captures/usb-receive-diagnostic): a further
  three-second receive-only check with 1000 ms reads and current timer state
  explicitly unconfirmed produced zero bytes. Storage verification passed.
  [libusb debug log](../../captures/usb-receive-diagnostic-libusb.log) shows successful
  interface-0 claim and three submitted interrupt reads ending in timeouts,
  rather than a claim/access failure. The installed PyUSB backend was inspected:
  it returns transferred bytes even on a timeout with partial data, so its
  timeout exception path is not simply discarding a reported partial transfer.
  This does not rule out loss or incompatibility elsewhere in the USB stack.

## Next steps, performed interactively one at a time

The HID-focused investigation found a new Mac-side lead: Ultraleap Hand Tracking
repeatedly attempts to open the DSAN device. Details, exact evidence, and the
descriptor-inspection command are in [HID investigation](hid-investigation.md).
The user authorized a temporary service-stop comparison. Ultraleap was unloaded.
After a full dongle power cycle, one 8-byte report arrived, followed by silence,
and the descriptor request still timed out. Ultraleap was verified unloaded
throughout the test; the result does not establish it as the cause. The scheduled
restoration fallback had not restored the service when checked. An explicit
restoration's administrator prompt was accidentally canceled. The owner explicitly
authorized retrying; restoration then succeeded and an independent service check
confirmed Ultraleap running again. This temporary-service comparison is complete.

A later full dongle power-cycle experiment (user asked to remove both USB and
RJ45, wait ten seconds, then reconnect) restored one input report. The
[post-cycle capture](../../captures/pro2000-after-full-power-cycle-2026-09-26T230243.633224_0000)
received `07 81 00 21 6F 07 00 00` in one read, then no further input during ten
seconds. Exact timer display/run state was unconfirmed. USB identity and endpoint
descriptors were unchanged; HIDAPI still did not enumerate the device. Integrity
and replay checks passed. One report after reconnect does not establish sustained
reception or compatibility. The report remains unparsed.

The first attempt to capture continuously across a Repeat press used a tool PTY.
On the user's reply, its process was gone and the journal contained only opening
and connected events, with no end record or received bytes. Preserve this
[incomplete attempt](../../captures/pro2000-repeat-during-open-capture) and its
annotations; it does not establish coverage of the physical action and is not a
valid no-data transition test. The exact reason for process termination is unknown.

The user then reported the timer had elapsed and that they were pressing Repeat
and Start. A new bounded two-minute recording was launched as a detached process
with file output, outside the tool PTY. Its receive loop now journals periodic
status records to document liveness during silent periods. The PID and log are
recorded locally. The process was confirmed alive and repeatedly reading after
launch. The Repeat/Start transition may precede opening; do not label it captured
without timing evidence. No application-generated device commands were sent.

That [detached recording](../../captures/pro2000-running-background-2026-09-26T230632.650203_0000)
completed normally after 120 seconds, with 120 empty reads, 60 periodic status
records, and zero received bytes. Integrity and offline replay checks passed.
The user reported 0:00 while the receive loop was demonstrably active; the
observation was annotated. They then reported restarting near completion, but
its physical timing relative to the end is not established. Neither restart
transitions nor zero-crossing timing are verified. Unlike the incomplete PTY
attempt, this recording establishes sustained attempted reception throughout its
documented window. Further timer button presses are not presently useful without
new evidence about the device interface or hardware path.

The direct PRO-2000 -> VC-2000PC path and USB disconnect/reconnect comparison are
recorded. Before the full-power-cycle experiment, only one 8-byte report was received across the labelled capture attempts;
the running, displayed-zero, and Repeat captures provided no input. Pause further
timer-state experiments while investigating the receive path. The user recalls
prior Windows success tentatively but has no Windows machine now. Newly located
legacy DSAN documentation distinguishes dongle configurations, so compatibility
cannot be inferred from that recollection. The only available USB-C adapter is
Anker, so a hub-bypass comparison is unavailable. Keep the existing connection;
there is no evidence to recommend a replacement. The next missing evidence is
whether this unit's configuration supports PRO-2000 data and how its USB input
is intended to be read. A [vendor compatibility brief](dsan-compatibility-brief.md)
collects the precise questions and observed results; it has not been sent. No
Windows test, device configuration command, firmware change, or driver change
has been performed. No vendor message has been sent.
Paused, zero-crossing, and program-switching fixtures remain outstanding. No
timer field or checksum is verified yet.

Only then determine whether USB report boundaries contain framing, counts,
report IDs, padding, timer bytes, or cue events. Preserve all unknown fields.
Promote labelled real captures to fixtures with provenance. Implement and test
streaming packet extraction across every split point, multiple packets per read,
corruption, length/checksum rejection, unknown types and resynchronization. Do
not strip HID bytes or apply Limitimer framing before that mapping is supported.

After decoding is verified, implement timer state separately from rendering,
including device versus local warning/overtime settings and explicit stale
state. Test disconnect and replay behavior before relying on the application at
an event. Windows and Intel macOS hardware/build testing remain outstanding.
