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

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily Douyin spark message" `
    -Force

Write-Host "Scheduled task $TaskName installed for 07:30 local time."
