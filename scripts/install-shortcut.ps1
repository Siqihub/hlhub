$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Launcher = Join-Path $Root "scripts\start-dashboard.cmd"
$Icon = Join-Path $Root "assets\icons\autody.ico"
$ShortcutPath = Join-Path $Desktop "AutoDy 管理台.lnk"

if (-not (Test-Path $Launcher)) {
    throw "未找到管理台启动器：$Launcher"
}

foreach ($oldName in @(
    "AutoDy-管理台.cmd",
    "AutoDy-重新登录.cmd",
    "AutoDy-需要处理.txt",
    "AutoDy 管理台.lnk"
)) {
    $oldPath = Join-Path $Desktop $oldName
    if (Test-Path $oldPath) {
        Remove-Item -LiteralPath $oldPath -Force
    }
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "AutoDy 续火助手管理台"
if (Test-Path $Icon) {
    $Shortcut.IconLocation = "$Icon,0"
}
$Shortcut.Save()

Write-Output $ShortcutPath
