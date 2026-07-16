@echo off
setlocal
set "AUTODY_HOME=%~dp0"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0data\ms-playwright"
set "PLAYWRIGHT_SKIP_BROWSER_GC=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
set "ExitCode=%ERRORLEVEL%"
if errorlevel 1 (
  echo [ERROR] AutoDy installation failed. See the stage output above.
  pause
  exit /b %ExitCode%
)
echo [SUCCESS] AutoDy installation completed.
pause
exit /b 0
