Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:AUTODY_HOME = $Root
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Root "data\ms-playwright"
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Config = Join-Path $Root "config.yaml"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "AutoDy virtual environment was not found. Run install.cmd first."
}

& $Python -m autody.cli repair-playwright --config $Config
if ($LASTEXITCODE -ne 0) {
    throw "Playwright repair failed with exit code $LASTEXITCODE."
}
