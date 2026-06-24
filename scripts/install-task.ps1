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

$PowerShell = (Get-Command powershell.exe).Source
$RunScript = Join-Path $Root "scripts\run-scheduled.ps1"
$HealthScript = Join-Path $Root "scripts\health-check.ps1"
$Action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`"" `
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

$DailyHealthAction = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$HealthScript`"" `
    -WorkingDirectory $Root
$DailyHealthTrigger = New-ScheduledTaskTrigger -Daily -At "07:20"
Register-ScheduledTask `
    -TaskName "AutoDy-Health-Daily" `
    -Action $DailyHealthAction `
    -Trigger $DailyHealthTrigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Check Douyin login before daily AutoDy send" `
    -Force `
    -ErrorAction Stop | Out-Null

$WeeklyHealthTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Sunday `
    -At "20:00"
Register-ScheduledTask `
    -TaskName "AutoDy-Health-Weekly" `
    -Action $DailyHealthAction `
    -Trigger $WeeklyHealthTrigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Weekly Douyin login health reminder" `
    -Force `
    -ErrorAction Stop | Out-Null

$InstalledTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if (-not $InstalledTask.Settings.StartWhenAvailable) {
    throw "Scheduled task verification failed: StartWhenAvailable is disabled."
}

Write-Host "Scheduled task $TaskName installed for 07:30 local time."
