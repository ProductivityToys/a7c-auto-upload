# Build a replaceable libwdi DLL with signed upstream libusb-win32 payloads.
# Run on Windows x64. Dependencies are pinned source archives, not live downloads.
param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop'
& 'C:\Program Files\7-Zip\7z.exe' x "$Root\w64devkit.exe" "-o$Root\toolchain" -y | Out-Null
Expand-Archive "$Root\libwdi-v1.5.1.zip" "$Root\driver-source" -Force
Expand-Archive "$Root\libusb-win32-1.4.0.2.zip" "$Root\driver-source" -Force
$env:PATH="$Root\toolchain\w64devkit\bin;"+$env:PATH
$src="$Root\driver-source\libwdi-1.5.1"
$usb=(Get-ChildItem "$Root\driver-source" -Directory -Filter 'libusb-win32*' | Select-Object -First 1).FullName.Replace('\','/')
$config=@"
#define OPT_M64 1
#define WDF_VER 1011
#define ENABLE_LOGGING 1
#define INCLUDE_DEBUG_LOGGING 1
#define LIBUSB0_DIR "$usb"
#define INSTALLER_PATH_64 "."
#define PACKAGE_VERSION "1.5.1"
"@
[IO.File]::WriteAllText("$src\config.h",$config)
Set-Location "$src\libwdi"
$ErrorActionPreference='Continue'
& gcc -O2 -I.. installer.c -o installer_x64.exe -static -lsetupapi -lnewdev -lole32
if($LASTEXITCODE -ne 0){throw 'installer compile failed'}
& gcc -O2 -I.. embedder.c -o embedder.exe
if($LASTEXITCODE -ne 0){throw 'embedder compile failed'}
& .\embedder.exe embedded.h
if($LASTEXITCODE -ne 0){throw 'embedding failed'}
& windres -i libwdi.rc -o libwdi_rc.o
if($LASTEXITCODE -ne 0){throw 'resource failed'}
& gcc -O2 -shared -I.. -DDLL_EXPORT -o libwdi.dll logging.c tokenizer.c vid_data.c pki.c libwdi_dlg.c libwdi.c libwdi_rc.o '-Wl,--out-implib,libwdi.dll.a' -lsetupapi -lole32 -lntdll -static-libgcc
if($LASTEXITCODE -ne 0){throw 'DLL compile failed'}
# Only a read-only enumeration test; no prepare/stage/install calls.
Write-Output 'Driver DLL build completed'
