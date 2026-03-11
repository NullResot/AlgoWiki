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
    [string]$SuperadminPassword = "",
    [string]$ContentFile = "backend\\data\\attachment2.md",
    [switch]$Rebuild,
    [string]$SourceSqlitePath = "",
    [string]$FixturePath = "",
    [switch]$KeepFixture
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
        $DbPath = Join-Path $projectRoot "storage\\db_live.sqlite3"
    }

    $dbDir = Split-Path -Parent $DbPath
    if ($dbDir -and -not (Test-Path $dbDir)) {
        New-Item -ItemType Directory -Path $dbDir -Force | Out-Null
    }

    if ($Rebuild -and (Test-Path $DbPath)) {
        Remove-Item $DbPath -Force
    }
    if ($Rebuild -and (Test-Path "$DbPath-journal")) {
        Remove-Item "$DbPath-journal" -Force
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

    $env:MYSQL_BOOTSTRAP_HOST = $DbHost
    $env:MYSQL_BOOTSTRAP_PORT = "$DbPort"
    $env:MYSQL_BOOTSTRAP_USER = $DbUser
    $env:MYSQL_BOOTSTRAP_PASSWORD = $DbPassword
    $env:MYSQL_BOOTSTRAP_DATABASE = $DbName
    $env:MYSQL_BOOTSTRAP_REBUILD = if ($Rebuild) { "1" } else { "0" }

    @'
import os
import pymysql

host = os.environ["MYSQL_BOOTSTRAP_HOST"]
port = int(os.environ["MYSQL_BOOTSTRAP_PORT"])
user = os.environ["MYSQL_BOOTSTRAP_USER"]
password = os.environ.get("MYSQL_BOOTSTRAP_PASSWORD", "")
database = os.environ["MYSQL_BOOTSTRAP_DATABASE"]
rebuild = os.environ.get("MYSQL_BOOTSTRAP_REBUILD", "0") == "1"

conn = pymysql.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    charset="utf8mb4",
    autocommit=True,
)

try:
    with conn.cursor() as cursor:
        if rebuild:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
finally:
    conn.close()
'@ | venv\Scripts\python.exe -
    if ($LASTEXITCODE -ne 0) {
        throw "Create/check MySQL database failed. Exit code: $LASTEXITCODE"
    }
}

if ($script:loadedEnvFile) {
    Write-Output "Loaded env file: $EnvFile"
}

venv\Scripts\python.exe backend\manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) {
    throw "Database migrate failed. Exit code: $LASTEXITCODE"
}

if (-not [string]::IsNullOrWhiteSpace($SourceSqlitePath)) {
    if (-not (Test-Path $SourceSqlitePath)) {
        throw "Source sqlite database not found: $SourceSqlitePath"
    }
    if ($DbEngine -ne "mysql") {
        throw "SourceSqlitePath import is only supported when DbEngine=mysql."
    }

    if ([string]::IsNullOrWhiteSpace($FixturePath)) {
        $FixturePath = Join-Path $projectRoot "storage\\sqlite_to_mysql_fixture.json"
    }
    $fixtureDir = Split-Path -Parent $FixturePath
    if ($fixtureDir -and -not (Test-Path $fixtureDir)) {
        New-Item -ItemType Directory -Path $fixtureDir -Force | Out-Null
    }

    Write-Output "Exporting sqlite data from: $SourceSqlitePath"
    $env:DB_ENGINE = "sqlite"
    $env:SQLITE_NAME = $SourceSqlitePath
    Remove-Item $FixturePath -Force -ErrorAction SilentlyContinue
    venv\Scripts\python.exe backend\manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --indent 2 | Out-File -FilePath $FixturePath -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "Dump sqlite data failed. Exit code: $LASTEXITCODE"
    }

    Write-Output "Importing fixture to mysql: $FixturePath"
    $env:DB_ENGINE = "mysql"
    $env:DB_HOST = $DbHost
    $env:DB_PORT = "$DbPort"
    $env:DB_NAME = $DbName
    $env:DB_USER = $DbUser
    $env:DB_PASSWORD = $DbPassword
    Remove-Item Env:SQLITE_NAME -ErrorAction SilentlyContinue

    venv\Scripts\python.exe backend\manage.py loaddata $FixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Load fixture to mysql failed. Exit code: $LASTEXITCODE"
    }

    if (-not $KeepFixture -and (Test-Path $FixturePath)) {
        Remove-Item $FixturePath -Force
    }

    # Ensure superadmin password is known after cross-db import.
    venv\Scripts\python.exe backend\manage.py seed_initial_data `
        --skip-markdown-section-import `
        --skip-demo-users `
        --reset-superadmin-password `
        --superadmin-password $SuperadminPassword
    if ($LASTEXITCODE -ne 0) {
        throw "Reset superadmin password after import failed. Exit code: $LASTEXITCODE"
    }
} else {
    venv\Scripts\python.exe backend\manage.py seed_initial_data `
        --content-file $ContentFile `
        --reset-superadmin-password `
        --superadmin-password $SuperadminPassword
    if ($LASTEXITCODE -ne 0) {
        throw "Database seed failed. Exit code: $LASTEXITCODE"
    }
}

Write-Output ""
Write-Output "Database is ready."
Write-Output "Superadmin: superadmin / $SuperadminPassword"
