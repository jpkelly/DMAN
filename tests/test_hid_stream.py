"""HID envelope normalization. Real reports are copied verbatim from local captures;
other cases are synthetic and exercise the vendor-derived tag rules only."""
import unittest

from dsan_capture.hid_stream import OTHER, STATUS, STREAM, normalize_report

# Real 8-byte interrupt-IN reports (raw libusb, no report-ID slot).
REAL_STOPPED_0100 = bytes.fromhex("0781108300008100")         # captures/pro2000-p1-stopped-0100
REAL_AFTER_POWER_CYCLE = bytes.fromhex("078100216f070000")    # captures/pro2000-after-full-power-cycle-*
REAL_ACCESS_CHECK = bytes(8)                                  # captures/initial-access-check


class NormalizeReportTests(unittest.TestCase):
    def test_real_reports_carry_seven_stream_bytes(self):
        report = normalize_report(REAL_STOPPED_0100, report_id_slot=False)
        self.assertEqual(report, normalize_report(b"\0" + REAL_STOPPED_0100, report_id_slot=True))
        self.assertEqual((report.kind, report.payload, report.truncated), (STREAM, bytes.fromhex("81108300008100"), False))
        self.assertEqual(normalize_report(REAL_AFTER_POWER_CYCLE, report_id_slot=False).payload, bytes.fromhex("8100216f070000"))

    def test_zero_count_is_an_empty_stream_report(self):
        report = normalize_report(REAL_ACCESS_CHECK, report_id_slot=False)
        self.assertEqual((report.kind, report.payload, report.truncated), (STREAM, b"", False))

    def test_count_limits_payload_and_padding_is_ignored(self):
        report = normalize_report(bytes.fromhex("0281aa5555555555"), report_id_slot=False)
        self.assertEqual(report.payload, bytes.fromhex("81aa"))

    def test_count_beyond_received_bytes_is_marked_truncated(self):
        report = normalize_report(bytes.fromhex("0781"), report_id_slot=False)
        self.assertEqual((report.payload, report.declared, report.truncated), (b"\x81", 7, True))

    def test_extended_count(self):
        report = normalize_report(bytes.fromhex("7f03010203ffff"), report_id_slot=False)
        self.assertEqual((report.payload, report.truncated), (bytes.fromhex("010203"), False))
        self.assertTrue(normalize_report(b"\x7f", report_id_slot=False).truncated)

    def test_status_and_other_tags_stay_out_of_the_stream(self):
        self.assertEqual(normalize_report(bytes.fromhex("8001020304050607"), report_id_slot=False).kind, STATUS)
        other = normalize_report(bytes.fromhex("9001020304050607"), report_id_slot=False)
        self.assertEqual((other.kind, other.payload), (OTHER, bytes.fromhex("9001020304050607")))

    def test_layout_must_be_stated_and_report_nonempty(self):
        with self.assertRaises(TypeError):
            normalize_report(REAL_STOPPED_0100)
        with self.assertRaises(ValueError):
            normalize_report(b"\0", report_id_slot=True)


if __name__ == "__main__":
    unittest.main()
