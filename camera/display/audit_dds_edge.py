#!/usr/bin/env python3
"""Offline contract for the fixed DDS corner experiment; no camera writes."""
import argparse
import json
from pathlib import Path
from audit_ui_contract import Image, IMAGES
from audit_overlay_routes import expect
from audit_dds_text import audit as audit_text


def audit(image):
    audit_text(image)
    # DMP's clip rectangle +28..2e becomes the GL viewport, not glScissor.
    expect(image, 0x7d2316, bytes.fromhex(
        "b4f92800b4f92a10b4f92c20b4f92e30e5f7fbfe"))
    # Setter's context +8/+c/+10/+14 and dirty flag +6fc.
    expect(image, 0x7cef70, bytes.fromhex("01238460c5600661416180f8fc36"))
    # GL_VIEWPORT (0xba2) query returns those same four fields.
    expect(image, 0x7a2122, bytes.fromhex("40f6a2318e420fd0"))
    expect(image, 0x7a214a, bytes.fromhex(
        "8168c8f80010c368c8f804300269c8f808204169c8f80c10"))
    return {
        "scope": "offline contract; clipped rendering still requires runtime validation",
        "firmware_sha256": IMAGES["obj"][1],
        "route_elf": ["0x68d13c", "0x68ce02", "0x68d7b8", "0x68bc04",
                      "0x7d1de0", "0x7d4520", "0x7d39d0", "0x7d2090"],
        "viewport_setter_elf": "0x7b8120", "viewport_storage_elf": "0x7cef60",
        "viewport_query_enum": "0xba2", "not_scissor_enable": True,
        "original_position": [30, 250], "candidate_position": [536, 432],
        "unchanged_destination_size": [576, 192],
        "predicted_visible_rectangle": [536, 432, 104, 48],
        "ram_changes": {"shared_font_bytes": 128, "coordinate_bytes": 4},
        "executable_changes": 0,
        "limits": ["corner only; underlying DDS surface still full sized",
                   "no independent plane or transparency proof",
                   "no exclusion lock against native DDS users"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    im = Image(args.research / IMAGES["obj"][0], IMAGES["obj"][1])
    try:
        result = audit(im)
    finally:
        im.stream.close()
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
