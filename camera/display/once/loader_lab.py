#!/usr/bin/env python3
"""Run ARM entry loading in an isolated Docker lab, never on the camera."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

IMAGE = "alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc"
ABI = {
    "ld.so": ("camera-2.00-resume/lib__ld-2.11.2.so",
              "bea521ec613680aae1f9237ccdec52b79169b079969f184d62b3e7f6b1ee5246"),
    "libc.so.6": ("camera-2.00-boot/lib__libc-2.11.2.so",
                  "2b294f4c256aebb2746cacddefc39c33c448a0d7f18c2813daa54109c445b910"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--regression-entry", type=Path,
                   help="Optional old failing entry.so; expected to exit 139 in lab")
    a = p.parse_args()
    root, bundle, out = a.research.resolve(), a.bundle.resolve(), a.output.resolve()
    # Image must already be available; the test itself has no network access.
    subprocess.run(["docker", "image", "inspect", IMAGE],
                   check=True, stdout=subprocess.DEVNULL)
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((bundle / "manifest.json").read_text())
    for name, (relative, expected) in ABI.items():
        source = root / "evidence" / relative
        if sha(source) != expected:
            raise ValueError("Unverified ABI file: " + str(source))
        shutil.copyfile(source, out / name)
    for name in ("entry.so", "observer.so"):
        if sha(bundle / name) != manifest["files"][name]["sha256"]:
            raise ValueError("Bundle does not match manifest")
        shutil.copyfile(bundle / name, out / name)
    if a.regression_entry:
        shutil.copyfile(a.regression_entry, out / "regression.so")
    src = Path(__file__).resolve().parent
    fixture = src.parent / "tests/once_arm_fixture.c"
    startup = src.parents[2] / "maintenance/startup.S"
    compiler = ["/opt/homebrew/opt/llvm/bin/clang", "--target=arm-linux-gnueabi",
                "-mcpu=cortex-a9", "-marm", "-mfloat-abi=soft", "-Os",
                "-Wall", "-Wextra", "-Werror", "-fno-stack-protector",
                "-fno-builtin", "-nostdlib", "-c"]
    for source, name in ((fixture, "fixture.o"), (startup, "startup.o")):
        subprocess.run(compiler + [str(source), "-o", str(out / name)], check=True)
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = (str(root / "tools/lld21/lib") +
                               ":/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib")
    subprocess.run([
        str(root / "tools/lld21/lld"), "-flavor", "gnu", "-m", "armelf_linux_eabi",
        "--hash-style=sysv", "-z", "nocombreloc", "--dynamic-linker=/lab/ld.so",
        "-e", "_start", str(out / "startup.o"), str(out / "fixture.o"),
        str(out / "libc.so.6"), "-o", str(out / "fixture"),
    ], env=env, check=True)
    for name in ("ld.so", "fixture"):
        (out / name).chmod(0o755)
    remote = "/setting/a7c-display-once"
    combined = remote + "/entry.so:" + remote + "/observer.so"
    cases = [
        ("baseline", "absent", {}, 0),
        ("entry", "unmarked", {"LD_PRELOAD": remote + "/entry.so"}, 0),
        ("observer", "absent", {"LD_PRELOAD": remote + "/observer.so"}, 0),
        ("combined", "unmarked", {"LD_PRELOAD": combined}, 0),
        ("restore-unset", "unset", {"LD_PRELOAD": combined, "A7C_UI_ONCE": "v1"}, 0),
    ]
    for label, old in (("empty", ""), ("saved", "/lab/libc.so.6")):
        cases.append(("restore-" + label, label, {
            "LD_PRELOAD": combined + ":" + old, "A7C_UI_ONCE": "v1",
            "A7C_UI_SAVED_LD_PRELOAD": old,
        }, 0))
    if a.regression_entry:
        cases.append(("old-entry-control", "unmarked", {"LD_PRELOAD": "/lab/regression.so"}, 139))
    report = {
        "scope": "isolated ARM userspace; no Sony kernel, drivers, im or UI",
        "image": IMAGE, "abi": ABI,
        "files": {n: sha(out / n) for n in ("ld.so", "libc.so.6", "entry.so", "observer.so", "fixture")},
        "cases": [],
    }
    if a.regression_entry:
        report["files"]["regression.so"] = sha(out / "regression.so")
    for label, mode, variables, expected in cases:
        name = "a7c-loader-lab-" + uuid.uuid4().hex[:12]
        cmd = ["docker", "run", "--rm", "--init", "--pull", "never", "--name", name,
               "--platform", "linux/arm/v7", "--network", "none", "--read-only",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--memory", "256m", "--cpus", "1", "--pids-limit", "32",
               "--ulimit", "core=0"]
        for mount in ("/lab", remote):
            cmd += ["--mount", f"type=bind,src={out},dst={mount},readonly"]
        for key, value in variables.items():
            cmd += ["--env", key + "=" + value]
        cmd += ["--entrypoint", "/lab/ld.so", IMAGE,
                "--library-path", "/lab", "/lab/fixture", mode]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL)
            raise
        output = result.stdout.decode(errors="replace")
        passed = result.returncode == expected and (
            "A7C_ARM_ENTRY_OK" in output if expected == 0 else "Segmentation fault" in output)
        report["cases"].append({"name": label, "expected": expected,
                                "exit": result.returncode, "passed": passed, "output": output})
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(label, result.returncode, "PASS" if passed else "FAIL", flush=True)
        if not passed:
            raise SystemExit("Loader lab failed; report retained")


if __name__ == "__main__":
    main()
