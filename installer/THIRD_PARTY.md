# Third-party components

- Sony-PMCA-RE USB subset: MIT, copyright upstream contributors.
  Revision `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0`.
  https://github.com/ma1co/Sony-PMCA-RE — `vendor/PMCA-LICENSE.txt`.
- PyUSB 1.3.1: BSD-3-Clause. https://github.com/pyusb/pyusb
- PyCryptodome / pycryptodomex 3.24.1: BSD / public domain components.
  https://www.pycryptodome.org/
- libusb-package 1.0.30.0: Apache-2.0 wrapper; bundled libusb is LGPL-2.1-or-later.
  https://github.com/pyocd/libusb-package and https://libusb.info/
- PySide6-Essentials / Shiboken6 / Qt 6.12.0: LGPL-3.0-only option used for this preview.
  https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.12.0
  https://download.qt.io/official_releases/qt/6.12/6.12.0/single/
  Qt libraries are dynamically linked and replaceable in the unpacked App directory.
  No restriction on reverse engineering for debugging modifications to these libraries is imposed.
  License texts are included under `licenses/`.
- CPython: PSF license. https://www.python.org/
- PyInstaller bootloader: GPL with distribution exception. https://pyinstaller.org/en/stable/license.html

Desktop distributions include dependency metadata; source is supplied alongside them.
The uploader includes original ARM code, not Sony firmware libraries or fonts.

- Windows driver preparation: libwdi 1.5.1, LGPL-3.0-or-later, Pete Batard and contributors.
  https://github.com/pbatard/libwdi/tree/v1.5.1
  Replaceable `a7c_installer/resources/windows-drivers/libwdi.dll` embeds upstream libusb-win32 1.4.0.2.
  Driver binaries: GPL-3.0; user library/installer: LGPL, as stated in the included installer_license.txt.
  https://github.com/mcuee/libusb-win32/tree/release_1.4.0.2
  Exact source archives, upstream binary archive, build script and version/hash manifest are included
  in `resources/windows-drivers`; license texts are also under `licenses/`.
  The DLL is built with w64devkit x64 2.11.0; see the included build instructions.
  No restriction on replacement or reverse engineering to debug modified libraries is imposed.
