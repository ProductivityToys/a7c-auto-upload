#!/usr/bin/env python3
"""Read-only ILCE-7C 2.00 ELF audit. Does not connect to or execute camera code."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from elftools.elf.elffile import ELFFile


CUSTOM_TEST = "_ZN13AppWidgetBase20widgetUserTestCustomEPK9ParamList"
IMAGES = {
    "obj": (
        "evidence/camera-2.00-obj/usr__lib__libObj.so",
        "ac07a5dfb140381bf95813a76794d83437726231a740928e590be8d4ea5dfdbd",
    ),
    "view": (
        "evidence/camera-2.00-ui/usr__lib__viewUnified2.so",
        "1e524d4e97e6f0a1fc45e45dbbabec2f5d1a84d59d27e2d22e76f5fad73e2abe",
    ),
}


class Image:
    def __init__(self, path, expected):
        self.stream = path.open("rb")
        digest = hashlib.sha256()
        for chunk in iter(lambda: self.stream.read(1024 * 1024), b""):
            digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            self.stream.close()
            raise ValueError(f"Firmware hash mismatch: {path}")
        self.elf = ELFFile(self.stream)
        if self.elf.elfclass != 32 or self.elf["e_machine"] != "EM_ARM":
            raise ValueError("Expected ARM32 ELF")
        self.loads = [s for s in self.elf.iter_segments()
                      if s["p_type"] == "PT_LOAD"]
        self.symbols = {s.name: s for s in
                        self.elf.get_section_by_name(".dynsym").iter_symbols()}
        self.relocations = {}
        for section in self.elf.iter_sections():
            if section["sh_type"] != "SHT_REL":
                continue
            symbols = self.elf.get_section(section["sh_link"])
            for rel in section.iter_relocations():
                if rel["r_info_sym"]:
                    self.relocations[rel["r_offset"]] = {
                        "symbol": symbols.get_symbol(rel["r_info_sym"]).name,
                        "type": rel["r_info_type"],
                    }
        self.dynamic = {t.entry.d_tag: t.entry.d_val for t in
                        self.elf.get_section_by_name(".dynamic").iter_tags()
                        if t.entry.d_tag in ("DT_FLAGS", "DT_FLAGS_1", "DT_SYMBOLIC")}

    def read(self, address, size):
        seg = next(s for s in self.loads if
                   s["p_vaddr"] <= address and
                   address + size <= s["p_vaddr"] + s["p_filesz"])
        self.stream.seek(seg["p_offset"] + address - seg["p_vaddr"])
        return self.stream.read(size)

    def u32(self, address):
        return struct.unpack("<I", self.read(address, 4))[0]


def audit(images):
    obj, view = images["obj"], images["view"]
    # Thumb return-only body; this is not a proposal to patch these bytes.
    if obj.read(0x41F804, 6) != bytes.fromhex("80b500af80bd"):
        raise ValueError("Custom test is no longer the expected empty implementation")
    symbol = obj.symbols[CUSTOM_TEST]
    if (symbol["st_value"], symbol["st_info"]["bind"],
            symbol["st_other"]["visibility"]) != (
                0x41F805, "STB_GLOBAL", "STV_DEFAULT"):
        raise ValueError("Unexpected custom-test symbol binding")
    # PAS_LabelCustom constructor: PC-relative GOT -> vtable, then address point +8.
    vtable = view.u32(0x827CBE + view.u32(0x827D28) + view.u32(0x827D2C))
    if vtable != 0xB77C80:
        raise ValueError("Unexpected PAS_LabelCustom vtable")
    custom_relocation = view.relocations[vtable + 8 + 0xE4]
    if custom_relocation != {"symbol": CUSTOM_TEST, "type": 2}:
        raise ValueError("Expected symbolic R_ARM_ABS32 custom-test slot")
    # TestcmdManager switch uses event - 0x17002002, then a Thumb halfword table.
    event_base = (-obj.u32(0x3FFEFC)) & 0xFFFFFFFF
    event = 0x1700200B
    offset = struct.unpack("<H", obj.read(0x3FFD54 + 2 * (event - event_base), 2))[0]
    branch = 0x3FFD54 + 2 * offset
    if branch != 0x400228:
        raise ValueError("Unexpected widget-test switch branch")
    if obj.read(0x4002BA, 10) != bytes.fromhex("03682146d3f8e0309847"):
        raise ValueError("Expected virtual ParamList test call at slot 0xe0")
    forwards = {}
    for name, slot, expected in (
        ("resource_text", 0x1B4, 0x827BFF),
        ("direct_text", 0x1B0, 0x827C0F),
    ):
        target = view.u32(vtable + 8 + slot)
        if target != expected:
            raise ValueError(f"Unexpected {name} forwarder")
        forwards[name] = {"virtual_slot": hex(slot), "thumb_function": hex(target)}
    return {
        "scope": "offline ELF facts only; not a live hook or installation preflight",
        "firmware": "ILCE-7C 2.00",
        "sha256": {k: v[1] for k, v in IMAGES.items()},
        "widget_test": {
            "event": hex(event), "branch": hex(branch),
            "required_integer_parameters": [1, 2, 3, 4],
            "lookup_arguments": {"1": "group", "2": "layout", "3": "widget"},
            "parameter_4": "required and logged; not used as lookup argument",
            "virtual_slot": "0xe0",
            "custom_slot": "0xe4",
            "child_traversal": "0x41fd22; same ParamList also reaches child widgets",
        },
        "candidate": {
            "group": "0x1a3db4a3", "layout": "0xd90a4744", "widget": "0x53034e72",
            "type": "PAS_LabelCustom", "vtable": hex(vtable),
            "embedded_GEN_Label": "0x1d8",
            "custom_test_relocation": custom_relocation,
            "forwarders": forwards,
        },
        "linking": {
            "symbol": CUSTOM_TEST, "definition": "GLOBAL DEFAULT, empty",
            "image_dynamic_flags": {k: v.dynamic for k, v in images.items()},
            "observed_view_dlopen_flags": "0x101 at libObj 0x89d944 (no DEEPBIND bit)",
            "conclusion": "symbol interposition candidate, not runtime-proven",
        },
        "restoration": {
            "getText": "returns RecordPtr resource ID, or 0xffffffff; not char*",
            "setTextDirect": "resets old RecordPtr before requesting new text resource",
            "visibility": "getDispState and getSelfDispState are separate states",
            "prohibited_assumption": "a saved numeric resource ID alone guarantees restoration",
        },
        "unresolved": [
            "Prove selected test callback executes on the intended UI thread.",
            "Load observer into im.elf without affecting other processes or existing launchers.",
            "Validate exact target type and current runtime ID; parent and child both receive tests.",
            "Determine text resource ownership and layout teardown behavior before any mutation.",
            "Implement local expiry and cleanup independent of NAS/Wi-Fi; no wake polling.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    images = {}
    try:
        for name, (relative, digest) in IMAGES.items():
            images[name] = Image(args.research / relative, digest)
        result = audit(images)
        # Never replace existing evidence.
        with args.output.open("x") as out:
            args.output.chmod(0o600)
            json.dump(result, out, indent=2)
            out.write("\n")
    finally:
        for image in images.values():
            image.stream.close()
    print(f"Offline contract verified: {args.output}")


if __name__ == "__main__":
    main()
