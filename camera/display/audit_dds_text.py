#!/usr/bin/env python3
"""Audit fixed DDS text limits and compare a model with an existing numeric capture.

Offline only. Uses a personally extracted firmware; never patches a camera.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from audit_ui_contract import IMAGES, Image
from audit_overlay_routes import expect
from audit_grm_overlay import audit as audit_dds
from dds_text_plan import render_slot_zero
from decode_osd import unpack_capture


def arm_plt_symbol(image, address):
    a, b, c = struct.unpack("<III", image.read(address, 12))
    if (a & 0xfffff000, b & 0xfffff000, c & 0xfffff000) != (
            0xe28fc000, 0xe28cc000, 0xe5bcf000):
        raise ValueError("Unexpected ARM PLT instruction form")
    def immediate(word):
        value, rotate = word & 255, ((word >> 8) & 15) * 2
        return ((value >> rotate) | (value << (32 - rotate))) & 0xffffffff
    slot = address + 8 + immediate(a) + immediate(b) + (c & 4095)
    rel = image.relocations[slot]
    if rel["type"] != 22:
        raise ValueError("Expected jump-slot relocation")
    return rel["symbol"]


def audit(image):
    audit_dds(image)
    # Destination x/y come from the supplied two halfwords, but the scaling
    # is instruction-immediate x2/y6, not caller-controlled message fields.
    expect(image, 0x7db52e, bytes.fromhex(
        "2b880622f96820466d88bb808b88fd805b003b81cb8853433a1d7b81"))
    expect(image, 0x7db344, bytes.fromhex("03ebcb0313f805a0"))
    expect(image, 0x7db34c, bytes.fromhex("01360afa06f313f4807f"))
    expect(image, 0x7db4d8, bytes.fromhex(
        "7b6815f0010f0ebf03f51053a3f50c53703b01350c34082d7b60e4d1"))
    font_section = next(s for s in image.elf.iter_sections()
                        if s["sh_addr"] <= 0x13eb2e0 and
                        0x13eb2e0 + 128 <= s["sh_addr"] + s["sh_size"])
    if font_section.name != ".data" or font_section["sh_flags"] & 3 != 3:
        raise ValueError("Expected writable, allocated font data section")
    glyph_bg = 0x7db366 + image.u32(0x7db390)
    if glyph_bg != 0x13eb360 or image.read(glyph_bg, 2) != b"\x0f\x00":
        raise ValueError("Unexpected active-glyph background")
    for address in (0x68e7bc, 0x68e7c4, 0x68e7e4, 0x68e7f4, 0x68e7fc, 0x68e804):
        expect(image, address, bytes.fromhex("80b5002000af80bd"))
    # Native bitmap write locks and GPE completion wait use process-local
    # pthread objects. They are not standalone cross-process draw RPCs.
    mutex = arm_plt_symbol(image, 0x1090d8)
    condition = arm_plt_symbol(image, 0x10d034)
    if (mutex, condition) != ("pthread_mutex_lock", "pthread_cond_wait"):
        raise ValueError("Native synchronization identity changed")
    return {
        "firmware": "ILCE-7C 2.00", "native_sha256": IMAGES["obj"][1],
        "scope": "offline; no camera access or native writes",
        "font": {"elf_va": "0x13eb2e0", "bytes": 128, "glyphs": 16,
                 "glyph_size": [8, 8], "section": font_section.name,
                 "sha256": hashlib.sha256(image.read(0x13eb2e0, 128)).hexdigest(),
                 "shared": True, "text_replacement_runtime_verified": False},
        "geometry": {"source": [288, 32], "scale": [2, 6], "destination": [576, 192],
                     "slot_zero_characters": [8, 2], "scale_is_code_immediate": True},
        "glyph_background_u16": 15, "disabled_slot_blank_baseline_u16": 0,
        "native_text": "TextRM_createText/drawText depend on initialized native resources and handles; no external text RPC established",
        "native_blit": "GRM_gpermRectblit constructs heap commands containing local bitmap objects; completion uses pthread mutex/condition",
        "bitmap_lock": "0x6b7438 uses mutex at object+0x24 and condition at +0x40; raw proc writes bypass this protocol",
        "fbrm_yuv_api": "all six inspected exported functions are return-zero stubs",
        "next": "A RAM font experiment could prove letters, but would not reduce the shared destructive rectangle; requires independent restoration and concurrency handling first",
    }


def compare_capture(image, path):
    raw = unpack_capture(path.read_bytes())
    palette = struct.unpack("<8H", image.read(0x1007a30, 16))
    reference = render_slot_zero(image.read(0x13eb2e0, 128),
                                bytes.fromhex("a7c0000100000000"), palette[5])
    actual = struct.unpack("<307200H", raw)
    expected = struct.unpack("<307200H", reference)
    changed = sum(actual[y * 640 + x] != expected[y * 640 + x]
                  for y in range(250, 442) for x in range(30, 606))
    if changed:
        raise ValueError(f"Numeric reference capture mismatch: {changed} pixels")
    return {"path": str(path), "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "compared_pixels": 576 * 192, "mismatched_pixels": changed,
            "scope": "matches previous fixed numeric capture; does not validate custom letters on camera"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--numeric-capture", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    image = Image(args.research / IMAGES["obj"][0], IMAGES["obj"][1])
    try:
        report = audit(image)
        if args.numeric_capture:
            report["numeric_reference_validation"] = compare_capture(image, args.numeric_capture)
    finally:
        image.stream.close()
    with args.output.open("x") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
