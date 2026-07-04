$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:AUTODY_HOME = $Root
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Root "data\ms-playwright"
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Config = Join-Path $Root "config.yaml"

if (-not (Test-Path $Python)) {
    throw "未找到 $Python，请先运行 install.cmd。"
}

& $Python -m autody.cli repair-playwright --config $Config
exit $LASTEXITCODE
