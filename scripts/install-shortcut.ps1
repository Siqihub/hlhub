Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Launcher = Join-Path $ProjectRoot "scripts\start-dashboard.cmd"
$Icon = Join-Path $ProjectRoot "assets\icons\autody.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "AutoDy Management.lnk"

if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    throw "AutoDy launcher not found: $Launcher"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.Arguments = ""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "AutoDy Management"

if (Test-Path -LiteralPath $Icon -PathType Leaf) {
    $Shortcut.IconLocation = ('{0},0' -f $Icon)
}

$Shortcut.Save()

if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) {
    throw "Shortcut creation failed: $ShortcutPath"
}

Write-Output $ShortcutPath
