#!/usr/bin/env python3
"""Build one-shot load/revoke tools offline; never edits a camera or preload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from elftools.elf.elffile import ELFFile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root, out = args.research.resolve(), args.output.resolve()
    src = Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=False)
    observer = src.parent / "observer"
    subprocess.run([sys.executable, str(observer / "audit_loading.py"),
                    "--research", str(root), "--output", str(out / "loading-audit.json")], check=True)
    subprocess.run([sys.executable, str(observer / "build.py"),
                    "--research", str(root), "--output", str(out / "observer-build")], check=True)
    libc = root / "evidence/camera-2.00-boot/lib__libc-2.11.2.so"
    # Observer builder above already verified this exact libc.
    base = ["/opt/homebrew/opt/llvm/bin/clang", "--target=arm-linux-gnueabi",
            "-mcpu=cortex-a9", "-marm", "-mfloat-abi=soft", "-Os", "-Wall", "-Wextra",
            "-Werror", "-fPIC", "-fvisibility=hidden", "-fno-stack-protector",
            "-fno-builtin", "-nostdlib"]
    for name in ("environment", "shim", "entry", "revoke", "enable", "load_check"):
        subprocess.run(base + ["-c", str(src / (name + ".c")),
                              "-o", str(out / (name + ".o"))], check=True)
    startup = src.parents[2] / "maintenance/startup.S"
    subprocess.run(base + ["-c", str(startup), "-o", str(out / "startup.o")], check=True)
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = (str(root / "tools/lld21/lib") +
                               ":/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib")
    link = [str(root / "tools/lld21/lld"), "-flavor", "gnu", "-m", "armelf_linux_eabi",
            "--hash-style=sysv", "-z", "noexecstack", "-z", "relro", "-z", "now",
            # glibc 2.11.2 reapplies DT_RELCOUNT to a separate eager PLT range.
            # LLD can place ARM.exidx between REL and JMPREL. Disable that count.
            "-z", "nocombreloc",
            "--no-undefined", "--allow-shlib-undefined"]
    results = {}
    for name, obj, shared in (("exec-shim.so", "shim", True), ("entry.so", "entry", True),
                              ("revoke", "revoke", False), ("enable", "enable", False),
                              ("load-check", "load_check", False)):
        mode = (["-shared", "-soname", name] if shared else
                ["--dynamic-linker=/lib/ld-linux.so.3", "-e", "_start", str(out / "startup.o")])
        target = out / name
        subprocess.run(link + mode + [str(out / (obj + ".o")), str(out / "environment.o"),
                                      str(libc), "-o", str(target)], env=env, check=True)
        with target.open("rb") as stream:
            elf = ELFFile(stream)
            assert elf["e_machine"] == "EM_ARM" and elf.elfclass == 32
            syms = list(elf.get_section_by_name(".dynsym").iter_symbols())
            imports = sorted(s.name for s in syms if s.name and s["st_shndx"] == "SHN_UNDEF")
            exports = sorted(s.name for s in syms if s.name and s["st_shndx"] != "SHN_UNDEF")
            allowed = {
                "shim": {"open", "close", "fsync", "read", "write", "readlink",
                         "syscall", "__errno_location"},
                "entry": {"environ", "readlink", "getpid"},
                "revoke": {"__libc_start_main", "__errno_location", "open", "close",
                           "read", "write", "fsync", "unlink", "rename"},
                "enable": {"__libc_start_main", "__errno_location", "open", "close",
                           "read", "write", "fsync", "unlink", "rename"},
                "load_check": {"__libc_start_main", "__errno_location", "fork", "execve",
                               "waitpid", "printf", "fflush", "alarm", "signal", "_exit"},
            }[obj]
            assert set(imports) == allowed, (obj, imports)
            tags = list(elf.get_section_by_name(".dynamic").iter_tags())
            assert not any(t.entry.d_tag in ("DT_RELCOUNT", "DT_RELACOUNT") for t in tags)
            needed = [t.needed for t in tags if t.entry.d_tag == "DT_NEEDED"]
            assert needed == ["libc.so.6"], needed
            dynamic = {t.entry.d_tag: t.entry.d_val for t in tags
                       if t.entry.d_tag in {"DT_INIT_ARRAYSZ", "DT_INIT", "DT_FINI",
                                           "DT_FINI_ARRAYSZ", "DT_TEXTREL"}}
            assert not any(x in dynamic for x in ("DT_INIT", "DT_FINI", "DT_FINI_ARRAYSZ", "DT_TEXTREL"))
            assert dynamic.get("DT_INIT_ARRAYSZ", 0) == (4 if obj == "entry" else 0)
            if shared:
                assert set(exports) == ({"execve"} if obj == "shim" else {"a7c_ui_once_entry_status"})
            assert all(not (s["p_flags"] & 1) for s in elf.iter_segments()
                       if s["p_type"] == "PT_GNU_STACK")
            results[name] = {"sha256": sha(target), "bytes": target.stat().st_size,
                             "imports": imports, "exports": exports,
                             "needed": needed, "init_array_bytes": dynamic.get("DT_INIT_ARRAYSZ", 0)}
    payload = (out / "observer-build/a7c-ui-observer.so").read_bytes()
    (out / "observer.so").write_bytes(payload)
    results["observer.so"] = {"sha256": sha(out / "observer.so"), "bytes": len(payload),
                             "manifest": "observer-build/manifest.json"}
    manifest = {
        "schema": 1, "scope": "one-shot loading experiment; observer remains disarmed",
        "target": "ILCE-7C 2.00", "remote_directory": "/setting/a7c-display-once",
        "files": results, "sources": {f.name: sha(f) for f in
                                      sorted(src.glob("*.c")) + sorted(src.glob("*.h")) + [Path(__file__)]},
        "runtime_verified": False, "installed": False,
        "recovery": "revoke --disable; preserve mapped binaries; exit/reboot required to clear mappings",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Built one-shot loading bundle:", out)


if __name__ == "__main__":
    main()
