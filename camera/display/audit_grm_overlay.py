#!/usr/bin/env python3
"""Audit native GRM/DDS overlay evidence offline; never send camera messages."""
import argparse
import json
import struct
from pathlib import Path

from audit_ui_contract import IMAGES, Image
from audit_overlay_routes import expect


def audit(image):
    # These are ELF addresses for the exact 2.00 image, not runtime pointers.
    checks = {
        "receive_dispatch": (0x7DB12C, "088851f8042c984204d005f1080000f007ff"),
        "message_switch": (0x7DBF96,
            "40f203139d423cd006d8023b9d420bd0b5f5817f6ad11ee0"
            "b5f5827f47d04ff602739d4262d158e0"),
        "set_bounds_and_copy": (0x7DB6F8,
            "8a78cb78072a10d8072b10d818246243841880181034012516300431a5700822a38031f540e5"),
        "clear_flag": (0x7DB734, "8b78072b06d8182202fb030300201033987080bd"),
        "set_tail": (0x7DC030, "184b4946e05807f10407bd46bde8f04ffff758bb"),
        "clear_tail": (0x7DC05C, "0d4b4946e05807f10407bd46bde8f04ffff760bb"),
        "render_tail": (0x7DC070, "084be05807f10407bd46bde8f04ffff775bb"),
        "render_first_four_bytes": (0x7DB450, "042de9d1"),
        "render_remaining_four_bytes": (0x7DB48C, "082de9d1"),
        "bitmap_vslot_64_noop": (0x6B7764, "80b5002000af80bd"),
    }
    for address, encoded in checks.values():
        expect(image, address, bytes.fromhex(encoded))
    if image.u32(0x7DB16C) != 0x005C011D:
        raise ValueError("DDS receive queue changed")
    if image.u32(0x7DBE00) != 0x005C011D:
        raise ValueError("DDS refresh sender queue changed")
    state_slot = 0x7DBF6A + image.u32(0x7DC090) + image.u32(0x7DC094)
    glyph_slot = 0x7DB33C + image.u32(0x7DB388) + image.u32(0x7DB38C)
    if (state_slot, image.u32(state_slot)) != (0x13D8A90, 0x145AAE4):
        raise ValueError("DDS state relocation target changed")
    if (glyph_slot, image.u32(glyph_slot)) != (0x13D8C90, 0x13EB2E0):
        raise ValueError("DDS glyph relocation target changed")
    if 0x7DB030 + image.u32(0x7DB058) != 0x145AAC8:
        raise ValueError("DDS lifecycle singleton changed")
    slots = {"retain": (0x54, 0x6B6DE9), "release": (0x58, 0x6B76E9),
             "no_op": (0x64, 0x6B7765), "cpu_write_lock": (0x4C, 0x6B7439),
             "cpu_write_unlock": (0x50, 0x6B6E55)}
    for offset, target in slots.values():
        if image.u32(0x13B1F50 + offset) != target:
            raise ValueError("Bitmap vtable changed")
    palette = struct.unpack("<8H", image.read(0x1007A30, 16))
    return {
        "firmware": "ILCE-7C 2.00", "sha256": IMAGES["obj"][1],
        "scope": "offline instruction/data checks, not a callable or live-verified ABI",
        "camera_access": False, "runtime_verified": False,
        "checked_instructions": {k: hex(v[0]) for k, v in checks.items()},
        "bitmap": {
            "vtable_address_point": "0x13b1f50",
            "slots": {k: {"slot": hex(o), "thumb_target": hex(t)}
                      for k, (o, t) in slots.items()},
            "debug_overlay": "0x68d13c",
            "ownership": "retain/release guards object lifetime; these are not CPU write locks",
            "flush_limit": "slot +0x64 returns zero; it is not evidence of a cache flush",
            "independent_plane_proven": False,
        },
        "dds": {
            "receive_queue": "0x005c011d", "worker": "0x7db10c",
            "dispatcher": "0x7dbf4c", "state_elf_va": "0x145aae4",
            "lifecycle_elf_va": "0x145aac8",
            "lifecycle_offsets": {"timer_handle": "0xc", "first_message_pending": "0x10"},
            "messages": {
                "0x0103": "12-byte payload: u16 type, u8 slot, u8 palette, 8 data bytes; copies data",
                "0x0104": "slot at payload +2; clears override flag, not underlying registered data",
                "0xff02": "refresh through 0x7db76c -> 0x7db5a8 -> 0x7db518 -> 0x68d13c",
                "0x0101/0x0102": "register/unregister native data pointers; excluded from proposed probe",
                "0xff01": "native worker exit; excluded from proposed probe",
            },
            "bounds": "slot and palette must both be 0..7",
            "glyphs": "16 8x8 glyphs for hex digits; each data byte becomes two hex digits",
            "glyph_elf_va": "0x13eb2e0",
            "palette_words": [hex(v) for v in palette],
            "surface": "288x32 source bitmap; destination scales width x2, height x6",
            "clear_semantics": "all eight effective slots disabled plus previous-visible flag -> one blank render",
            "background": "blank pixel comes from BSS at 0x145aae0; initial zero, runtime value unverified",
            "lifecycle": "initial handled message can arm native timer; clear branch does not disarm it",
            "not_proven": [
                "external sender allocation/header and delivery contract",
                "currently unused slot and native registered-data state",
                "visible LCD target and blank-render restoration",
                "timer state before/after and natural sleep behavior",
                "arbitrary ASCII rendering (UPLOADING is not supported by hex renderer)",
            ],
        },
        "next": "Read native DDS runtime state, finish external sender/timer ABI, then a bounded numeric display trial; no preload reboot or raw pixel writer.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image = Image(args.research / IMAGES["obj"][0], IMAGES["obj"][1])
    try:
        result = audit(image)
    finally:
        image.stream.close()
    with args.output.open("x") as stream:
        args.output.chmod(0o600)
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print("Offline GRM/DDS audit:", args.output)


if __name__ == "__main__":
    main()
