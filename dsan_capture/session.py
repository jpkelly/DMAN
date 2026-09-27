"""Append-only acquisition records. Raw bytes stay independent of future decoding."""
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, indent=2)
        file.write("\n")


class SessionWriter:
    def __init__(self, directory, metadata):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.origin_ns = time.monotonic_ns()
        self.offset = 0
        self.digest = hashlib.sha256()
        self.closed = False
        save_json(self.directory / "metadata.json", {**metadata, "schema": 1, "started_utc": utc_now(), "monotonic_origin_ns": self.origin_ns, "timestamp_semantics": "Host read completion, not wire/byte arrival time", "protocol_verified": False})
        self.raw = (self.directory / "raw.bin").open("xb", buffering=0)
        self.events = (self.directory / "events.jsonl").open("x", encoding="utf-8")

    def event(self, kind, *, utc=None, elapsed_ns=None, **fields):
        item = {"kind": kind, "utc": utc or utc_now(), "elapsed_ns": time.monotonic_ns() - self.origin_ns if elapsed_ns is None else elapsed_ns, **fields}
        self.events.write(json.dumps(item) + "\n")
        self.events.flush()
        os.fsync(self.events.fileno())
        return item

    def receive(self, data, utc, elapsed_ns):
        if not data:
            return None
        start = self.offset
        view = memoryview(data)
        while view:
            count = self.raw.write(view)
            if not count:
                raise OSError("Raw capture write made no progress")
            view = view[count:]
        os.fsync(self.raw.fileno())
        self.digest.update(data)
        self.offset += len(data)
        return self.event("rx", utc=utc, elapsed_ns=elapsed_ns, offset=start, length=len(data))

    def close(self, reason, *, receive_summary=None):
        if self.closed:
            return
        try:
            fields = {} if receive_summary is None else {"receive_summary": receive_summary}
            self.event("end", reason=reason, bytes=self.offset, sha256=self.digest.hexdigest(), **fields)
        finally:
            self.closed = True
            self.raw.close()
            self.events.close()


def annotate(directory, text, at=None):
    directory = Path(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    if metadata.get("schema") != 1:
        raise ValueError("Unknown capture schema")
    # Separate files avoid concurrent writers corrupting the acquisition journal.
    save_json(directory / "annotations" / (uuid.uuid4().hex + ".json"), {"kind": "annotation", "created_utc": utc_now(), "at_seconds": at, "text": text})


def validate(directory):
    """Verify offsets/hash before replay; unfinished sessions remain recoverable."""
    directory = Path(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    if metadata.get("schema") != 1:
        raise ValueError("Unknown capture schema")
    size = (directory / "raw.bin").stat().st_size
    offset = 0
    last_rx_ns = -1
    digest = hashlib.sha256()
    end = None
    warnings = []
    with (directory / "raw.bin").open("rb") as raw, (directory / "events.jsonl").open(encoding="utf-8") as events:
        for number, line in enumerate(events, 1):
            if not line.endswith("\n"):
                warnings.append(f"Incomplete final journal line {number}; ignored")
                break
            event = json.loads(line)
            if end is not None:
                raise ValueError("Journal contains records after end")
            if event["kind"] == "rx":
                length = event["length"]
                elapsed = event["elapsed_ns"]
                if type(length) is not int or length <= 0 or event["offset"] != offset or offset + length > size:
                    raise ValueError(f"Invalid raw range at journal line {number}")
                if type(elapsed) is not int or elapsed < 0 or elapsed < last_rx_ns:
                    raise ValueError("Non-monotonic receive timestamps")
                remaining = length
                while remaining:
                    block = raw.read(min(65536, remaining))
                    if not block:
                        raise ValueError("Raw capture changed during validation")
                    digest.update(block)
                    remaining -= len(block)
                offset += length
                last_rx_ns = elapsed
            elif event["kind"] == "end":
                end = event
    if end:
        if end["bytes"] != offset or offset != size or end["sha256"] != digest.hexdigest():
            raise ValueError("Capture length or SHA-256 mismatch")
    else:
        warnings.append("Unfinished capture; replay contains only fully journaled reads")
        if size != offset:
            warnings.append(f"{size - offset} trailing raw bytes have no timestamp; preserved in raw.bin")
    return {"bytes": size, "journaled_bytes": offset, "complete": end is not None, "warnings": warnings}


def replay(directory, speed=0, sleep=time.sleep, clock=time.monotonic):
    """Yield (event, bytes) with original read boundaries, without accessing hardware."""
    directory = Path(directory)
    validate(directory)
    origin = clock()
    with (directory / "raw.bin").open("rb") as raw, (directory / "events.jsonl").open(encoding="utf-8") as events:
        for line in events:
            if not line.endswith("\n"):
                break
            event = json.loads(line)
            if speed > 0:
                delay = event["elapsed_ns"] / 1e9 / speed - (clock() - origin)
                if delay > 0:
                    sleep(delay)
            data = b""
            if event["kind"] == "rx":
                raw.seek(event["offset"])
                data = raw.read(event["length"])
            yield event, data


def hex_lines(data, offset=0):
    for index in range(0, len(data), 16):
        row = data[index:index + 16]
        printable = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        yield f"{offset + index:08x}  {row.hex(' '):47}  |{printable}|"
