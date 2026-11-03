#!/usr/bin/env python3
"""Prepare pinned own-camera payloads and minimal MIT upstream USB sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parents[1]
APP = HERE.parent
PMCA_REVISION = "a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pmca", type=Path, required=True)
    parser.add_argument("--local-media", type=Path, required=True, help="ARM build with FAT long-name receipt lookup fix")
    parser.add_argument("--plainftp", type=Path, required=True, help="ARM FTP client with read-only connection check")
    parser.add_argument("--discovery", type=Path, required=True, help="ARM recorder hint with suspend/resume detection")
    parser.add_argument("--native-display", type=Path, required=True, help="Verified single/dual-buffer service build at /tmp_bt/a7X.so")
    args = parser.parse_args()
    actual = subprocess.check_output(["git", "-C", str(args.pmca), "rev-parse", "HEAD"], text=True).strip()
    if actual != PMCA_REVISION:
        raise SystemExit("Unexpected upstream revision")
    payload = {}
    root = APP / "releases"
    with zipfile.ZipFile(root / "0.4.0-home.1/a7c-nas-uploader-0.4.0-home.1.zip") as archive:
        frozen = json.loads(archive.read("manifest.json"))

        def read(name):
            value = archive.read(name)
            if digest(value) != frozen["files"][name]["sha256"]:
                raise ValueError("Frozen payload differs: " + name)
            return value

        payload["/setting/a7c-uploader/worker.sh"] = read("payload/boot.sh")
        for name in frozen["files"]:
            if name.startswith("payload/plainftp/"):
                payload["/setting/a7c-uploader/" + name[len("payload/"):]] = read(name)
        for name in ("native-probe", "native-module.so", "native-start.sh", "consumer.sh", "native.sha256", "redraw"):
            payload["/setting/a7c-display/" + name] = read("payload/display/" + name)
        dependencies = dict(line.split()[::-1] for line in read("payload/display/native.sha256").decode().splitlines())
    media = args.local_media.read_bytes()
    if not media.startswith(b"\x7fELF\x01\x01") or media[18:20] != b"\x28\x00":
        raise ValueError("local-media must be an ARM little-endian ELF32 build")
    payload["/setting/a7c-uploader/plainftp/local-media"] = media
    for name, path in (("plainftp", args.plainftp), ("discovery", args.discovery)):
        value = path.read_bytes()
        if not value.startswith(b"\x7fELF\x01\x01") or value[18:20] != b"\x28\x00":
            raise ValueError(name + " must be an ARM little-endian ELF32 build")
        payload["/setting/a7c-uploader/plainftp/" + name] = value
    native = json.loads((args.native_display / "manifest.json").read_text())
    if (not native.get("rect_service_trial") or not native.get("service_lifecycle_ack")
            or native["path"] != "/tmp_bt/a7X.so"):
        raise ValueError("Unexpected native display service build")
    for source, target in (("marker.so", "native-module.so"), ("module-probe", "native-probe")):
        value = (args.native_display / source).read_bytes()
        if digest(value) != native["binaries"][source]:
            raise ValueError("Native display build differs: " + source)
        payload["/setting/a7c-display/" + target] = value
    payload["/setting/a7c-display/native-start.sh"] = (APP / "camera/display/upload/native-start.sh").read_bytes().replace(b"M=/tmp_bt/a70.so\n", b"M=/tmp_bt/a7X.so\n")
    plain = "/setting/a7c-uploader/plainftp/"
    payload[plain + "plain-worker.sh"] = (APP / "camera/uploader/plainftp/worker.sh").read_bytes()
    members = [line.split()[1] for line in payload[plain + "manifest"].decode().splitlines()]
    payload[plain + "manifest"] = "".join(digest(payload[plain + n]) + " " + n + "\n" for n in members).encode()
    with zipfile.ZipFile(root / "0.1.0-baseline.1/a7c-nas-uploader-0.1.0-baseline.1-apps-layout.2.zip") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        name = "camera/uploader/launcher.so"
        value = archive.read(name)
        assert digest(value) == manifest["files"][name]["sha256"]
        payload["/setting/a7c-uploader/launcher.so"] = value
    payload["/setting/a7c-uploader/supervisor.sh"] = (HERE / "camera/supervisor.sh").read_bytes()
    payload["/setting/a7c-display/stage.sh"] = (HERE / "camera/display-stage.sh").read_bytes()
    payload["/setting/a7c-display/stage.sha256"] = (digest(payload["/setting/a7c-display/stage.sh"]) + "\n").encode()
    prefix = "/setting/a7c-display/"
    members = ["native-probe", "native-module.so", "native-start.sh", "consumer.sh", "native.sha256", "redraw"]
    payload[prefix + "manifest"] = "".join(digest(payload[prefix + n]) + " " + n + "\n" for n in members).encode()
    info = {
        "format": 1, "payload_version": "0.4.1-installer.14-preview",
        "firmware": {"model": "ILCE-7C", "version": "2.00", "version_txt": "39119_05.2021111501", "dependencies": dependencies},
        "files": {},
    }
    resources = HERE / "a7c_installer/resources"
    resources.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(resources / "camera.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for target, value in sorted(payload.items()):
            name = target.removeprefix("/setting/")
            info["files"][name] = {"target": target, "bytes": len(value), "sha256": digest(value)}
            archive.writestr(name, value)
        archive.writestr("manifest.json", json.dumps(info, indent=2) + "\n")
    vendor = HERE / "vendor/pmca"
    vendor.mkdir(parents=True, exist_ok=True)
    for name in ("__init__.py",):
        shutil.copyfile(args.pmca / "pmca" / name, vendor / name)
    for name in ("usb", "util"):
        shutil.copytree(args.pmca / "pmca" / name, vendor / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(args.pmca / "LICENSE.txt", HERE / "vendor/PMCA-LICENSE.txt")
    (HERE / "vendor/NOTICE.txt").write_text(
        "Sony-PMCA-RE USB transport subset\nhttps://github.com/ma1co/Sony-PMCA-RE\n"
        + PMCA_REVISION + "\nMIT license: PMCA-LICENSE.txt\n")
    print("Prepared", len(payload), "camera files; upstream", PMCA_REVISION)


if __name__ == "__main__":
    main()
