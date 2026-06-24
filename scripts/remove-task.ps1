$ErrorActionPreference = "Stop"
$TaskNames = @("AutoDy-DailySpark", "AutoDy-Health-Daily", "AutoDy-Health-Weekly")

foreach ($TaskName in $TaskNames) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Scheduled task $TaskName removed."
    }
}
