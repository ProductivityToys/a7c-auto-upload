#!/usr/bin/env python3
"""Offline ARM shared observer build. No camera access or loading/install step."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from elftools.elf.elffile import ELFFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES, audit, CUSTOM_TEST


def digest(path):
    with path.open("rb") as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
        return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.research.resolve(), args.output.resolve()
    src = Path(__file__).resolve().parent
    images = {}
    try:
        for name, (relative, sha) in IMAGES.items():
            images[name] = Image(root / relative, sha)
        contract = audit(images)
        obj = images["obj"]
        # Leaf getter bodies: getID returns this+0x24, getValue loads its word.
        for address, data in (
            (0x632542, "80b5243000af80bd"),
            (0x66D468, "80b500af006880bd"),
            (0x3520EA, "80b500af006980bd"),
        ):
            if obj.read(address, 8) != bytes.fromhex(data):
                raise ValueError(f"Read accessor ABI changed at {address:#x}")
    finally:
        for image in images.values():
            image.stream.close()
    libc = root / "evidence/camera-2.00-boot/lib__libc-2.11.2.so"
    if digest(libc) != "2b294f4c256aebb2746cacddefc39c33c448a0d7f18c2813daa54109c445b910":
        raise ValueError("Unverified libc")
    rt = root / "evidence/camera-2.00-boot/lib__librt-2.11.2.so"
    if digest(rt) != "c50f058518dcae9ebb69141cb3b7f7f59d6278e4153020eca00b64ef197b8b40":
        raise ValueError("Unverified librt")
    # Reference only: exact Thumb path for clock 0/1 -> syscall 263 -> svc.
    # Do not link librt: it brings libpthread and initialization side effects.
    with rt.open("rb") as stream:
        elf = ELFFile(stream)
        def read_va(address, size):
            for segment in elf.iter_segments():
                if (segment["p_type"] == "PT_LOAD" and
                    segment["p_vaddr"] <= address and
                    address + size <= segment["p_vaddr"] + segment["p_filesz"]):
                    stream.seek(segment["p_offset"] + address - segment["p_vaddr"])
                    return stream.read(size)
            raise ValueError("Clock audit address not file-backed")
        if read_va(0x31ac, 14) != bytes.fromhex("012810b509d840f2071c00f033fe"):
            raise ValueError("Clock syscall selection changed")
        if read_va(0x3e20, 8) != bytes.fromhex("80b5674600df80bd"):
            raise ValueError("Clock syscall trampoline changed")
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run([
        "/opt/homebrew/opt/llvm/bin/clang", "--target=arm-linux-gnueabi",
        "-mcpu=cortex-a9", "-marm", "-mfloat-abi=soft", "-Os",
        "-Wall", "-Wextra", "-Werror", "-fPIC", "-fvisibility=hidden",
        "-fno-stack-protector", "-fno-builtin", "-nostdlib",
        "-c", str(src / "passive.c"), "-o", str(out / "passive.o"),
    ], check=True)
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = (str(root / "tools/lld21/lib") +
                               ":/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib")
    binary = out / "a7c-ui-observer.so"
    subprocess.run([
        str(root / "tools/lld21/lld"), "-flavor", "gnu", "-m", "armelf_linux_eabi",
        "-shared", "--hash-style=sysv", "-z", "noexecstack", "-z", "relro", "-z", "now",
        "-z", "nocombreloc",  # Avoid old-loader RELCOUNT reuse on a separate PLT range.
        "--no-undefined", "--allow-shlib-undefined", "-soname", binary.name,
        str(out / "passive.o"), str(libc), "-o", str(binary),
    ], env=env, check=True)
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        assert elf["e_machine"] == "EM_ARM" and elf.elfclass == 32
        assert elf["e_type"] == "ET_DYN" and elf["e_entry"] == 0
        syms = list(elf.get_section_by_name(".dynsym").iter_symbols())
        imports = sorted(s.name for s in syms if s.name and s["st_shndx"] == "SHN_UNDEF")
        exports = sorted(s.name for s in syms if s.name and s["st_shndx"] != "SHN_UNDEF")
        assert set(imports) == {
            "getpid", "syscall", "readlink",
        }, imports
        assert set(exports) == {
            CUSTOM_TEST, "a7c_ui_observer_arm", "a7c_ui_observer_disarm",
            "a7c_ui_observer_snapshot",
        }, exports
        tags = list(elf.get_section_by_name(".dynamic").iter_tags())
        assert not any(t.entry.d_tag in {
            "DT_INIT", "DT_INIT_ARRAY", "DT_FINI", "DT_FINI_ARRAY", "DT_TEXTREL",
            "DT_RELCOUNT", "DT_RELACOUNT",
        } for t in tags)
        assert all(not (s["p_flags"] & 1) for s in elf.iter_segments()
                   if s["p_type"] == "PT_GNU_STACK")
        needed = [t.needed for t in tags if t.entry.d_tag == "DT_NEEDED"]
        assert needed == ["libc.so.6"], needed
    manifest = {
        "scope": "offline-only inert shared observer; no loader or UI mutation",
        "runtime_verified": False, "installed": False,
        "abi": 2,
        "binary_sha256": digest(binary), "binary_bytes": binary.stat().st_size,
        "source_sha256": {p.name: digest(p) for p in
                          (src / "passive.c", src / "passive.h", Path(__file__).resolve())},
        "imports": imports, "exports": exports, "needed": needed,
        "libc_sha256": digest(libc), "librt_reference_sha256": digest(rt),
        "clock_source": "ARM EABI syscall 263; audited native clock_gettime and svc trampoline",
        "contract": contract,
        "limits": "one sample, 1..60 second lazy expiry; no constructor or timer",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Built offline observer:", binary)


if __name__ == "__main__":
    main()
