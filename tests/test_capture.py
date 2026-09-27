"""Synthetic infrastructure tests. These bytes are NOT DSAN protocol fixtures."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dsan_capture.__main__ import main
from dsan_capture.discovery import difference
from dsan_capture.session import SessionWriter, annotate, replay, validate
from dsan_capture.transport import SerialReceiver, UsbReceiver


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "session"

    def session(self, chunks=None):
        chunks = chunks if chunks is not None else [bytes(range(256)), b"\x00\xff\x00"]
        writer = SessionWriter(self.path, {"label": "synthetic infrastructure test"})
        for index, chunk in enumerate(chunks):
            writer.receive(chunk, "2026-01-01T00:00:00+00:00", (index + 1) * 1_000_000_000)
        writer.close("test")
        return chunks

    def test_all_byte_values_and_read_boundaries_round_trip(self):
        chunks = self.session()
        self.assertEqual((self.path / "raw.bin").read_bytes(), b"".join(chunks))
        self.assertEqual([data for event, data in replay(self.path) if event["kind"] == "rx"], chunks)
        self.assertTrue(validate(self.path)["complete"])

    def test_corruption_detected_before_replay(self):
        self.session()
        with (self.path / "raw.bin").open("r+b") as raw:
            raw.write(b"\xff")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            next(replay(self.path))

    def test_truncation_detected(self):
        self.session()
        with (self.path / "raw.bin").open("r+b") as raw:
            raw.truncate(4)
        with self.assertRaisesRegex(ValueError, "Invalid raw range"):
            validate(self.path)

    def test_invalid_offset_detected(self):
        self.session()
        path = self.path / "events.jsonl"
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events[0]["offset"] = 1
        path.write_text("".join(json.dumps(e) + "\n" for e in events))
        with self.assertRaisesRegex(ValueError, "Invalid raw range"):
            validate(self.path)

    def test_interrupted_capture_preserves_unindexed_bytes(self):
        writer = SessionWriter(self.path, {})
        writer.receive(b"abc", "test", 1)
        writer.raw.write(b"orphan")
        writer.raw.close()
        writer.events.write('{"kind":')
        writer.events.close()
        report = validate(self.path)
        self.assertFalse(report["complete"])
        self.assertEqual(report["bytes"], 9)
        self.assertEqual(report["journaled_bytes"], 3)
        self.assertEqual(len(report["warnings"]), 3)
        self.assertEqual([data for _, data in replay(self.path)], [b"abc"])

    def test_empty_capture_valid(self):
        self.session([])
        self.assertEqual(validate(self.path)["bytes"], 0)

    def test_existing_session_never_overwritten(self):
        self.session()
        with self.assertRaises(FileExistsError):
            SessionWriter(self.path, {})

    def test_annotations_leave_acquisition_unchanged(self):
        self.session()
        before = {name: (self.path / name).read_bytes() for name in ("raw.bin", "events.jsonl", "metadata.json")}
        annotate(self.path, "Synthetic note", at=2)
        for name, data in before.items():
            self.assertEqual((self.path / name).read_bytes(), data)
        self.assertEqual(len(list((self.path / "annotations").glob("*.json"))), 1)

    def test_replay_timing_uses_absolute_deadlines(self):
        self.session([b"a", b"b"])
        now = [0.0]
        waits = []
        def sleep(delay):
            waits.append(delay)
            now[0] += delay
        list(replay(self.path, speed=2, sleep=sleep, clock=lambda: now[0]))
        self.assertEqual(waits, [0.5, 0.5])

    def test_transport_failure_keeps_received_data(self):
        class Receiver:
            info = {"synthetic": True}
            settings = {"transport": "test"}
            reads = 0
            closed = False
            def read(self):
                self.reads += 1
                if self.reads == 1:
                    return b"\x00\xff"
                raise OSError("Synthetic unplug")
            def close(self):
                self.closed = True
        receiver = Receiver()
        with patch("dsan_capture.transport.SerialReceiver", return_value=receiver), patch("dsan_capture.__main__.inventory", return_value={}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = main(["capture", "--out", str(self.path), "--label", "synthetic", "--timer-model", "synthetic", "--signal-path", "synthetic", "serial", "--port", "fake", "--baud", "1", "--data-bits", "8", "--parity", "N", "--stop-bits", "1"])
        self.assertEqual(status, 1)
        self.assertTrue(receiver.closed)
        self.assertEqual(validate(self.path)["bytes"], 2)
        events = [e for e, _ in replay(self.path)]
        self.assertEqual(events[-1]["reason"], "transport-or-recording-error")
        self.assertIn("Synthetic unplug", events[-2]["message"])

    def test_serial_does_not_write_and_sets_inactive_lines_before_open(self):
        class Device:
            def open(self):
                assert self.dtr is False and self.rts is False
            def close(self):
                pass
            def read(self, size):
                return b"\x00"
            in_waiting = 1
        device = Device()
        with patch("serial.Serial", return_value=device) as factory, patch("dsan_capture.discovery.serial_ports", return_value=[{"device": "fake"}]):
            receiver = SerialReceiver("fake", 19200, 8, "N", 1)
            self.assertEqual(receiver.read(), b"\x00")
            receiver.close()
        self.assertFalse(factory.call_args.kwargs["xonxoff"])
        self.assertFalse(factory.call_args.kwargs["rtscts"])

    def test_no_data_distinguished_from_open_failure(self):
        from unittest.mock import Mock
        receiver = Mock(info={"synthetic": True}, settings={"transport": "test"})
        receiver.read.side_effect = [b"", b"", KeyboardInterrupt()]
        output = io.StringIO()
        args = ["capture", "--out", str(self.path), "--label", "synthetic",
                "--timer-model", "synthetic", "--signal-path", "synthetic",
                "serial", "--port", "fake", "--baud", "1", "--data-bits", "8",
                "--parity", "N", "--stop-bits", "1"]
        with patch("dsan_capture.transport.SerialReceiver", return_value=receiver), patch("dsan_capture.__main__.inventory", return_value={}), contextlib.redirect_stdout(output):
            self.assertEqual(main(args), 0)
        end = list(replay(self.path))[-1][0]
        self.assertEqual(end["receive_summary"], {"interface_opened": True, "reads_with_data": 0, "empty_reads": 2})
        self.assertIn("no input bytes arrived", output.getvalue())

        failed_path = self.path.parent / "open-failure"
        args[args.index(str(self.path))] = str(failed_path)
        output = io.StringIO()
        with patch("dsan_capture.transport.SerialReceiver", side_effect=OSError("Synthetic open failure")), patch("dsan_capture.__main__.inventory", return_value={}), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)
        end = list(replay(failed_path))[-1][0]
        self.assertFalse(end["receive_summary"]["interface_opened"])
        self.assertNotIn("Interface opened", output.getvalue())

    def test_close_failure_not_reported_as_normal_completion(self):
        from unittest.mock import Mock
        receiver = Mock(info={}, settings={})
        receiver.read.side_effect = KeyboardInterrupt()
        receiver.close.side_effect = OSError("Synthetic close failure")
        with patch("dsan_capture.transport.SerialReceiver", return_value=receiver), patch("dsan_capture.__main__.inventory", return_value={}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = main(["capture", "--out", str(self.path), "--label", "synthetic", "--timer-model", "synthetic", "--signal-path", "synthetic", "serial", "--port", "fake", "--baud", "1", "--data-bits", "8", "--parity", "N", "--stop-bits", "1"])
        self.assertEqual(status, 1)
        self.assertEqual(list(replay(self.path))[-1][0]["reason"], "transport-close-error")

    def test_empty_receive_loop_records_liveness(self):
        from unittest.mock import Mock
        receiver = Mock(info={}, settings={})
        receiver.read.side_effect = [b"", KeyboardInterrupt()]
        with patch("dsan_capture.transport.SerialReceiver", return_value=receiver), patch("dsan_capture.__main__.inventory", return_value={}), patch("dsan_capture.__main__.time.monotonic", side_effect=[0.0, 0.0, 2.1, 2.1]), contextlib.redirect_stdout(io.StringIO()):
            status = main(["capture", "--out", str(self.path), "--label", "synthetic", "--timer-model", "synthetic", "--signal-path", "synthetic", "serial", "--port", "fake", "--baud", "1", "--data-bits", "8", "--parity", "N", "--stop-bits", "1"])
        self.assertEqual(status, 0)
        events = [event for event, _ in replay(self.path)]
        heartbeats = [event for event in events if event["kind"] == "receive-status"]
        self.assertEqual(len(heartbeats), 1)
        self.assertEqual(heartbeats[0]["empty_reads"], 1)
        self.assertEqual(heartbeats[0]["reads_with_data"], 0)
        self.assertTrue(heartbeats[0]["interface_opened"])
        self.assertEqual(events[-1]["reason"], "user-stop")

    def test_usb_out_endpoint_rejected_before_open(self):
        with self.assertRaisesRegex(ValueError, "Only USB IN"):
            UsbReceiver(1, 1, 1, 1, 0, 1)

    def test_diff_reports_added_removed_and_errors(self):
        before = {"serial": [{"device": "old"}], "errors": {"usb": "unavailable"}}
        after = {"serial": [{"device": "new"}]}
        diff = difference(before, after)
        self.assertEqual(diff["serial"]["added"], [{"device": "new"}])
        self.assertEqual(diff["serial"]["removed"], [{"device": "old"}])
        self.assertEqual(diff["inventory_errors"]["before"], before["errors"])


if __name__ == "__main__":
    unittest.main()
