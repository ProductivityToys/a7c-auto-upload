#!/usr/bin/env python3
"""Build on each target OS; packages own payloads and MIT PMCA transport only."""
import argparse
import os
import json
import plistlib
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]


def finalize_macos(app):
    metadata = json.loads((HERE / 'validation.json').read_text())
    version = metadata['installer_version']
    plist = app / 'Contents/Info.plist'
    value = plistlib.loads(plist.read_bytes())
    value.update(CFBundleDisplayName='A7C 自动上传',
                 CFBundleShortVersionString=version.split('-')[0],
                 CFBundleVersion=metadata['package_revision'].rsplit('.', 1)[-1],
                 CFBundleGetInfoString=version,
                 NSRemovableVolumesUsageDescription='需要访问 USB 相机，以读取上传服务配置并安装、更新或卸载相机服务。')
    plist.write_bytes(plistlib.dumps(value))
    subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, help="Reusable PyInstaller work/spec directory")
    parser.add_argument("--console", action="store_true", help="Diagnostic build with visible stderr")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = args.work_root.resolve() if args.work_root else output
    work.mkdir(parents=True, exist_ok=True)
    separator = ":" if sys.platform != "win32" else ";"
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
              "--distpath", str(output), "--workpath", str(work / "build"),
              "--specpath", str(work / "spec"), "--paths", str(HERE),
              "--paths", str(HERE / "vendor"),
              "--add-data", str(HERE / "a7c_installer/resources") + separator + "a7c_installer/resources",
              "--add-data", str(HERE / "vendor") + separator + "vendor",
              "--add-data", str(HERE / "licenses") + separator + "licenses",
              "--add-data", str(HERE / "THIRD_PARTY.md") + separator + ".",
              "--copy-metadata", "PySide6-Essentials", "--copy-metadata", "shiboken6",
              "--copy-metadata", "pyusb", "--copy-metadata", "pycryptodomex",
              "--collect-all", "libusb_package", "--hidden-import", "pmca.usb.sony",
              "--hidden-import", "pmca.usb.driver.generic.libusb",
              "--hidden-import", "Cryptodome.Hash.SHA256",
              "--hidden-import", "Cryptodome.Hash.SHA1"]
    for name in ('START_HERE.md', 'RECOVERY.md', 'SHARING.md', 'FEEDBACK.md', 'THIRD_PARTY.md', 'validation.json'):
        common += ['--add-data', str(HERE / name) + separator + 'a7c_installer/resources/help']
    environment = os.environ.copy()
    # A venv created from Conda does not expose Library/bin to PyInstaller's
    # dependency analysis, although source Python can import ctypes normally.
    conda_libraries = Path(sys.base_prefix) / "Library/bin"
    if sys.platform == "win32" and conda_libraries.is_dir():
        environment["PATH"] = str(conda_libraries) + os.pathsep + environment.get("PATH", "")
        ffi = conda_libraries / "ffi-8.dll"
        if ffi.is_file():
            common += ["--add-binary", str(ffi) + ";."]
    gui = common + ["--name", "A7C Installer", "--console" if args.console else "--windowed"]
    gui += ['--icon', str(HERE / 'packaging/assets' / ('app.icns' if sys.platform == 'darwin' else 'app.ico'))]
    if sys.platform == "win32":
        gui += ["--uac-admin"]
    if sys.platform == "darwin":
        gui += ["--osx-bundle-identifier", "net.zeenith.a7c-installer"]
    subprocess.run(gui + [str(HERE / "app.py")], check=True, cwd=HERE, env=environment)
    if sys.platform == 'darwin':
        finalize_macos(output / 'A7C Installer.app')
    # CLI remains a source bundle: small and inspectable, sharing the same core.
    print("Built desktop app:", output)


if __name__ == "__main__":
    main()
