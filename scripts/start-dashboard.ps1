param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
    [string]$PythonPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ProjectPython = if ($PythonPath) { $PythonPath } else { Join-Path $ProjectRoot ".venv\Scripts\python.exe" }
$Config = Join-Path $ProjectRoot "config.yaml"
$PackagePath = Join-Path $ProjectRoot "src\autody"
$LogDirectory = Join-Path $ProjectRoot "data\logs"
$DiagnosticLog = Join-Path $LogDirectory "dashboard-launcher.log"
$StandardOutput = Join-Path $LogDirectory "dashboard-launcher.stdout.log"
$StandardError = Join-Path $LogDirectory "dashboard-launcher.stderr.log"
$Url = "http://127.0.0.1:8765"
$env:AUTODY_HOME = $ProjectRoot
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $ProjectRoot "data\ms-playwright"
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"

function Write-Diagnostic {
    param([string]$Message)
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" | Add-Content -LiteralPath $DiagnosticLog -Encoding UTF8
}

function Fail-Launch {
    param([string]$Stage, [string]$Message, [int]$ExitCode = 1)
    Write-Diagnostic "FAIL ${Stage}: $Message"
    Write-Host "AutoDy dashboard failed during: $Stage" -ForegroundColor Red
    Write-Host $Message -ForegroundColor Red
    Write-Host "Diagnostic log: $DiagnosticLog"
    Read-Host "Press Enter to close this window" | Out-Null
    exit $ExitCode
}

function Get-ServiceIdentity {
    try {
        return Invoke-RestMethod -Uri "$Url/api/service-identity" -TimeoutSec 2 -ErrorAction Stop
    } catch {
        return $null
    }
}

function Get-PortConnection {
    try {
        return Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction Stop | Select-Object -First 1
    } catch {
        return $null
    }
}

function Test-CurrentProjectIdentity {
    param($Identity)
    if ($null -eq $Identity -or $Identity.application -ne "AutoDy") {
        return $false
    }
    try {
        $identityRoot = [IO.Path]::GetFullPath([string]$Identity.project_path).TrimEnd('\\')
        $identityPackage = [IO.Path]::GetFullPath([string]$Identity.package_path).TrimEnd('\\')
        $expectedRoot = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\\')
        $expectedPackage = [IO.Path]::GetFullPath($PackagePath).TrimEnd('\\')
        return $identityRoot -eq $expectedRoot -and $identityPackage -eq $expectedPackage
    } catch {
        return $false
    }
}

function Stop-ConfirmedAutoDyService {
    param($Connection, $Identity)
    if ($null -eq $Connection -or $null -eq $Identity -or $Identity.application -ne "AutoDy") {
        return $false
    }
    Write-Diagnostic "Stopping confirmed stale AutoDy listener PID $($Connection.OwningProcess)."
    Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 250
        if ($null -eq (Get-PortConnection)) {
            return $true
        }
    }
    return $false
}

if (-not (Test-Path -LiteralPath $ProjectPython -PathType Leaf)) {
    Fail-Launch "project runtime check" "Project Python was not found: $ProjectPython"
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    Fail-Launch "configuration check" "AutoDy configuration was not found: $Config"
}

$connection = Get-PortConnection
$identity = Get-ServiceIdentity
if (Test-CurrentProjectIdentity $identity) {
    Start-Process "$Url"
    exit 0
}
if ($null -ne $connection) {
    if (-not (Stop-ConfirmedAutoDyService -Connection $connection -Identity $identity)) {
        Fail-Launch "port check" "Port 8765 is occupied by an unrelated application (PID $($connection.OwningProcess))."
    }
}

try {
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    Remove-Item -LiteralPath $StandardOutput, $StandardError -Force -ErrorAction SilentlyContinue
    $process = Start-Process -FilePath $ProjectPython `
        -ArgumentList @("-m", "autody.cli", "ui", "--no-open", "--config", $Config) `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $StandardOutput `
        -RedirectStandardError $StandardError `
        -WindowStyle Hidden `
        -PassThru
    Write-Diagnostic "Started AutoDy service PID $($process.Id)."
} catch {
    Fail-Launch "service start" $_.Exception.Message
}

for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    $identity = Get-ServiceIdentity
    if (Test-CurrentProjectIdentity $identity) {
        Start-Process "$Url"
        exit 0
    }
    if ($process.HasExited) {
        Fail-Launch "service start" "AutoDy exited with code $($process.ExitCode)."
    }
}

Fail-Launch "startup timeout" "AutoDy did not respond on port 8765 within 10 seconds."
