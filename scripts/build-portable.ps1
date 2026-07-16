$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Output = Join-Path $Root "output"
$Stage = Join-Path $Output "AutoDy-Windows"
$Archive = Join-Path $Output "AutoDy-Windows-Portable.zip"
$Checksum = Join-Path $Output "AutoDy-Windows-Portable.zip.sha256"

if (Test-Path $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
if (Test-Path $Archive) { Remove-Item -LiteralPath $Archive -Force }
if (Test-Path $Checksum) { Remove-Item -LiteralPath $Checksum -Force }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$items = @(
    "src", "scripts", "docs", "assets", "message-packs", ".github",
    "pyproject.toml", "README.md", "LICENSE", "SECURITY.md", "THIRD_PARTY_NOTICES.md",
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
$forbidden = @("config.yaml", "messages.txt", ".venv", "node_modules", "browser-profile", "avatar-cache", "account-profile", "account-avatar", "discovered_friends", "data\\logs", "data\\history", "data\\preflight")
$entries = Get-ChildItem -LiteralPath $Stage -Recurse -Force | ForEach-Object { $_.FullName.Substring($Stage.Length).TrimStart('\\') }
foreach ($item in $forbidden) {
    if ($entries | Where-Object { $_ -like "*$item*" }) { throw "Portable archive staging contains excluded local data: $item" }
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
"$hash  AutoDy-Windows-Portable.zip" | Set-Content -Encoding ascii -NoNewline $Checksum
Write-Host "Portable archive: $Archive"
Write-Host "SHA-256: $Checksum"
