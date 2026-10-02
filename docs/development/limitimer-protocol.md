# Limitimer stream protocol: reference analysis

Status 2026-09-27. Implementation: [hid_stream.py](../../dsan_capture/hid_stream.py)
(USB report → byte stream) and [limitimer.py](../../dsan_capture/limitimer.py)
(stream → frames → state). Both are original code. Tests:
[test_hid_stream.py](../../tests/test_hid_stream.py), [test_limitimer.py](../../tests/test_limitimer.py).

## Evidence levels

| Level | Meaning |
| --- | --- |
| **Wire-verified** | Holds across Depili/limitimer's RS-485 captures (real Limitimer, another setup) |
| **Upstream label** | Upstream's naming/interpretation; consistent with its labelled captures, not independently confirmed |
| **Dongle fragment** | Seen in our own VC-2000PC reports: three 7-byte fragments, no complete frame |
| **Unverified** | Not yet observed on our hardware |

Nothing below is verified end-to-end on the PRO-2000 → VC-2000PC → Mac path.

**Pi update:** the PRO-2000 → VC-2000PC → Pi HID path now delivers sustained
reports. In a user-labelled P1 stopped-at-1:00 capture, 110 consecutive state
frames decode to selected index 0, stopped, total 60 and elapsed 0, following
three older states at opening. The 52-byte state body and absent FF terminator
are observed across complete dongle frames. Checksum bytes are zero/absent; do
not describe them as CRC-valid. Running/paused/overtime/program-switch semantics
remain to be checked. See [Pi results](pi5-investigation.md) and the
[real fixture regression](../../tests/test_dongle_fixture.py).

## Sources

