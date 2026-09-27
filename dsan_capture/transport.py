"""Receive-only application APIs. No writes, feature reports, or device commands."""
import platform


class SerialReceiver:
    def __init__(self, port, baud, data_bits, parity, stop_bits):
        import serial
        from .discovery import serial_ports
        matches = [p for p in serial_ports() if p["device"] == port]
        if len(matches) != 1:
            raise ValueError("Choose an exact, currently enumerated serial port; URLs are not supported")
        self.info = matches[0]
        self.settings = {"transport": "serial", "port": port, "baud": baud, "data_bits": data_bits, "parity": parity, "stop_bits": stop_bits, "timeout_seconds": 0.1, "xonxoff": False, "rtscts": False, "dsrdtr": False, "rts": False, "dtr": False}
        self.device = serial.Serial(port=None, baudrate=baud, bytesize=data_bits, parity=parity, stopbits=stop_bits, timeout=0.1, xonxoff=False, rtscts=False, dsrdtr=False)
        # Set inactive BEFORE opening. Some drivers can still briefly toggle lines.
        self.device.dtr = False
        self.device.rts = False
        if platform.system() != "Windows":
            self.device.exclusive = True
        self.device.port = port
        try:
            self.device.open()
        except BaseException:
            self.device.close()
            raise

    def read(self):
        return self.device.read(max(1, min(self.device.in_waiting, 4096)))

    def close(self):
        self.device.close()


class HidReceiver:
    def __init__(self, path_hex, read_size):
        import hid
        from .discovery import hid_devices
        matches = [d for d in hid_devices() if d["path_hex"] == path_hex]
        if len(matches) != 1:
            raise ValueError("HID path is not currently enumerated; inspect USB descriptors instead")
        self.info = matches[0]
        self.settings = {"transport": "hid", "path_hex": path_hex, "read_size": read_size, "timeout_ms": 100, "report_bytes": "Unmodified HIDAPI input bytes; report ID retained if returned by API"}
        self.device = hid.device()
        try:
            self.device.open_path(bytes.fromhex(path_hex))
        except BaseException:
            self.device.close()
            raise

    def read(self):
        return bytes(self.device.read(self.settings["read_size"], timeout_ms=100))

    def close(self):
        self.device.close()


class UsbReceiver:
    def __init__(self, vid, pid, bus, address, interface, endpoint, timeout_ms=100):
        import usb.core
        import usb.util
        from .discovery import usb_backend, usb_descriptors
        if not endpoint & 0x80:
            raise ValueError("Only USB IN endpoints are allowed")
        if not 1 <= timeout_ms <= 5000:
            raise ValueError("USB read timeout must be between 1 and 5000 ms")
        matches = list(usb.core.find(find_all=True, idVendor=vid, idProduct=pid, bus=bus, address=address, backend=usb_backend()))
        if len(matches) != 1:
            raise ValueError("Expected one matching USB device; inspect again for bus/address")
        self.device = matches[0]
        self.interface = interface
        self.claimed = False
        try:
            # Inspect only the selected dongle, even when several share VID/PID.
            descriptors = usb_descriptors(vid, pid, bus=bus, address=address)
            self.info = next(d for d in descriptors if d["bus"] == bus and d["address"] == address)
            # Read current configuration only; no set_configuration or alt-setting changes.
            cfg = self.device.get_active_configuration()
            intf = cfg[(interface, 0)]
            ep = usb.util.find_descriptor(intf, bEndpointAddress=endpoint)
            if ep is None or ep.bmAttributes & 3 != 3:
                raise ValueError("Selected endpoint is not interrupt IN on alternate setting 0")
            self.settings = {"transport": "usb-interrupt", "vid": vid, "pid": pid, "bus": bus, "address": address, "configuration": cfg.bConfigurationValue, "interface": interface, "alternate": 0, "endpoint": endpoint, "read_size": ep.wMaxPacketSize, "timeout_ms": timeout_ms}
            # Never detach a kernel driver. Busy/access errors require investigation.
            usb.util.claim_interface(self.device, interface)
            self.claimed = True
        except BaseException:
            usb.util.dispose_resources(self.device)
            raise

    def read(self):
        import usb.core
        try:
            return bytes(self.device.read(self.settings["endpoint"], self.settings["read_size"], timeout=self.settings["timeout_ms"]))
        except usb.core.USBTimeoutError:
            return b""

    def close(self):
        import usb.util
        try:
            if self.claimed:
                usb.util.release_interface(self.device, self.interface)
        finally:
            usb.util.dispose_resources(self.device)
