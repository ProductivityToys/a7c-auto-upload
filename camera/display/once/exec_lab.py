#!/usr/bin/env python3
"""Exercise the exact ARM exec shim in fake bootin/im processes, offline only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from loader_lab import ABI, IMAGE, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    root, bundle, out = a.research.resolve(), a.bundle.resolve(), a.output.resolve()
    subprocess.run(["docker", "image", "inspect", IMAGE],
                   check=True, stdout=subprocess.DEVNULL)
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((bundle / "manifest.json").read_text())
    for name, (relative, expected) in ABI.items():
        source = root / "evidence" / relative
        if sha(source) != expected:
            raise ValueError("Unverified ABI: " + str(source))
        shutil.copyfile(source, out / name)
    for name in ("exec-shim.so", "entry.so", "observer.so"):
        if sha(bundle / name) != manifest["files"][name]["sha256"]:
            raise ValueError("Bundle mismatch: " + name)
        shutil.copyfile(bundle / name, out / name)
    src = Path(__file__).resolve().parent
    compiler = ["/opt/homebrew/opt/llvm/bin/clang", "--target=arm-linux-gnueabi",
                "-mcpu=cortex-a9", "-marm", "-mfloat-abi=soft", "-Os",
                "-Wall", "-Wextra", "-Werror", "-fno-stack-protector",
                "-fno-builtin", "-nostdlib", "-c"]
    sources = [(src.parent / "tests/once_exec_arm_fixture.c", "fixture"),
               (src / "environment.c", "environment"),
               (src.parents[2] / "maintenance/startup.S", "startup")]
    for source, name in sources:
        subprocess.run(compiler + [str(source), "-o", str(out / (name + ".o"))],
                       check=True)
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = (str(root / "tools/lld21/lib") +
                               ":/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib")
    subprocess.run([
        str(root / "tools/lld21/lld"), "-flavor", "gnu", "-m", "armelf_linux_eabi",
        "--hash-style=sysv", "-z", "nocombreloc", "-z", "now", "-z", "relro",
        "-z", "noexecstack", "--dynamic-linker=/lab/ld.so", "-e", "_start",
        *(str(out / (name + ".o")) for _, name in sources),
        str(out / "libc.so.6"), "-o", str(out / "fixture"),
    ], env=env, check=True)
    for name in ("ld.so", "fixture"):
        (out / name).chmod(0o755)
    (out / "invalid-executable").write_bytes(b"not an ELF executable\n")
    (out / "invalid-executable").chmod(0o755)
    remote = "/setting/a7c-display-once"
    report = {
        "scope": "isolated ARM fake bootin/im exec; no Sony processes or devices",
        "image": IMAGE, "abi": ABI,
        "files": {n: sha(out / n) for n in
                  ("ld.so", "libc.so.6", "exec-shim.so", "entry.so", "observer.so", "fixture")},
        "cases": [],
    }
    for case in ("once", "no-ticket", "bad-ticket", "spent",
                 "wrong-caller", "wrong-target", "exec-failure"):
        name = "a7c-exec-lab-" + uuid.uuid4().hex[:12]
        cmd = ["docker", "run", "--rm", "--init", "--pull", "never", "--name", name,
               "--platform", "linux/arm/v7", "--network", "none", "--read-only",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--memory", "256m", "--cpus", "1", "--pids-limit", "32",
               "--ulimit", "core=0", "--tmpfs", remote + ":rw,noexec,nosuid,size=64k",
               "--env", "LD_LIBRARY_PATH=/lab", "--env", "LD_PRELOAD=/lab/exec-shim.so"]
        mounts = [(out, "/lab"), (out / "fixture", "/usr/bin/bootin.elf"),
                  (out / "fixture", "/usr/bin/other.elf"),
                  (out / ("invalid-executable" if case == "exec-failure" else "fixture"),
                   "/usr/bin/im.elf")]
        for payload in ("entry.so", "observer.so"):
            mounts.append((out / payload, remote + "/" + payload))
        for source, target in mounts:
            cmd += ["--mount", f"type=bind,src={source},dst={target},readonly"]
        # Direct exec is essential: shim scopes itself using /proc/self/exe.
        entry = "/usr/bin/other.elf" if case == "wrong-caller" else "/usr/bin/bootin.elf"
        cmd += ["--entrypoint", entry, IMAGE, case]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=20)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL)
            raise
        output = result.stdout.decode(errors="replace")
        passed = result.returncode == 0 and "A7C_ARM_EXEC_OK" in output
        report["cases"].append({"name": case, "exit": result.returncode,
                                "passed": passed, "output": output})
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(case, result.returncode, "PASS" if passed else "FAIL", flush=True)
        if not passed:
            raise SystemExit("ARM exec lab failed; evidence retained")


if __name__ == "__main__":
    main()
