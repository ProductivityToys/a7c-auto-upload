$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding
if ($args.Count -eq 0) {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) {
        try {
            $launchArgs = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"'
            $process = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList $launchArgs
            exit $process.ExitCode
        } catch {
            Write-Host 'Administrator launch cancelled or failed.'
            exit 1
        }
    }
}
try {
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ from python.org first.' }
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
$ErrorActionPreference = 'Continue'
& '.venv\Scripts\python.exe' -c 'import usb, Cryptodome, libusb_package' 2>$null
$a7c_import_exit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($a7c_import_exit -ne 0) {
    & '.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if ($args.Count -eq 0) {
    & '.venv\Scripts\python.exe' -m a7c_installer.interactive
} else {
    & '.venv\Scripts\python.exe' install.py @args
}
exit $LASTEXITCODE

} catch {
    Write-Host $_.Exception.Message
    if ($args.Count -eq 0) { Read-Host 'Startup failed. Press Enter to close' | Out-Null }
    exit 1
}
