$ErrorActionPreference = "Stop"
$TaskName = "AutoDy-DailySpark"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Exe = Join-Path $Root ".venv\Scripts\autody.exe"

if (-not (Test-Path $Exe)) {
    throw "Missing $Exe. Create .venv and install the project first."
}
if (-not (Test-Path (Join-Path $Root "config.yaml"))) {
    throw "Missing config.yaml. Copy and edit config.example.yaml first."
}

$Action = New-ScheduledTaskAction `
    -Execute $Exe `
    -Argument "run --config `"$Root\config.yaml`"" `
    -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At "07:30"
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal `
    -UserId $CurrentUser `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Daily Douyin spark message" `
    -Force `
    -ErrorAction Stop | Out-Null

$InstalledTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if (-not $InstalledTask.Settings.StartWhenAvailable) {
    throw "Scheduled task verification failed: StartWhenAvailable is disabled."
}

Write-Host "Scheduled task $TaskName installed for 07:30 local time."
