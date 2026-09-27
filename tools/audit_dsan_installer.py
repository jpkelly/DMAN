"""Offline, non-executing audit of the two inspected DSAN Gammadyne installers.

Reads PE metadata and zlib payload blocks. Writes JSON only, never installs or
loads a vendor binary, and has no hardware or network access. This is a research
tool for these packages, not a general-purpose installer extractor.
"""
import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PE:
    def __init__(self, data):
        self.data = data
        if data[:2] != b"MZ":
            raise ValueError("Missing DOS signature")
        header = self.u32(60)
        if data[header:header + 4] != b"PE\0\0":
            raise ValueError("Missing PE signature")
        self.optional = header + 24
        if self.u16(self.optional) != 0x10B:
            raise ValueError("This audit supports PE32 only")
        self.base = self.u32(self.optional + 28)
        table = self.optional + self.u16(header + 20)
        self.sections = []
        for index in range(self.u16(header + 6)):
            offset = table + 40 * index
            name = data[offset:offset + 8].split(b"\0")[0].decode("ascii")
            virtual_size, rva, size, raw = struct.unpack_from("<IIII", data, offset + 8)
            if raw + size > len(data):
                raise ValueError("Section outside file")
            self.sections.append((name, rva, virtual_size, raw, size))

    def u16(self, offset):
        return struct.unpack_from("<H", self.data, offset)[0]

    def u32(self, offset):
        return struct.unpack_from("<I", self.data, offset)[0]

    def offset(self, rva):
        for _, start, _, raw, size in self.sections:
            if start <= rva < start + size:
                return raw + rva - start
        raise ValueError("RVA outside raw sections")

    def string(self, rva):
        offset = self.offset(rva)
        return self.data[offset:self.data.index(0, offset)].decode("ascii")

    def span(self):
        return self.data[:max(raw + size for _, _, _, raw, size in self.sections)]

    def imports(self):
        result = {}
        rva = self.u32(self.optional + 96 + 8)
        if not rva:
            return result
        offset = self.offset(rva)
        while True:
            lookup, _, _, name, address = struct.unpack_from("<IIIII", self.data, offset)
            if not name:
                break
            dll = self.string(name)
            values = []
            cursor = self.offset(lookup or address)
            index = 0
            while value := self.u32(cursor + 4 * index):
                symbol = f"ordinal:{value & 0xffff}" if value & 0x80000000 else self.string(value + 2)
                values.append({"name": symbol, "iat_va": hex(self.base + address + 4 * index)})
                index += 1
            result[dll] = values
            offset += 20
        return result

    def exports(self):
        rva = self.u32(self.optional + 96)
        if not rva:
            return {}
        offset = self.offset(rva)
        count = self.u32(offset + 24)
        functions = self.offset(self.u32(offset + 28))
        names = self.offset(self.u32(offset + 32))
        ordinals = self.offset(self.u32(offset + 36))
        return {self.string(self.u32(names + 4 * i)): hex(self.u32(functions + 4 * self.u16(ordinals + 2 * i))) for i in range(count)}


def payload(image):
    sections = [s for s in image.sections if s[0] == ".setup"]
    if len(sections) != 1:
        raise ValueError("Expected one Gammadyne .setup section")
    _, _, _, start, size = sections[0]
    end = start + size
    chunks, records = [], []
    # Each observed block has an 8-byte header, including its compressed length.
    # The other header word is preserved as unknown, not labelled a checksum.
    for match in re.finditer(b"\x78[\x01\x5e\x9c\xda]", image.data[start:end]):
        offset = start + match.start()
        if offset < start + 8:
            continue
        length = image.u32(offset - 8)
        if length < 8 or offset + length > end:
            continue
        try:
            decoder = zlib.decompressobj()
            block = decoder.decompress(image.data[offset:offset + length], 4194305)
        except zlib.error:
            continue
        if not decoder.eof or decoder.unused_data or not 256 < len(block) <= 4194304:
            continue
        if records and offset != records[-1]["offset"] + records[-1]["compressed_bytes"] + 8:
            raise ValueError("Non-contiguous payload blocks; unsupported installer")
        records.append({"offset": offset, "compressed_bytes": length,
                        "expanded_bytes": len(block), "header_unknown_u32": image.u32(offset - 4)})
        chunks.append(block)
        if sum(len(c) for c in chunks) > 128 * 1024 * 1024:
            raise ValueError("Payload exceeds research limit")
    if not chunks:
        raise ValueError("No validated zlib block sequence")
    return b"".join(chunks), records


def audit(path):
    data = path.read_bytes()
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Installer exceeds research limit")
    unpacked, blocks = payload(PE(data))
    offset, count, images, configs = 0, 0, [], []
    while offset < len(unpacked):
        length = struct.unpack_from("<I", unpacked, offset)[0]
        if length < 8 or offset + length + 4 > len(unpacked):
            raise ValueError("Invalid payload record boundary")
        record = unpacked[offset:offset + length]
        name_end = record.index(0, 4, min(len(record), 512))
        name = record[4:name_end].decode("ascii")
        if name.lower() == "usbif.dll" or (name.startswith("VideoClockFor") and name.endswith(".exe")):
            # Locate a complete PE inside this named record; retain no binaries.
            matches = []
            for match in re.finditer(b"MZ", record[:4096]):
                try:
                    pe = PE(record[match.start():])
                    matches.append((match.start(), pe))
                except (ValueError, struct.error, IndexError, UnicodeError):
                    continue
            if len(matches) != 1:
                raise ValueError(f"Expected one valid PE for {name}")
            position, pe = matches[0]
            imports = pe.imports()
            images.append({"name": name, "payload_offset": offset + position,
                           "pe_section_span_bytes": len(pe.span()),
                           "pe_section_span_sha256": sha(pe.span()), "image_base": hex(pe.base),
                           "usb_imports": imports.get("USBIF.dll", []),
                           "read_write_imports": [x for x in imports.get("KERNEL32.dll", []) if x["name"] in ("ReadFile", "WriteFile", "CreateFileA", "GetOverlappedResult")],
                           "exports": pe.exports()})
        if name == "Default.cfg":
            text = record.decode("ascii", errors="replace")
            configs.append({"name": name, "settings": re.findall(r"([^\r\n]+)//(?:Port A Device Type|COM Port Number|version)[^\r\n]*", text)})
        offset += length + 4  # Unknown trailer preserved by retaining the source.
        count += 1
    return {"source": str(path), "installer_bytes": len(data), "installer_sha256": sha(data),
            "method": "Static PE/zlib inspection only; no vendor code executed or loaded",
            "hash_scope": "Embedded hashes cover PE headers through last raw section, excluding overlays/installer metadata",
            "payload_blocks": blocks, "payload_record_count": count, "images": images,
            "configuration_hints": configs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = json.dumps(audit(args.installer), indent=2) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8") as file:
            file.write(result)
    else:
        print(result, end="")
