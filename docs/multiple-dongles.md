# Multiple dongles and independent displays

The owner requires concurrent dongles and reports that the existing Windows
software behaved erratically with more than one connected. This is a core
application requirement. A dongle/source and a timer program are different
identities: source A / program 1 must remain distinct from source B / program 1.

The owner reports internal DIP switches or jumpers select whether each dongle
serves Limitimer or PerfectCue. Store the operator-confirmed hardware role per
source. The common VID/PID, product name, and firmware-like serial string cannot
be assumed to identify that role. Exact jumper positions are not documented yet.

## Evidence about the vendor implementation

Additional static inspection of the USB library identified in the
[installer research](dongle-research.md) shows:

- One process-global current-device handle at RVA `B030`, read by connection
  checks and close/read/write operations.
- Process-global receive storage and cursors (including RVAs `DB08`, `EC10`,
  `EC14`) and one stored device path at RVA `EB0C`.
- The open-by-ID callback checks VID/PID and accepts a matching device
  (`1C00`–`1C2A`). The enumeration loop stores its callback result at `1861` and
  exits when that result is nonzero (`1787`–`178C`). Thus that path selects the
  first matching device rather than giving the caller separate device handles.
- The application selects the shared product ID `101A`, not a particular USB
  location or distinct device instance in the traced opening path.

This is a credible source-selection limitation when identical dongles coexist,
but it does not prove the mechanism behind the reported erratic display. These
globals are per process; separate application processes do not literally share
that memory. They can nevertheless select the same physical dongle using the
same first-match rule. Do not reuse this single-context DLL as our multi-source
transport architecture.

## Required behavior

1. Give each configured source its own application ID and operator label, such
   as “Stage left” or “Lectern”. Each display explicitly selects a source and
   a program within that source. Never merge programs by program number alone.
   Include a “follow active program” selection per Limitimer source once that
   field is verified. It follows that controller's selection, not the last active
   program received from any connected dongle.
2. Bind each live connection to an exact device instance: HID path/collection or
   USB bus/address/interface. VID/PID identifies a product, not an individual
   dongle. Do not pick the first result. Prevent duplicate opens of the same
   endpoint within the application.
   Match initialization and decoding to the confirmed role for that source.
   A PerfectCue-configured dongle must not feed the countdown decoder. Cue events
   are distinct from timer programs; a cue-display feature is outside the current
   timer-display scope unless requested separately.
3. Preserve topology/location and descriptor information as identity hints. The
   observed serial string is `Ver 0.17 10/03/14`; do not assume that it is unique
   or use it as the sole persistent key. USB addresses and HID paths may change
   on reconnect. Port topology can identify a socket, not necessarily the same
   physical dongle after devices are swapped.
4. Each source owns a transport handle, reader, report normalizer, streaming
   decoder, timer state, connection generation, freshness clock and raw journal.
   Interleaved reads from A and B must never share a packet assembly buffer.
   Bound queues independently and expose overruns; one stalled source must not
   block the other readers or silently lose their data.
5. Initialization applies only to the selected, still-current device handle,
   once per intended connection. Never broadcast a mode selection to every
   matching VID/PID or reinitialize all devices during discovery. The existing
   receive-only restriction still applies until a specific output test is
   authorized. The application's device-type selection does not substitute for
   the dongle's internal switch/jumper setting.
6. A disconnect or stale-data timeout affects only that source. Mark its last
   value stale and keep the other displays updating. Discard callbacks from an
   older connection generation. If reconnect identity is ambiguous, show the
   ambiguity and require rebinding rather than substituting another timer.
7. Replay maintains source labels and separate streams. A combined replay uses a
   common timebase while preserving original per-source timestamps and report
   boundaries. Synthetic multi-source tests must be labelled synthetic.

## Implemented foundation versus remaining work

Transport objects already own separate handles and require an explicit target.
USB descriptor inspection now accepts bus/address filters, and opening one USB
receiver inspects only that target instead of all dongles with the same VID/PID.
Descriptor metadata now includes `port_numbers` when available, otherwise null.
Discovery can still intentionally list all matching devices.

Three synthetic tests check interleaved reads from two same-product devices,
closing one without closing the other, refusal to substitute a peer when the
selected device is absent, and discovery of both devices. These test the current
transport foundation, not a completed multi-source application. All 23 current
tests and syntax checks pass. No multiple-dongle hardware test has been run.

The source registry, reconnect policy, concurrent capture manager, separate
decoders/state, multi-source replay and display assignments remain to be built.
The existing CLI records one explicit device per invocation; it is not yet a
multi-device UI or manager.

## Hardware acceptance test after single-source decoding works

Use two controllers with visibly different times and labels. Capture both
simultaneously; run/pause and switch programs on one while leaving the other
unchanged. Disconnect A and verify that only A becomes stale. Reconnect it,
reverse connection order, and move/swap ports to test ambiguous identity handling.
Repeat with both dongles reporting the same serial string, if applicable. Test
simultaneous initialization without cross-addressed writes, sustained input and
isolated error/overrun handling on macOS and Windows before claiming support.
If a PerfectCue-configured dongle is also connected, verify that its events never
change any countdown source. Test this as source/type isolation, not as an
assumption that all same-product dongles provide timer data.
