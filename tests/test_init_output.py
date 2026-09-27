"""Opt-in initialization output with a synthetic device; proves request shape,
ordering and opt-in behavior only, not how real hardware responds."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from dsan_capture.__main__ import main
from dsan_capture.init_output import limitimer_init_request


class FakeDevice:
    def __init__(self, log, fail=False):
        self.log = log
        self.fail = fail

    def ctrl_transfer(self, *args, timeout):
        self.log.append(("tx", args))
        if self.fail:
            raise OSError("Synthetic pipe error")
        return len(args[4])


class FakeReceiver:
    log = []
    fail = False

    def __init__(self, vid, pid, bus, address, interface, endpoint, timeout_ms=100):
        self.device = FakeDevice(self.log, self.fail)
        self.chunks = [bytes.fromhex("0781108300008100")]
        self.info = {"bus": bus, "address": address}
        self.settings = {"transport": "usb-interrupt", "bus": bus, "address": address}

    def read(self):
        self.log.append(("read",))
        time.sleep(0.01)
        return self.chunks.pop(0) if self.chunks else b""

    def close(self):
        self.log.append(("close",))


class InitOutputTests(unittest.TestCase):
    def setUp(self):
        FakeReceiver.log = []
        FakeReceiver.fail = False
        for name, replacement in (("dsan_capture.transport.UsbReceiver", FakeReceiver), ("dsan_capture.__main__.inventory", lambda: {})):
            patcher = patch(name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "session"

    def run_capture(self, *extra):
        argv = ["capture", "--out", str(self.out), "--label", "synthetic", "--timer-model", "synthetic", "--signal-path", "synthetic",
                "--seconds", "0.2", "--quiet", "usb-interrupt", "--vid", "0x0483", "--pid", "0x101a", "--bus", "0", "--address", "3",
                "--interface", "0", "--endpoint", "0x81", *extra]
        with patch("builtins.print"):
            self.assertEqual(main(argv), 0)
        events = [json.loads(line) for line in (self.out / "events.jsonl").read_text().splitlines()]
        return events, json.loads((self.out / "metadata.json").read_text())

    def test_exact_request(self):
        request = limitimer_init_request(0)
        self.assertEqual((request["bmRequestType"], request["bRequest"], request["wValue"], request["wIndex"]), (0x21, 0x09, 0x0200, 0))
        self.assertEqual(request["data"], b"\x8d\x00" + bytes(62))

    def test_default_capture_sends_nothing(self):
        events, metadata = self.run_capture()
        self.assertNotIn("tx", [entry[0] for entry in FakeReceiver.log])
        self.assertTrue(metadata["receive_only"])
        self.assertFalse([e for e in events if e["kind"].startswith("tx")])

    def test_opt_in_sends_once_after_reading_starts(self):
        events, metadata = self.run_capture("--send-limitimer-init", "--init-after", "0")
        kinds = [entry[0] for entry in FakeReceiver.log]
        self.assertEqual(kinds.count("tx"), 1)
        self.assertEqual(kinds[0], "read")
        tx = next(entry for entry in FakeReceiver.log if entry[0] == "tx")
        self.assertEqual(tx[1], (0x21, 0x09, 0x0200, 0, b"\x8d\x00" + bytes(62)))
        self.assertFalse(metadata["receive_only"])
        request = next(e for e in events if e["kind"] == "tx-request")
        self.assertEqual((request["target"], request["data_hex"]), ({"bus": 0, "address": 3, "interface": 0}, "8d00" + "00" * 62))
        self.assertEqual(next(e for e in events if e["kind"] == "tx-result")["written"], 64)
        self.assertEqual(events[-1]["kind"], "end")

    def test_failure_is_recorded_and_not_retried(self):
        FakeReceiver.fail = True
        events, _ = self.run_capture("--send-limitimer-init", "--init-after", "0")
        self.assertEqual([entry[0] for entry in FakeReceiver.log].count("tx"), 1)
        result = next(e for e in events if e["kind"] == "tx-result")
        self.assertIn("Synthetic pipe error", result["error"])
        self.assertEqual(events[-1]["reason"], "duration")


if __name__ == "__main__":
    unittest.main()
