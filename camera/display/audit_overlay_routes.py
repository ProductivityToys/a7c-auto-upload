#!/usr/bin/env python3
"""Offline evidence for temporary overlay routes; never executes camera code."""
import argparse
import json
import struct

from audit_ui_contract import IMAGES, Image, audit


def expect(image, address, expected):
    if image.read(address, len(expected)) != expected:
        raise ValueError(f"Instruction mismatch at {address:#x}")


def plt_target(image, address):
    """Resolve the verified Thumb veneer -> three-instruction ARM PLT form."""
    expect(image, address, bytes.fromhex("7847c046"))
    start = address + 4
    a, b, c = struct.unpack("<III", image.read(start, 12))
    if (a & 0xFFFFF000, b & 0xFFFFF000, c & 0xFFFFF000) != (
        0xE28FC000, 0xE28CC000, 0xE5BCF000
    ):
        raise ValueError("Unexpected ARM PLT form")

    def immediate(word):
        value, rotate = word & 255, ((word >> 8) & 15) * 2
        return ((value >> rotate) | (value << (32 - rotate))) & 0xFFFFFFFF

    slot = start + 8 + immediate(a) + immediate(b) + (c & 4095)
    relocation = image.relocations[slot]
    if relocation["type"] != 22:  # R_ARM_JUMP_SLOT
        raise ValueError("Expected symbolic PLT relocation")
    return {"veneer": hex(address), "got": hex(slot), **relocation}


def audit_routes(images):
    contract = audit(images)
    view = images["view"]
    resource = plt_target(view, 0x1826A0)
    timer = plt_target(view, 0x187728)
    if resource["symbol"] != "_ZN16CautionRsrcMgrIF11GetResourceEtt":
        raise ValueError("Unexpected resource getter")
    if timer["symbol"] != "_ZN8ViewBase13timerScheduleEP10TimerEventmj":
        raise ValueError("Unexpected timer target")
    # Fixed group 0x10; tail call to the resource lookup veneer above.
    expect(view, 0x21C8B8, bytes.fromhex("80b5102100afbde8804065f7edbe"))
    # Two PAS_LabelCustom objects receive descriptor resource IDs at slot 0x1b4.
    expect(view, 0x21EE1E, bytes.fromhex("3268d9f8003048461168d3f8b4319847"))
    expect(view, 0x21EE2E, bytes.fromhex("3268d8f8003040465168d3f8b4319847"))
    # timerCancel, descriptor halfword +0x14, nonzero *1000, timerSchedule.
    expect(view, 0x21EDD2, bytes.fromhex(
        "2046d4f8581169f7f4e8b38a002b34d02046d4f8581104224ff47a74"
        "634307f10c07bd46bde8f04f68f795bc"))
    # ViewFtpSettingTransfer helper calls getModelInfo(this, 0x12c, 2, ...).
    expect(view, 0x231184, bytes.fromhex("28464ff4967102223b46009457f79ae9"))
    return {
        "scope": "offline verified instruction/relocation facts; no usable overlay backend",
        "firmware": "ILCE-7C 2.00",
        "sha256": contract["sha256"],
        "caution": {
            "resource_getter": resource,
            "resource_group_helper": "0x21c8b8: fixed group 0x10",
            "display_helper": "0x21ecec",
            "label_calls": ["0x21ee1e", "0x21ee2e"],
            "label_slot": contract["candidate"]["forwarders"]["resource_text"],
            "direct_text_slot_not_used_by_these_calls":
                contract["candidate"]["forwarders"]["direct_text"],
            "timer": timer,
            "timer_units": "descriptor +0x14 halfword multiplied by 1000 when nonzero",
            "limit": "Proves resource-driven calls, not absence of all other text paths. "
                     "Timer scheduling alone does not prove safe close/restoration.",
        },
        "ftp_view": {
            "factory": "0x231126",
            "checked_helper": "0x23114a",
            "model": "0x12c",
            "property": 2,
            "limit": "This view consults the factory model. No arbitrary-text "
                     "external API or standalone progress overlay is established.",
        },
        "runtime_verified": False,
        "next_gate": "Establish a stable UI-thread entry and owned temporary widget; "
                     "prove expiry and layout teardown before uploader integration.",
    }


def main():
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    images = {}
    try:
        for name, (relative, digest) in IMAGES.items():
            images[name] = Image(args.research / relative, digest)
        result = audit_routes(images)
        with args.output.open("x") as stream:
            args.output.chmod(0o600)
            json.dump(result, stream, indent=2)
            stream.write("\n")
    finally:
        for image in images.values():
            image.stream.close()
    print(f"Offline overlay route audit: {args.output}")


if __name__ == "__main__":
    main()
