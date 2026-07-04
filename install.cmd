@echo off
set "AUTODY_HOME=%~dp0"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0data\ms-playwright"
set "PLAYWRIGHT_SKIP_BROWSER_GC=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
pause
