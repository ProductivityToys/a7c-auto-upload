#!/usr/bin/env python3
"""Audit extracted 2.00 loading boundaries. Does not install, load or patch code."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image

SOURCES = {
    "im": ("evidence/camera-2.00-display-runtime/usr__bin__im.elf",
           "fca372d437333271f5d21c880768c02a99509bcc2629e3ba00122fb7a9f716af"),
    "bootin": ("evidence/camera-2.00-boot/usr__bin__bootin.elf",
               "8078230424e9a3c47848ac2a03db044898f05c3f13ef1ec7c4381ac8cd42be1a"),
}


def string(image, address):
    result = bytearray()
    for i in range(256):
        c = image.read(address + i, 1)
        if c == b"\0":
            return result.decode("ascii")
        result.extend(c)
    raise ValueError("Unterminated native string")


def audit(im, boot):
    needed = [t.needed for t in im.elf.get_section_by_name(".dynamic").iter_tags()
              if t.entry.d_tag == "DT_NEEDED"]
    if "libObj.so" in needed:
        raise ValueError("im direct dependency changed")
    checks = [
        (boot, 0x8FEE, "304639462268fff7c8ee"),  # args/env and execve@plt
        (boot, 0x9AFA, "fff707fa"),             # launch helper, not libc system()
        (boot, 0x99D0, "58f8049f4846fff790e907f10b0102464846fff704ea10b10135042df0d1"),
        (im, 0xB3BE, "026900afc0890e46194b00280cbf10461846174b196afdf71eee"),
        (im, 0xB3F4, "61692846fdf704ef"),       # init name -> dlsym
    ]
    for image, address, data in checks:
        if image.read(address, len(bytes.fromhex(data))) != bytes.fromhex(data):
            raise ValueError(f"Unexpected instructions at {address:#x}")
    for image, address, symbol in (
        (boot, 0x131BC, "execve"),
        (im, 0x151A0, "dlopen"),
        (im, 0x15240, "dlsym"),
    ):
        if image.relocations[address] != {"symbol": symbol, "type": 22}:
            raise ValueError("Expected R_ARM_JUMP_SLOT: " + symbol)
    obj_path = string(im, im.u32(0xB42C))
    preload = string(boot, boot.u32(0x9B74))
    flags_argument = string(boot, boot.u32(0x9B9C))
    target = string(boot, boot.u32(0x9B84))
    if (obj_path, preload, flags_argument, target) != (
        "/usr/lib/libObj.so", "/setting/mode/preload", "lazy-global ", "/usr/bin/im.elf ",
    ):
        raise ValueError("Unexpected path/argument constants")
    table = boot.u32(0x9BB8)
    prefixes = [string(boot, boot.u32(table + 4 * i)) for i in range(1, 5)]
    if prefixes != [
        "/usr/tool/LeakTracer.so", "/usr/tool/libefence.so",
        "/usr/tool/libjemalloc_tsh.so", "/usr/tool/libmcheckb.so",
    ]:
        raise ValueError("Unexpected native preload prefix table")
    return {
        "scope": "offline exact-file audit only; not a live installation preflight",
        "sha256": {k: v[1] for k, v in SOURCES.items()},
        "im_direct_needed": needed,
        "module_loading": {
            "function": "im 0xb3b8", "path_constant": obj_path,
            "descriptor": "path +0x10; nonzero halfword +0xe selects libObj path",
            "init_symbol": "descriptor +0x14; looked up via dlsym after dlopen",
            "flags": "runtime state +0x20; bootin appends lazy-global",
            "limitation": "Transitive dependencies and live initialization order not proven.",
        },
        "launch_boundary": {
            "command_builder": "bootin 0x991c",
            "helper_call": "0x9afa -> 0x8f0c",
            "helper": "splits arguments, forks, closes inherited fds, execve with environ",
            "execve_call": "0x8ff4 -> PLT 0x8d88, JUMP_SLOT 0x131bc",
            "target_argument": target,
            "limitation": (
                "2026-10-21 live v5 trial: software reboot restored snapshot state; "
                "no shim/entry/observer mapping in bootin or im and no spent ticket. "
                "The static exec boundary is not a verified post-snapshot entry."
            ),
        },
        "native_preload": {
            "path": preload, "gate": "boot mode bit 0x40",
            "allowed_prefixes": prefixes,
            "comparison": "strncmp(candidate, prefix, strlen(prefix)); not exact equality",
            "decision": "Do not enable diagnostic allocators or repurpose this file for observer.",
        },
        "next_constraints": [
            "Do not retry preload/reboot without evidence bootin and im will actually exec.",
            "Keep observer free of Sony DT_NEEDED and Sony undefined symbols.",
            "If exec-boundary shim is used, its own startup/loading scope still needs proof.",
            "Modify only intended bootin -> im exec environment; preserve other variables.",
            "Remove observer preload entry before im children execute; preserve other entries.",
            "Consume single-use activation before experiment; next boot must work without observer.",
            "Disarm is not dlclose: outstanding callbacks/vtable references must be quiescent.",
        ],
        "camera_accessed": False, "installed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    images = {}
    try:
        for name, (relative, digest) in SOURCES.items():
            images[name] = Image(args.research / relative, digest)
        result = audit(images["im"], images["bootin"])
        with args.output.open("x") as output:
            args.output.chmod(0o600)
            json.dump(result, output, indent=2)
            output.write("\n")
    finally:
        for image in images.values():
            image.stream.close()
    print("Offline loading boundary verified:", args.output)


if __name__ == "__main__":
    main()
