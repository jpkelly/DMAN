"""Synthetic transport-isolation tests; no claims about verified timer packets."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from dsan_capture.discovery import usb_descriptors
from dsan_capture.transport import UsbReceiver


class Device:
    idVendor = 0x0483
    idProduct = 0x101A
    bDeviceClass = 0
    bus = 1

    def __init__(self, address, chunks):
        self.address = address
        self.port_numbers = (1, address)
        self.chunks = iter(chunks)
        self.closed = False

    def __iter__(self):
        return iter(())

    def get_active_configuration(self):
        class Configuration:
            bConfigurationValue = 1
            def __getitem__(self, key):
                if key != (0, 0):
                    raise KeyError(key)
                return SimpleNamespace()
        return Configuration()

    def read(self, endpoint, length, timeout):
        if self.closed:
            raise OSError("Synthetic disconnected device")
        return next(self.chunks)


class MultipleReceiverTests(unittest.TestCase):
    def setUp(self):
        self.a = Device(4, [b"A-prefix", b"A-rest"])
        self.b = Device(5, [b"B-prefix", b"B-rest", b"B-alive"])
        self.devices = [self.a, self.b]
        self.find_calls = []

        def find(**selectors):
            self.find_calls.append(selectors)
            return [d for d in self.devices if all(getattr(d, key) == value for key, value in selectors.items() if key not in ("backend", "find_all"))]

        for name, replacement in (
            ("dsan_capture.discovery.usb_backend", lambda: object()),
            ("usb.core.find", find),
            ("usb.util.claim_interface", lambda *args: None),
            ("usb.util.release_interface", lambda device, interface: setattr(device, "closed", True)),
            ("usb.util.dispose_resources", lambda *args: None),
            ("usb.util.find_descriptor", lambda *args, **kwargs: SimpleNamespace(bmAttributes=3, wMaxPacketSize=8)),
        ):
            patcher = patch(name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_same_product_id_receivers_remain_separate(self):
        a = UsbReceiver(0x0483, 0x101A, 1, 4, 0, 0x81)
        b = UsbReceiver(0x0483, 0x101A, 1, 5, 0, 0x81)
        self.assertEqual((a.read(), b.read(), a.read(), b.read()),
                         (b"A-prefix", b"B-prefix", b"A-rest", b"B-rest"))
        a.close()
        self.assertTrue(self.a.closed)
        self.assertFalse(self.b.closed)
        self.assertEqual(b.read(), b"B-alive")
        b.close()
        self.assertEqual(a.info["port_numbers"], [1, 4])
        self.assertEqual(b.info["port_numbers"], [1, 5])
        self.assertTrue(all("address" in call and "bus" in call for call in self.find_calls))

    def test_missing_target_never_falls_back_to_peer(self):
        with self.assertRaisesRegex(ValueError, "Expected one matching"):
            UsbReceiver(0x0483, 0x101A, 1, 99, 0, 0x81)

    def test_unfiltered_discovery_still_lists_both_devices(self):
        descriptors = usb_descriptors(0x0483, 0x101A)
        self.assertEqual([d["address"] for d in descriptors], [4, 5])


if __name__ == "__main__":
    unittest.main()
