@echo off
chcp 65001 >nul
for %%I in ("%~dp0..") do set "AUTODY_HOME=%%~fI"
set "PLAYWRIGHT_BROWSERS_PATH=%AUTODY_HOME%\data\ms-playwright"
set "PLAYWRIGHT_SKIP_BROWSER_GC=1"

if not exist "%AUTODY_HOME%\.venv\Scripts\autody.exe" (
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
start "" "%AUTODY_HOME%\.venv\Scripts\autody.exe" ui --config "%AUTODY_HOME%\config.yaml"