- [Depili/limitimer](https://gitlab.com/Depili/limitimer) at `1cec6f97`: Go
  decoder (`decode.go`), state parser (`packet.go`), and 29 raw RS-485 captures.
- [Clock-8001](https://gitlab.com/clock-8001/clock-8001) `v4/clock/limitimer.go`
  and `counter.go`: consumer of that library (program mapping, warning/expired
  display, active program as a fifth timer).
- [clock8002 limitimer.md](https://github.com/jpkelly/clock8002/blob/master/limitimer.md):
  wiring and usage notes only.
- The vendor host parser (see [dongle research](dongle-research.md)) looks for
  `81` and `83` and accepts length 52 or 55 at `83`, matching the 52-byte body below.

All upstream code is GPL-2.0-or-later. It was read, not copied; see
[third-party notes](../third-party.md).

## Layer 1: USB report → stream (vendor-derived)

Each 8-byte interrupt-IN report (no report-ID slot on raw libusb) carries a tag
byte then payload. Tag below `7F` = count of stream bytes that follow; `7F` = the
next byte is the count; `80` = status; above `80` = other messages. Status and
other reports are kept separate, not fed to the timer stream. Source: static
analysis of the vendor USB library. **Dongle fragment:** all three non-empty
reports start with `07` and their seven payload bytes fit Layer 2 exactly.

## Layer 2: stream → frames

```
81 | type | 7-bit body bytes ... | 83 | CRC-hi | CRC-lo | FF
```

- **Wire-verified:** CRC-16/MODBUS over `81` through `83` inclusive, high byte
  first. 851,164 checksum-valid frames across the upstream captures; zero mismatches.
- **Wire-verified:** body bytes have the high bit clear, so `81`/`83` are
  unambiguous in the body. Checksum bytes are full 8-bit and may be any value;
  the splitter always consumes exactly two after `83`.
- **Wire-verified:** two frame types: `00` state (52-byte body, 55 on the wire)
  and `10` sync (`81 10 83 cc cc FF`), strictly alternating in every non-lossy capture.
- **Wire-verified:** a zero checksum (`00 00`) occurs from some senders. In one
  upstream listener capture all frames have it, including frames truncated by
  dropped bytes. A zero checksum is reported as `absent`; exact length is then the
  only integrity check, and `decode_state` rejects any other length.
- **Dongle fragment:** `81 10 83 00 00 81 00` is a sync frame with zero checksum
  followed directly by `81` with **no `FF`**. Every upstream wire frame has `FF`.
  The dongle may strip it; not established. The splitter treats `FF` as optional
  and counts terminated/unterminated frames per source.

### Improvements over the upstream decoder

1. Upstream discards the byte after a missing `FF`. With the dongle fragment that
   byte is the next frame's `81`, so it would lose every following frame. Ours
   resynchronizes on it.
2. Upstream accepts a zero checksum as valid. Ours accepts but labels it
   `absent`, and requires exact state length.
3. Upstream's frames are slices of a reused buffer; ours are immutable values.
4. Discarded bytes are returned with a reason instead of only logged.
5. One splitter per source; no package-level decoder state.

## Layer 3: state frame fields

Offsets within the 52-byte body (`81` at 0, `83` at 51).

| Offset | Field | Level |
| --- | --- | --- |
| 1 | Type `00` | Wire-verified |
| 2 | Config high: `20` permit changes, `01` beep-type high bit | Upstream label |
| 3 | Config low: `08` count down, `04`/`02` programs/session in min:sec, `10` continue after zero, `20` loud, `40` beep-type low bit, `01` unknown | Upstream label; `08` matches the count-up capture |
| 4 | Sequence, cycles 0–9 | Wire-verified |
| 5 | Selected program index (0 = P1) | Wire-verified against labelled P2/P3 captures |
| 6 + 11n | Program n flags: `01` run, `02` blink, `04` beep, `08` seconds-adjust | Run wire-verified; others upstream label |
| 7 + 11n | Unknown; values 0–5 seen, mostly 0; preserved raw | — |
| 8 + 11n | Total, 3 × 7-bit big-endian, seconds | Wire-verified (17:00 and 19:00 labels) |
| 11 + 11n | Sum-up (warning threshold), seconds | Wire-verified (7:00, 11:00 labels) |
| 14 + 11n | Elapsed, seconds; advances 1/s while running | Wire-verified |
| 50 | Unknown trailer, `00` so far; preserved raw | — |

Program 4 is the Limitimer "session" program. Remaining = total − elapsed,
negative in overtime. Upstream's display rule: warning when remaining ≤ sum-up
and not expired; expired when remaining < 1.

Other observations: every upstream capture starts with one all-zero state frame.
Upstream's hours-mode display computes minutes as `t / 60` without `% 60`,
which is a bug. Treat hours mode as unverified until a capture covers it.

**Dongle fragments** (fields at offsets 1–6 only):

| Capture | Bytes | Reading |
| --- | --- | --- |
| after-full-power-cycle | `81 00 21 6F 07 00 00` | State; config `21 6F`; seq 7; P1 selected; P1 flags 0 (not running) |
| ultraleap-stopped-after-power-cycle | `81 00 21 6F 09 00 01` | Seq 9; P1 selected; P1 run bit set. The label says run state was unknown, so this is unconfirmed |

Config low `6F` differs from upstream's usual `5F` in bit `10` (continue after
zero off) and bit `20` (loud on). Plausible DIP-switch differences; unconfirmed.

## Acceptance checks for our first sustained capture

1. Layer 1: reports keep the `07` + 7 payload shape; note any `7F`/`80`/other tags.
2. Complete frames appear: sync and 52-byte state frames alternating; record
   whether checksums are valid or absent, and whether `FF` ever appears.
3. Sequence cycles 0–9; no discarded bytes in steady state.
4. Stopped at 1:00 on P1: selected 0, P1 total 60, elapsed 0, run bit clear.
5. Running: P1 elapsed rises 1/s; run bit set. Paused: elapsed holds, run clear.
6. Crossing zero: remaining goes ≤ 0; check blink and continue-after-zero bits.
7. Program change: selected index follows the controller; per-program values hold.
8. Compare config bytes with the controller's documented DIP switch settings.
