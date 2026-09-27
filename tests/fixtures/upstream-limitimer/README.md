# Upstream Limitimer capture excerpts

Unmodified byte ranges copied from the RS-485 captures in
[Depili/limitimer](https://gitlab.com/Depili/limitimer) at commit
`1cec6f97c27022905da7b05c6e4ae9837368596c`. Copyright 2021 Vesa-Pekka Palmu,
GPL-2.0-or-later; see [the license](../../../docs/licenses/depili-limitimer-LICENSE.txt).

These are **upstream wire captures from a different setup**: a Limitimer
controller read directly over RS-485 at 19200 8N1, not our PRO-2000 through a
VC-2000PC USB dongle. They verify framing and field positions against real
Limitimer traffic. They do not verify our dongle's stream.

| Excerpt | Source file | Offset | Length | Source SHA-256 |
| --- | --- | --- | --- | --- |
| `p2-17min-7min-sumup.bin` | `p2_17min_7min_sumup_2021-12-03 15-10-09.txt` | 176809 | 1210 | `d5838e958527b0032ad5e81bb3f518e7c8683573a4a05175de10facdc6d88589` |
| `count-up.bin` | `count_up_2021-12-04 12-55-48.txt` | 156099 | 1210 | `a0fbc362de33088d3502f1096dadff7f5a09c9bf88ac898ae1dd0e127f56ed02` |
| `listener-raw-lossy.bin` | `listener_raw_2022-03-11T111244.txt` | 0 | 1024 | `693c5650d35817302599b07e4f6e62781ef9e7abefe7464f627389e4fc74a813` |

Excerpt SHA-256: `8cd14319fc07e8784fd648680031965a12b9ecf309e839e4fa1b421498a41044`,
`77246d798e6f7946e513cf2b8663d8318a2cce73170eb98dfaab9222c7813917`,
`0464bdbf1a1e7ea799b06f3b3069844a0c9c001324c3164178fbe6921c824ca9`.

The first two start mid-frame (offset is the middle of the file plus 3) so
resynchronization is exercised. The labels come from the upstream file names.
`listener-raw-lossy.bin` comes from a capture with dropped bytes and zero
checksums; its truncated frames are real corruption, useful for rejection tests.
