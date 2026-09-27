"""Read OS inventories and USB descriptors without opening serial ports."""
import json
import platform
import plistlib
import subprocess
from pathlib import Path


def usb_backend():
    import usb.backend.libusb1
    backend = usb.backend.libusb1.get_backend()
    if backend is None and platform.system() == "Darwin":
        for path in ("/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib"):
            if Path(path).exists():
                backend = usb.backend.libusb1.get_backend(find_library=lambda _: path)
                if backend:
                    break
    if backend is None:
        raise RuntimeError("libusb is unavailable; native USB inventory still works. No driver was changed.")
    return backend


def serial_ports():
    from serial.tools import list_ports
    fields = ("device", "description", "hwid", "vid", "pid", "serial_number", "location", "manufacturer", "product", "interface")
    return [{key: getattr(p, key, None) for key in fields} for p in sorted(list_ports.comports())]


def hid_devices():
    import hid
    result = []
    for device in hid.enumerate():
        item = dict(device)
        path = item.pop("path")
        item["path_hex"] = path.hex()
        result.append(item)
    return sorted(result, key=lambda item: item["path_hex"])


def mac_usb():
    raw = subprocess.check_output(["ioreg", "-a", "-l", "-r", "-c", "IOUSBHostDevice"], timeout=20)
    result = []
    fields = ("IORegistryEntryName", "IOObjectClass", "idVendor", "idProduct", "USB Product Name", "USB Vendor Name", "USB Serial Number", "locationID", "bDeviceClass", "bDeviceSubClass", "bDeviceProtocol", "bInterfaceNumber", "bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol", "bAlternateSetting", "bNumEndpoints", "CFBundleIdentifier", "IOCalloutDevice")

    def walk(node):
        if "idVendor" in node and "idProduct" in node:
            result.append({k: node[k] for k in fields if k in node})
        for child in node.get("IORegistryEntryChildren", []):
            walk(child)

    for node in plistlib.loads(raw):
        walk(node)
    return result


def windows_usb():
    script = "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); Get-PnpDevice -PresentOnly -ErrorAction Stop | Where-Object { $_.InstanceId -like 'USB\\*' } | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 4 -Compress"
    raw = subprocess.check_output(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout=30)
    data = json.loads(raw.decode("utf-8-sig")) if raw.strip() else []
    return data if isinstance(data, list) else [data]


def linux_usb():
    fields = ("idVendor", "idProduct", "manufacturer", "product", "serial", "bDeviceClass", "bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol")
    result = []
    for path in sorted(Path("/sys/bus/usb/devices").glob("*")):
        item = {k: (path / k).read_text().strip() for k in fields if (path / k).is_file()}
        if item:
            result.append({"path": str(path), **item})
    return result


def inventory():
    from .session import utc_now
    result = {"schema": 1, "utc": utc_now(), "platform": platform.platform(), "architecture": platform.machine(), "errors": {}}
    native = {"Darwin": mac_usb, "Windows": windows_usb, "Linux": linux_usb}.get(platform.system())
    for name, fn in (("serial", serial_ports), ("hid", hid_devices), ("usb", native)):
        try:
            if fn is None:
                raise RuntimeError("Native USB inventory unavailable on this OS")
            result[name] = fn()
        except Exception as exc:
            result[name] = []
            result["errors"][name] = str(exc)
    return result


def difference(before, after):
    result = {}
    for kind in ("serial", "hid", "usb"):
        a = {json.dumps(x, sort_keys=True) for x in before.get(kind, [])}
        b = {json.dumps(x, sort_keys=True) for x in after.get(kind, [])}
        result[kind] = {"added": [json.loads(x) for x in sorted(b - a)], "removed": [json.loads(x) for x in sorted(a - b)]}
    result["inventory_errors"] = {"before": before.get("errors", {}), "after": after.get("errors", {})}
    return result


def usb_descriptors(vid, pid, *, bus=None, address=None):
    """Read descriptors only. Never set configuration, detach drivers, or claim interfaces."""
    import usb.core
    import usb.util
    result = []
    selectors = {"idVendor": vid, "idProduct": pid}
    if bus is not None:
        selectors["bus"] = bus
    if address is not None:
        selectors["address"] = address
    for dev in usb.core.find(find_all=True, backend=usb_backend(), **selectors):
        try:
            try:
                ports = getattr(dev, "port_numbers", None)
            except (NotImplementedError, usb.core.USBError):
                ports = None
            item = {"vid": dev.idVendor, "pid": dev.idProduct, "bus": dev.bus, "address": dev.address, "port_numbers": list(ports) if ports is not None else None, "device_class": dev.bDeviceClass, "configurations": []}
            for cfg in dev:
                interfaces = []
                for intf in cfg:
                    interfaces.append({"number": intf.bInterfaceNumber, "alternate": intf.bAlternateSetting, "class": intf.bInterfaceClass, "subclass": intf.bInterfaceSubClass, "protocol": intf.bInterfaceProtocol, "extra_descriptors_hex": bytes(intf.extra_descriptors).hex(), "endpoints": [{"address": ep.bEndpointAddress, "attributes": ep.bmAttributes, "max_packet_size": ep.wMaxPacketSize, "interval": ep.bInterval} for ep in intf]})
                item["configurations"].append({"value": cfg.bConfigurationValue, "interfaces": interfaces})
            result.append(item)
        finally:
            usb.util.dispose_resources(dev)
    return result
