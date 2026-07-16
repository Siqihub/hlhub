@echo off
setlocal
set "ScriptsDir=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ScriptsDir%start-dashboard.ps1"
exit /b %ERRORLEVEL%
