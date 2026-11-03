#!/usr/bin/env python3
"""Assemble separate script/macOS packages; Windows archive comes from its build host."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
PREFIX = "a7c-installer-" + json.loads((HERE / "validation.json").read_text())["installer_version"]
GUIDES = ("START_HERE.md", "RECOVERY.md", "FEEDBACK.md", "SHARING.md")


def verify_payloads(mac_app, windows_zip):
    expected = (HERE / "a7c_installer/resources/camera.zip").read_bytes()
    with zipfile.ZipFile(HERE / "a7c_installer/resources/camera.zip") as archive:
        version = json.loads(archive.read("manifest.json"))["payload_version"]
    validation = json.loads((HERE / "validation.json").read_text())
    if validation["payload_version"] != version:
        raise ValueError("Validation describes a different payload")
    for name in (*GUIDES, "THIRD_PARTY.md", "validation.json"):
        guides = list(mac_app.rglob("help/" + name))
        if not guides or any(p.read_bytes() != (HERE / name).read_bytes() for p in guides):
            raise ValueError("macOS App bundled help differs from source: " + name)
    mac_payloads = list(mac_app.rglob("camera.zip"))
    if not mac_payloads or any(p.read_bytes() != expected for p in mac_payloads):
        raise ValueError("macOS App payload differs from source")
    with zipfile.ZipFile(windows_zip) as archive:
        names = [n for n in archive.namelist() if n.replace("\\", "/").endswith("/a7c_installer/resources/camera.zip")]
        for guide in (*GUIDES, "THIRD_PARTY.md", "validation.json"):
            help_files = [n for n in archive.namelist() if n.replace("\\", "/").endswith("/resources/help/" + guide)]
            if not help_files or any(archive.read(n) != (HERE / guide).read_bytes() for n in help_files):
                raise ValueError("Windows bundled help differs from source: " + guide)
        if not names or any(archive.read(n) != expected for n in names):
            raise ValueError("Windows App payload differs from source")


def document(destination):
    text = (HERE / "README.md").read_text().replace("../docs/installer.md", "DESIGN.md")
    (destination / "README.md").write_text(text)
    design = HERE.parent / "docs/installer.md"
    if not design.exists():
        design = HERE / "DESIGN.md"
    (destination / "DESIGN.md").write_text(design.read_text().replace("../installer/README.md", "README.md"))
    shutil.copyfile(HERE / "THIRD_PARTY.md", destination / "THIRD_PARTY.md")
    shutil.copyfile(HERE / "validation.json", destination / "validation.json")
    for name in GUIDES:
        shutil.copyfile(HERE / name, destination / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mac-app", type=Path, required=True)
    parser.add_argument("--windows-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify_payloads(args.mac_app, args.windows_zip)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    prefix = PREFIX
    if any(output.glob(prefix + "-*")):
        raise ValueError("同名发行成品已存在；请增加版本或选择新的输出目录，不覆盖已发送的文件。")
    files = []
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        root = Path(temporary) / (prefix + "-scripts")
        shutil.copytree(HERE, root / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "dist", "build", "*.spec", "distributions*.json", "tests"))
        document(root / "app")
        for launcher in (HERE / "packaging/launchers").iterdir():
            shutil.copy2(launcher, root / launcher.name)
        path = output / (root.name + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(root.rglob("*")):
                if source.is_file():
                    archive.write(source, source.relative_to(root.parent))
        files.append(path)
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        root = Path(temporary) / 'volume'
        root.mkdir()
        subprocess.run(['ditto', str(args.mac_app), str(root / 'A7C 自动上传.app')], check=True)
        (root / 'Applications').symlink_to('/Applications', target_is_directory=True)
        path = output / (prefix + '-macos-arm64.dmg')
        subprocess.run(['hdiutil', 'create', '-srcfolder', str(root),
                        '-volname', 'A7C 自动上传 - 拖入应用程序', '-fs', 'HFS+',
                        '-format', 'UDZO', str(path)], check=True)
        files.append(path)
    target = output / (prefix + "-windows-x64.zip")
    top = prefix + "-windows-x64/"
    input_top = PREFIX + "-windows-x64/"
    temporary = target.with_suffix(".next.zip")
    with zipfile.ZipFile(args.windows_zip) as original, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in original.infolist():
            name = entry.filename.replace("\\", "/")
            if not name.startswith(input_top) or ".." in Path(name).parts:
                raise ValueError("Unexpected Windows archive root")
            application = input_top + 'A7C Installer/'
            if not name.startswith(application):
                continue  # User help and licenses already live inside the app.
            relative = name[len(application):]
            if not relative:
                continue
            if relative == 'A7C Installer.exe':
                relative = 'A7C 自动上传.exe'
            normalized = copy.copy(entry)
            normalized.filename = top + relative
            archive.writestr(normalized, original.read(entry.filename))
    temporary.replace(target)
    files.append(target)
    manifest = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
    (output / "packages.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "SHA256SUMS").write_text("".join(v["sha256"] + "  " + k + "\n" for k, v in manifest.items()))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
