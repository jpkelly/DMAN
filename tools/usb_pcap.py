"""Print a macOS USB packet capture (tcpdump -i XHCn, DLT_USB_DARWIN) for one device.

Header layout follows Wireshark's usb_darwin dissector. Offline only.
"""
import argparse
import struct

REQUEST = {0: "SUBMIT", 1: "COMPLETE"}
TYPE = {0: "CTRL", 1: "ISOC", 2: "BULK", 3: "INTR"}
STATUS = {0: "ok", 0xE00002D6: "timeout", 0xE0005000: "stall", 0xE00002EB: "aborted"}


def packets(path):
    with open(path, "rb") as f:
        magic = f.read(24)
        endian = "<" if magic[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        nano = magic[:4] in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
        linktype = struct.unpack(endian + "I", magic[20:24])[0]
        while True:
            head = f.read(16)
            if len(head) < 16:
                return
            sec, frac, incl, _ = struct.unpack(endian + "IIII", head)
            yield linktype, sec + frac / (1e9 if nano else 1e6), f.read(incl)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pcap")
    p.add_argument("--location", type=lambda v: int(v, 0), help="device_location, e.g. 0x00110000")
    args = p.parse_args()
    for linktype, ts, data in packets(args.pcap):
        if len(data) < 32:
            continue
        _, hlen, req, io_len, status, _, _, loc, _, addr, ep, etype = struct.unpack("<HBBIIIQIBBBB", data[:32])
        if args.location is not None and loc != args.location:
            continue
        body = data[32:]
        extra = data[32:hlen] if hlen > 32 else b""
        payload = data[hlen:] if hlen >= 32 else body
        stamp = f"{ts % 86400:012.6f}"
        text = f"{stamp} {REQUEST.get(req, req):8} {TYPE.get(etype, etype)} addr={addr} ep={ep:#04x} len={io_len} status={STATUS.get(status, hex(status))}"
        if extra:
            text += f" hdr+{extra.hex(' ')}"
        if payload:
            text += f" data={payload[:64].hex(' ')}"
        print(text)


if __name__ == "__main__":
    main()
