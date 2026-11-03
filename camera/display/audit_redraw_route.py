#!/usr/bin/env python3
"""Offline evidence for the exact 2.00 native redraw countdown. No camera I/O."""
import argparse
import json
from pathlib import Path

from audit_ui_contract import IMAGES, Image
from audit_overlay_routes import expect


def audit(image):
    expect(image, 0x674A94, bytes.fromhex("044b80b57b4400af1878003818bf0120"))
    expect(image, 0x674AAC, bytes.fromhex("044b80b57b4400af1a780ab1013a1a70"))
    expect(image, 0x66DC60, bytes.fromhex("044b80b57b441b6800af186900b18047"))
    if 0x674A9C + image.u32(0x674AA8) != 0x14539B4:
        raise ValueError("Redraw getter target changed")
    if 0x674AB4 + image.u32(0x674AC0) != 0x14539B4:
        raise ValueError("Redraw decrement target changed")
    if 0x66DC68 + image.u32(0x66DC74) != 0x1453914:
        raise ValueError("Draw callback pointer changed")
    if image.symbols["pViewManager"]["st_value"] != 0x1488FDC:
        raise ValueError("View manager global changed")
    for address, symbol in (
        (0x13ADE64, "_ZN2ux6wgtsys5Layer9setActiveEb"),
        (0x13ADE6C, "_ZN2ux6wgtsys5Layer8setClearEb"),
    ):
        if image.relocations.get(address) != {"symbol": symbol, "type": 2}:
            raise ValueError("Layer operation relocation changed")
    return {
        "firmware": "ILCE-7C 2.00", "sha256": IMAGES["obj"][1],
        "scope": "offline instruction/relocation audit; runtime evidence remains separate",
        "camera_access": False,
        "counter_elf_va": "0x14539b4", "counter_bytes": 1,
        "counter_getter": "0x674a94", "counter_decrement": "0x674aac",
        "callback_pointer_global": "0x1453914",
        "runtime_verified_callback_table": "0x14539d8",
        "request_value": 2,
        "native_initialization": "0x6750e8 sets the same countdown to 2 on successful initialization",
        "native_frame_path": "0x89f4ec -> 0x61f140; nonzero countdown requests whole-scene dirty region, then decrements",
        "wakeup": "one existing read-only layout-list test event; not layer activation changes",
        "rejected_shortcut": "0x89f424 invokes Layer::setActive on every layer; not a pure redraw operation",
        "limitations": ["internal firmware-specific RAM ABI", "UI-thread scheduling and concurrent native invalidation still apply",
                       "counter consumption alone does not prove LCD visibility or restored pixels",
                       "no public redraw RPC or independent composition plane established"],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    image = Image(args.research / IMAGES["obj"][0], IMAGES["obj"][1])
    try:
        result = audit(image)
    finally:
        image.stream.close()
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
