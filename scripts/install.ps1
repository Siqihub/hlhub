$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
$env:AUTODY_HOME = $Root
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Root "data\ms-playwright"
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3.11 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
} else {
    throw "未找到 Python 3.11 或更高版本。请先安装 Python。"
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -e "."
& $Python -m playwright install chromium

if (-not (Test-Path "config.yaml")) {
    Copy-Item "config.example.yaml" "config.yaml"
}
if (-not (Test-Path "messages.txt")) {
    Copy-Item "messages.example.txt" "messages.txt"
}

$Shortcut = & (Join-Path $Root "scripts\install-shortcut.ps1")

Write-Host ""
Write-Host "AutoDy 安装完成。" -ForegroundColor Green
Write-Host "桌面入口：$Shortcut"
Write-Host "日常使用只需打开桌面的 AutoDy 管理台，无需再次运行 install.cmd。"
Start-Process $Shortcut
