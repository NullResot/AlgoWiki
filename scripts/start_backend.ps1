param(
    [ValidateSet("mysql", "sqlite")]
    [string]$DbEngine = "mysql",
    [string]$EnvFile = "",
    [string]$DbPath = "",
    [string]$DbHost = "",
    [int]$DbPort = 3306,
    [string]$DbName = "",
    [string]$DbUser = "",
    [string]$DbPassword = "",
    [string]$ServerHost = "127.0.0.1",
    [int]$Port = 8001,
    [switch]$SkipMigrate,
    [switch]$Background,
    [switch]$HealthCheck,
    [int]$HealthTimeoutSec = 20,
    [string]$PidFile = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$script:loadedEnvFile = $false
function Import-EnvFile {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            return
        }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            return
        }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            Set-Item -Path "Env:$key" -Value $value
        }
    }
    $script:loadedEnvFile = $true
}

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $defaultEnvFile = Join-Path $projectRoot "backend\.env"
    if (Test-Path $defaultEnvFile) {
        $EnvFile = $defaultEnvFile
    }
}
Import-EnvFile -Path $EnvFile

$DbEngine = if ($env:DB_ENGINE) { $env:DB_ENGINE } else { $DbEngine }
$DbEngine = $DbEngine.ToLowerInvariant()

if ($DbEngine -eq "sqlite") {
    if ([string]::IsNullOrWhiteSpace($DbPath) -and $env:SQLITE_NAME) {
        $DbPath = $env:SQLITE_NAME
    }
    if ([string]::IsNullOrWhiteSpace($DbPath)) {
        $DbPath = Join-Path $projectRoot "storage\db_live.sqlite3"
    }

    $dbDir = Split-Path -Parent $DbPath
    if ($dbDir -and -not (Test-Path $dbDir)) {
        New-Item -ItemType Directory -Path $dbDir -Force | Out-Null
    }

    $env:DB_ENGINE = "sqlite"
    $env:SQLITE_NAME = $DbPath

    Write-Output "DB_ENGINE=$env:DB_ENGINE"
    Write-Output "SQLITE_NAME=$env:SQLITE_NAME"
} else {
    if ([string]::IsNullOrWhiteSpace($DbHost)) { $DbHost = if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" } }
    if ($DbPort -eq 3306 -and $env:DB_PORT) { $DbPort = [int]$env:DB_PORT }
    if ([string]::IsNullOrWhiteSpace($DbName)) { $DbName = if ($env:DB_NAME) { $env:DB_NAME } else { "algowiki" } }
    if ([string]::IsNullOrWhiteSpace($DbUser)) { $DbUser = if ($env:DB_USER) { $env:DB_USER } else { "root" } }
    if ([string]::IsNullOrWhiteSpace($DbPassword) -and $env:DB_PASSWORD) { $DbPassword = $env:DB_PASSWORD }

    if ($DbName -notmatch "^[A-Za-z0-9_]+$") {
        throw "DB_NAME only supports letters, numbers, and underscore in this script."
    }

    $env:DB_ENGINE = "mysql"
    $env:DB_HOST = $DbHost
    $env:DB_PORT = "$DbPort"
    $env:DB_NAME = $DbName
    $env:DB_USER = $DbUser
    $env:DB_PASSWORD = $DbPassword
    Remove-Item Env:SQLITE_NAME -ErrorAction SilentlyContinue

    Write-Output "DB_ENGINE=$env:DB_ENGINE"
    Write-Output "DB_HOST=$env:DB_HOST"
    Write-Output "DB_PORT=$env:DB_PORT"
    Write-Output "DB_NAME=$env:DB_NAME"
    Write-Output "DB_USER=$env:DB_USER"
}

if ($script:loadedEnvFile) {
    Write-Output "Loaded env file: $EnvFile"
}

if (-not $SkipMigrate) {
    venv\Scripts\python.exe backend\manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        throw "Database migrate failed. Exit code: $LASTEXITCODE"
    }
}

$pythonExe = Join-Path $projectRoot "venv\Scripts\python.exe"
$managePy = Join-Path $projectRoot "backend\manage.py"
$runserverArgs = @($managePy, "runserver", "$ServerHost`:$Port")

if ($Background) {
    # Background mode avoids blocking the current terminal; --noreload prevents double process.
    $process = Start-Process -FilePath $pythonExe -ArgumentList ($runserverArgs + "--noreload") -PassThru -WorkingDirectory $projectRoot
    Write-Output "Backend started in background. PID=$($process.Id) URL=http://$ServerHost`:$Port/"

    if (-not [string]::IsNullOrWhiteSpace($PidFile)) {
        $pidDir = Split-Path -Parent $PidFile
        if ($pidDir -and -not (Test-Path $pidDir)) {
            New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        }
        Set-Content -Path $PidFile -Value $process.Id -Encoding ascii
        Write-Output "PID saved: $PidFile"
    }

    if ($HealthCheck) {
        $probeUrls = @(
            "http://$ServerHost`:$Port/api/health/",
            "http://$ServerHost`:$Port/admin/login/"
        )
        $ok = $false
        $deadline = (Get-Date).AddSeconds([Math]::Max(1, $HealthTimeoutSec))
        while ((Get-Date) -lt $deadline) {
            $allReachable = $true
            foreach ($url in $probeUrls) {
                try {
                    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
                    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 500) {
                        $allReachable = $false
                        break
                    }
                } catch {
                    $allReachable = $false
                    break
                }
            }
            if ($allReachable) {
                $ok = $true
                break
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ok) {
            throw "Backend started (PID=$($process.Id)) but health check failed within ${HealthTimeoutSec}s."
        }
        Write-Output "Health check passed: /api/health/ and /admin/login/ are reachable."
    }

    return
}

venv\Scripts\python.exe @runserverArgs
