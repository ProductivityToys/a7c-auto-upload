# Windows driver component

libwdi 1.5.1, libusb-win32 1.4.0.2, x64 only. libwdi.dll is dynamically loaded and replaceable.
Exact unmodified upstream source archives and the libusb-win32 binary input are included here.
Build configuration and commands are in build_windows_drivers.ps1; DLL C sources are unmodified.

To reproduce on Windows x64, obtain w64devkit-x64-2.11.0.7z.exe from
https://github.com/skeeto/w64devkit/releases/tag/v2.11.0 and save it as w64devkit.exe.
Place the included libwdi source archive under the name libwdi-v1.5.1.zip and the
libusb-win32 binary archive under libusb-win32-1.4.0.2.zip in the same scratch directory.
Run build_windows_drivers.ps1 -Root <scratch directory>; 7-Zip is required at the path in the script.
The output is driver-source/libwdi-1.5.1/libwdi/libwdi.dll. Compiler tooling is not shipped in this app.

The hash manifest checks the shipped DLL. To use a locally rebuilt replacement, update its
binaries/libwdi.dll SHA256 entry in manifest.json. This check is not a signature or publisher trust mechanism.
An offline app self-check loads the DLL and checks its embedded driver capability without
preparing, staging or installing a driver, enumerating USB devices, or modifying certificate stores.

Generated packages and rollback records are stored in %ProgramData%/A7CInstaller/drivers.
libwdi generates a device-scoped signing certificate during preparation. Recovery removes the
recorded driver package; it does not remove certificates from Windows trust stores.
