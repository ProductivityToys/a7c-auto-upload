#!/usr/bin/env python3
"""Decode a captured 640x480 OSD buffer using the candidate RGBA4444 layout.

Offline only. Never reads or writes a camera. Native format=1 is two bytes per
pixel; grayscale playback controls decode clearly with this nibble layout.
Colour order/alpha semantics still need an independently known colour sample.
"""
import argparse
from pathlib import Path
import struct
import zlib

WIDTH, HEIGHT = 640, 480


def unpack_capture(data):
    # Raw frames can begin with any pixel bytes, including the RLE magic.
    # Their fixed size exceeds the maximum accepted RLE size.
    if len(data) == WIDTH * HEIGHT * 2:
        return data
    if not data.startswith(b"A7R1"):
        raise ValueError("Invalid raw frame length")
    if len(data) < 12 or len(data) > 98304 or (len(data) - 8) % 4:
        raise ValueError("Invalid RLE length")
    expected, = struct.unpack_from("<I", data, 4)
    if expected != WIDTH * HEIGHT * 2:
        raise ValueError("Invalid RLE frame dimensions")
    raw = bytearray()
    for count, value in struct.iter_unpack("<HH", data[8:]):
        if not count or len(raw) + count * 2 > expected:
            raise ValueError("Invalid RLE run")
        raw.extend(struct.pack("<H", value) * count)
    if len(raw) != expected:
        raise ValueError("Truncated RLE frame")
    return bytes(raw)


def chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data +
            struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))


def decode(raw, alpha=True):
    if len(raw) != WIDTH * HEIGHT * 2:
        raise ValueError("Expected exactly 614400 bytes; no inferred dimensions")
    values = struct.unpack("<307200H", raw)
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)
        for value in values[y * WIDTH:(y + 1) * WIDTH]:
            rows.extend(((value >> 12) * 17, ((value >> 8) & 15) * 17,
                         ((value >> 4) & 15) * 17))
            if alpha:
                rows.append((value & 15) * 17)
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 6 if alpha else 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
            chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("raw", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--ignore-alpha", action="store_true",
                   help="Inspect RGB components without alpha; not a composited LCD screenshot")
    args = p.parse_args()
    png = decode(unpack_capture(args.raw.read_bytes()), alpha=not args.ignore_alpha)
    with args.output.open("xb") as f:
        f.write(png)
    print(args.output)


if __name__ == "__main__":
    main()
