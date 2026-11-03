#!/usr/bin/env python3
"""Offline DDS text experiment planner. No camera access or deployment output.

Reconstructs the firmware's fixed geometry, NOT a small independent overlay.
A text plan requires replacing the shared native font. Previews are simulations;
runtime evidence is recorded separately, not implied by successful rendering.
The small 5x7 patterns below are authored here; no Sony font is distributed.
"""
import argparse
import json
import struct
from pathlib import Path

from decode_osd import decode

PATTERNS = {
    " ": "00000/00000/00000/00000/00000/00000/00000",
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111",
    "G": "01110/10001/10000/10111/10001/10001/01110",
    "I": "11111/00100/00100/00100/00100/00100/11111",
    "L": "10000/10000/10000/10000/10000/10000/11111",
    "N": "10001/11001/11001/10101/10011/10011/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110",
    "P": "11110/10001/10001/11110/10000/10000/10000",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110",
    "Y": "10001/10001/01010/00100/00100/00100/00100",
    "0": "01110/10001/10011/10101/11001/10001/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111",
    "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010",
    "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110",
    "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110",
    "9": "01110/10001/10001/01111/00001/00001/01110",
    "%": "11001/11010/00010/00100/01000/01011/10011",
    "/": "00001/00010/00010/00100/01000/01000/10000",
    "-": "00000/00000/00000/11111/00000/00000/00000",
}


def compile_text(lines):
    """Two rows of eight characters, at most sixteen distinct glyphs total."""
    if len(lines) != 2 or any(not isinstance(s, str) or len(s) > 8 for s in lines):
        raise ValueError("Exactly two rows, at most eight characters each")
    text = "".join(s.ljust(8) for s in lines)
    alphabet = list(dict.fromkeys(" " + text))
    if len(alphabet) > 16:
        raise ValueError("Shared DDS font has only sixteen glyph slots")
    if any(c not in PATTERNS for c in alphabet):
        raise ValueError("Character missing from the experimental font")
    font = bytearray(128)
    for i, c in enumerate(alphabet):
        rows = PATTERNS[c].split("/")
        font[i * 8:(i + 1) * 8] = bytes([0] + [int(row, 2) << 2 for row in rows])
    indices = [alphabet.index(c) for c in text]
    payload = bytes((indices[i] << 4) | indices[i + 1] for i in range(0, 16, 2))
    return bytes(font), payload, alphabet


def compile_compact_upload():
    """Fixed 5x5 UPLOAD asset: 30px ink height under native y6 scaling.

    Keep the native 8x8 cells, character spacing and all transaction bounds.
    Two empty rows above and one below center the ink within the old cell.
    This reduces ink height, not the DDS surface or its background rectangle.
    """
    patterns = {
        "U": "10001/10001/10001/10001/01110",
        "P": "11110/10001/11110/10000/10000",
        "L": "10000/10000/10000/10000/11111",
        "O": "01110/10001/10001/10001/01110",
        "A": "01110/10001/11111/10001/10001",
        "D": "11110/10001/10001/10001/11110",
    }
    font, payload, alphabet = compile_text(["UPLOAD", ""])
    compact = bytearray(font)
    for c, pattern in patterns.items():
        i = alphabet.index(c)
        compact[i * 8:(i + 1) * 8] = bytes(
            [0, 0] + [int(row, 2) << 2 for row in pattern.split("/")] + [0])
    return bytes(compact), payload, alphabet


def render_slot_zero(font, payload, foreground=0xffff, glyph_background=0x000f,
                     blank=0, origin=(30, 250), clip_to_screen=False):
    """Return a synthetic raw OSD frame; fixed native nearest-neighbour x2/y6.

    Only slot zero is active. Other slots and the source gutters are blank.
    Background nibbles are numeric native values, not inferred alpha semantics.
    """
    if len(font) != 128 or len(payload) != 8:
        raise ValueError("Expected 128 font bytes and 8 payload bytes")
    x0, y0 = origin
    limit_x, limit_y = (639, 479) if clip_to_screen else (640 - 576, 480 - 192)
    if not (isinstance(x0, int) and isinstance(y0, int) and
            0 <= x0 <= limit_x and 0 <= y0 <= limit_y):
        raise ValueError("DDS rectangle outside fixed OSD")
    if any(not 0 <= c <= 0xffff for c in (foreground, glyph_background, blank)):
        raise ValueError("Expected 16-bit colours")
    pixels = [0] * (640 * 480)
    for y in range(min(192, 480 - y0)):
        sy = y // 6
        for x in range(min(576, 640 - x0)):
            sx, value = x // 2, blank
            if sx < 64 and sy < 16:
                char = (sy // 8) * 8 + sx // 8
                glyph = (payload[char // 2] >> (0 if char % 2 else 4)) & 15
                value = (foreground if font[glyph * 8 + sy % 8] & (128 >> (sx % 8))
                         else glyph_background)
            pixels[(y0 + y) * 640 + x0 + x] = value
    return struct.pack("<307200H", *pixels)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--line1", default="UPLOAD")
    p.add_argument("--line2", default="TEST")
    p.add_argument("--output", type=Path, required=True, help="New offline preview directory")
    args = p.parse_args()
    font, payload, alphabet = compile_text([args.line1, args.line2])
    args.output.mkdir(parents=False, exist_ok=False)
    (args.output / "preview.png").write_bytes(decode(render_slot_zero(font, payload), alpha=False))
    report = {
        "scope": "OFFLINE SIMULATION, NOT A CAMERA SCREENSHOT OR INSTALLABLE PAYLOAD",
        "lines": [args.line1, args.line2], "alphabet": alphabet,
        "font_hex": font.hex(), "slot_zero_payload_hex": payload.hex(),
        "rectangle": [30, 250, 576, 192], "native_code_changes": 0,
        "hypothetical_shared_ram_font_bytes": 128, "camera_writes_performed": 0,
        "runtime_text_verified": False, "small_overlay": False,
        "required_before_any_live_trial": [
            "verify exact firmware, glyph instructions and all native font bytes",
            "establish exclusive use or reject any concurrently active DDS slot",
            "arm independent font restoration before the first write, including partial-write recovery",
            "clear display and cancel timer, restore font and verify, then native redraw",
            "validate physical visibility, UI transitions and natural sleep separately",
        ],
    }
    (args.output / "plan.json").write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
