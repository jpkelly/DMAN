"""USB descriptor tests; no invented DSAN timer packets or HID input reports."""
import unittest
from types import SimpleNamespace

from dsan_capture.hid_inspection import read_report_descriptor, report_descriptor_length

# Exact HID extra descriptor observed in this dongle's saved USB inventory.
OBSERVED_HID_EXTRA = bytes.fromhex("09 21 00 01 00 01 22 2f 00")


class DescriptorTests(unittest.TestCase):
    def test_observed_descriptor_advertises_47_bytes(self):
        self.assertEqual(report_descriptor_length(OBSERVED_HID_EXTRA), 47)

    def test_malformed_and_missing_tables_rejected(self):
        for data in (b"", b"\x00\x21", OBSERVED_HID_EXTRA[:-1],
                     bytes.fromhex("09 21 00 01 00 02 22 2f 00"),
                     bytes.fromhex("09 21 00 01 00 01 22 ff ff")):
            with self.subTest(data=data), self.assertRaises(ValueError):
                report_descriptor_length(data)

    def device(self, response=b"synthetic", error=None):
        class Configuration:
            bConfigurationValue = 1
            def __getitem__(self, key):
                if key != (0, 0):
                    raise KeyError(key)
                return SimpleNamespace(bInterfaceClass=3, extra_descriptors=OBSERVED_HID_EXTRA)
        class Device:
            calls = []
            def get_active_configuration(self):
                return Configuration()
            def ctrl_transfer(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                if error:
                    raise error
                return response
        return Device()

    def test_only_standard_in_request_and_short_bytes_preserved(self):
        device = self.device()
        result = read_report_descriptor(device, 0, 1000)
        self.assertEqual(device.calls, [((0x81, 6, 0x2200, 0, 47), {"timeout": 1000})])
        self.assertEqual(result["status"], "short-read")
        self.assertEqual(bytes.fromhex(result["report_descriptor_hex"]), b"synthetic")

    def test_failure_is_saved_without_fabricating_descriptor(self):
        result = read_report_descriptor(self.device(error=TimeoutError("synthetic timeout")), 0, 1000)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["report_descriptor_hex"])
        self.assertEqual(result["advertised_length"], 47)
        self.assertEqual(result["error_type"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
