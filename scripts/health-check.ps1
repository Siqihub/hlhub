$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Exe = Join-Path $Root ".venv\Scripts\autody.exe"
$Config = Join-Path $Root "config.yaml"
$LogDir = Join-Path $Root "data\logs"
$Log = Join-Path $LogDir "scheduler.log"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Alert = Join-Path $Desktop "AutoDy-需要处理.txt"
$LoginShortcut = Join-Path $Desktop "AutoDy-重新登录.cmd"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
@"
@echo off
cd /d "$Root"
"$Exe" login --config "$Config"
pause
"@ | Set-Content -Encoding ASCII $LoginShortcut

"[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")] 开始登录健康检查" |
    Add-Content -Encoding UTF8 $Log
$stdout = Join-Path $env:TEMP "autody-health-stdout-$PID.log"
$stderr = Join-Path $env:TEMP "autody-health-stderr-$PID.log"
$process = Start-Process `
    -FilePath $Exe `
    -ArgumentList @("health-check", "--config", "`"$Config`"") `
    -WorkingDirectory $Root `
    -Wait `
    -PassThru `
    -NoNewWindow `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr
foreach ($path in @($stdout, $stderr)) {
    if (Test-Path $path) {
        Get-Content -Raw -Encoding UTF8 $path | Add-Content -Encoding UTF8 $Log
        Remove-Item -LiteralPath $path -Force
    }
}
$exitCode = $process.ExitCode

if ($exitCode -ne 0) {
    $message = @"
AutoDy 登录或聊天页面检查失败。
时间：$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

请双击桌面的 AutoDy-重新登录.cmd，完成扫码或安全验证。
详细日志：$Log
"@
    $message | Set-Content -Encoding UTF8 $Alert
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        $message,
        "AutoDy 需要重新登录",
        "OK",
        "Warning"
    ) | Out-Null
}

exit $exitCode
