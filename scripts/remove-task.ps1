$ErrorActionPreference = "Stop"
$TaskName = "AutoDy-DailySpark"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Scheduled task $TaskName removed."
} else {
    Write-Host "Scheduled task $TaskName is not installed."
}
