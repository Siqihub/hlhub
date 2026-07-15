$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Output = Join-Path $Root "output"
$Stage = Join-Path $Output "AutoDy-Windows"
$Archive = Join-Path $Output "AutoDy-Windows-Portable.zip"

if (Test-Path $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
if (Test-Path $Archive) { Remove-Item -LiteralPath $Archive -Force }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$items = @(
    "src", "scripts", "docs", "assets", "message-packs", ".github",
    "pyproject.toml", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "config.example.yaml", "messages.example.txt", "install.cmd"
)
foreach ($item in $items) {
    $source = Join-Path $Root $item
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination $Stage -Recurse -Force
    }
}

# Sensitive/runtime paths intentionally excluded: .venv, data, browser-profile,
# avatar-cache, discovered_friends.json, account-profile.json, account-avatar,
# config.yaml, messages.txt, node_modules, .git.
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Archive -Force
Write-Host "Portable archive: $Archive"
