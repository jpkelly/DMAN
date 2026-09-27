"""Inspect a HID report descriptor using a standard USB IN request only."""
from .discovery import usb_backend
from .session import utc_now


def report_descriptor_length(extra):
    """Read the report-descriptor length advertised by a USB HID descriptor."""
    offset = 0
    lengths = []
    while offset < len(extra):
        if offset + 2 > len(extra) or extra[offset] < 2:
            raise ValueError("Malformed USB extra descriptor header")
        end = offset + extra[offset]
        if end > len(extra):
            raise ValueError("Truncated USB extra descriptor")
        descriptor = extra[offset:end]
        if descriptor[1] == 0x21:
            if len(descriptor) < 6 or len(descriptor) != 6 + 3 * descriptor[5]:
                raise ValueError("Malformed HID descriptor length table")
            for index in range(6, len(descriptor), 3):
                if descriptor[index] == 0x22:
                    lengths.append(int.from_bytes(descriptor[index + 1:index + 3], "little"))
        offset = end
    if len(lengths) != 1 or not 1 <= lengths[0] <= 4096:
        raise ValueError("Expected one advertised report descriptor of 1–4096 bytes")
    return lengths[0]


def read_report_descriptor(device, interface, timeout_ms):
    """No HID GET_REPORT/SET_REPORT, feature requests, or configuration writes."""
    if not 1 <= timeout_ms <= 5000:
        raise ValueError("Descriptor timeout must be between 1 and 5000 ms")
    result = {"utc": utc_now(), "status": "error", "interface": interface,
              "timeout_ms": timeout_ms, "request": None, "report_descriptor_hex": None}
    try:
        cfg = device.get_active_configuration()
        intf = cfg[(interface, 0)]
        if intf.bInterfaceClass != 3:
            raise ValueError("Selected interface does not declare HID class")
        extra = bytes(intf.extra_descriptors)
        length = report_descriptor_length(extra)
        result.update(configuration=cfg.bConfigurationValue,
                      hid_extra_descriptors_hex=extra.hex(), advertised_length=length,
                      request={"bmRequestType": 0x81, "bRequest": 6,
                               "wValue": 0x2200, "wIndex": interface, "wLength": length})
        # Standard GET_DESCRIPTOR, device-to-host, interface recipient.
        data = bytes(device.ctrl_transfer(0x81, 6, 0x2200, interface, length, timeout=timeout_ms))
        result.update(report_descriptor_hex=data.hex(), received_length=len(data),
                      status="ok" if len(data) == length else "short-read")
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    return result


def inspect_hid(vid, pid, bus, address, interface, timeout_ms=1000):
    import usb.core
    import usb.util
    devices = list(usb.core.find(find_all=True, idVendor=vid, idProduct=pid,
                                bus=bus, address=address, backend=usb_backend()))
    if len(devices) != 1:
        raise ValueError("Expected exactly one device; refresh USB descriptors first")
    device = devices[0]
    try:
        result = read_report_descriptor(device, interface, timeout_ms)
        return {"vid": vid, "pid": pid, "bus": bus, "address": address, **result}
    finally:
        # PyUSB may claim the interface for the standard IN request; release it.
        usb.util.dispose_resources(device)
