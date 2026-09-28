# Browser device setup

The Windows launcher opens `/setup`. First run identifies dongles through the
same `guided_configure` routine as the console. Existing configurations are
validated and started in a background thread, with missing-device errors shown
on the setup page. A setup session is shared by browser clients; unique prompt
IDs reject duplicate or stale answers. State-changing requests require the
same Origin and recognized Host as the existing display controls.

The wizard does not infer a role from identical USB descriptors. Choose the role
matching the controller and internal dongle setting, then follow the physical
plug/unplug instructions. No device is opened during pairing. Review precedes
saving; saving re-enumerates the devices before replacing the configuration or
starting workers. Each selected worker sends its reviewed role initialization
once at startup. Existing device streams stop when assignments are applied.

The final check displays received data only. It does not count locally or claim
that a USB connection verifies the role. PerfectCue mapping remains verified
with the emulator and dongle only, not a real PerfectCue controller.

## Pi development test

The mixed-dongle preview task enables `--setup-pi pi@pi5start.local`. The Mac
serves `/setup` while enumeration reads the Pi's actual sysfs inventory through
SSH. No Mac USB enumeration is attempted. Deploy `tools/pi_inventory.py` and
`tools/pi_stream.py` to the remote tools directory before using this mode.

Assignments save to local `pi-sources.json` (ignored by Git). Saving starts one
SSH stream per selected HID node, with the explicit role initialization. This
development path tests browser pairing with real devices; it is not evidence
that the Windows USB driver path has been physically tested. Pi node bindings
must be checked after reconnect/reboot and can be re-paired with the wizard.

The local setup API tests use explicitly mocked device inventories and handles
to exercise pairing, cancellation, stale answers, changed devices, persistence,
and shutdown. No simulated readings are used in the operator UI.

## Real Pi browser pairing result

The browser wizard was exercised with both dongles initially connected. The
operator unplugged/reconnected Limitimer, then PerfectCue; each disappearance
was accepted only while its peer remained present. The naming and review pages
assigned PRO-2000 to `/dev/hidraw0` and Cue emulator to `/dev/hidraw1`. Save and
start persisted both bindings in local `pi-sources.json` and started the inputs.

During the following 23-second observation, the timer decoded 237 additional
state frames and reported Program 1 stopped at 12:00. The cue source recorded
six additional recognized events, including both Next and Previous. Both
sources remained connected without a reported error, and the setup and existing
video-output pages showed 12:00. These are received-device and UI observations;
comparison with the physical controller display remains an operator check.
State snapshots are retained locally in
`inventories/browser-setup-pi/post-save-state.jsonl` (not a raw USB capture).
This validates the Pi path, not Windows USB hardware or a real PerfectCue controller.
