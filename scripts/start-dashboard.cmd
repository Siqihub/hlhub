@echo off
chcp 65001 >nul
for %%I in ("%~dp0..") do set "AUTODY_HOME=%%~fI"
set "PLAYWRIGHT_BROWSERS_PATH=%AUTODY_HOME%\data\ms-playwright"
set "PLAYWRIGHT_SKIP_BROWSER_GC=1"

if not exist "%AUTODY_HOME%\.venv\Scripts\python.exe" (
  echo AutoDy 运行环境不存在，请先运行 install.cmd 完成安装或修复。
  pause
  exit /b 1
)

if not exist "%AUTODY_HOME%\config.yaml" (
  echo AutoDy 配置不存在，请先运行 install.cmd 生成配置。
  pause
  exit /b 1
)

cd /d "%AUTODY_HOME%"
powershell.exe -NoProfile -Command "try { $identity = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/service-identity' -TimeoutSec 2 -ErrorAction Stop; if ($identity.application -eq 'AutoDy' -and $identity.project_path -eq $env:AUTODY_HOME) { Start-Process 'http://127.0.0.1:8765'; exit 0 } } catch {} ; exit 1" >nul 2>&1
if not errorlevel 1 exit /b 0
start "" "%AUTODY_HOME%\.venv\Scripts\python.exe" -m autody.cli ui --config "%AUTODY_HOME%\config.yaml"
