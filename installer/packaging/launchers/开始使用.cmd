@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\install.ps1" %*
set "a7c_status=%errorlevel%"
if not "%a7c_status%"=="0" pause
exit /b %a7c_status%
