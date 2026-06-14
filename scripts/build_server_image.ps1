param(
    [string]$ImageName = "algowiki-web",
    [string]$Tag = "",
    [string]$OutputDir = "",
    [string]$FrontendBaseImage = "",
    [string]$BackendBaseImage = "",
    [switch]$NoCache,
    [switch]$NoSave
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $Tag) {
    $Tag = Get-Date -Format "yyyyMMdd-HHmmss"
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $projectRoot "storage\deploy"
}

$imageRef = "{0}:{1}" -f $ImageName, $Tag

$buildArgs = @(
    "build",
    "-f", (Join-Path $projectRoot "Dockerfile"),
    "-t", $imageRef
)

if ($NoCache) {
    $buildArgs += "--no-cache"
}

if ($FrontendBaseImage) {
    $buildArgs += @("--build-arg", ("FRONTEND_BASE_IMAGE={0}" -f $FrontendBaseImage))
}

if ($BackendBaseImage) {
    $buildArgs += @("--build-arg", ("BACKEND_BASE_IMAGE={0}" -f $BackendBaseImage))
}

$viteBuildArgNames = @(
    "VITE_TURNSTILE_SITE_KEY",
    "VITE_SECONDARY_CAPTCHA_ENABLED",
    "VITE_SECONDARY_CAPTCHA_PROVIDER",
    "VITE_GEETEST_CAPTCHA_ID"
)

foreach ($name in $viteBuildArgNames) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($null -ne $value -and $value -ne "") {
        $buildArgs += @("--build-arg", ("{0}={1}" -f $name, $value))
    }
}

$buildArgs += $projectRoot

& docker @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw ("docker build failed with exit code {0}" -f $LASTEXITCODE)
}

if (-not $NoSave) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $archivePath = Join-Path $OutputDir ("{0}-{1}.tar" -f $ImageName, $Tag)
    & docker save -o $archivePath $imageRef
    if ($LASTEXITCODE -ne 0) {
        throw ("docker save failed with exit code {0}" -f $LASTEXITCODE)
    }
    Write-Host ("Saved image archive: {0}" -f $archivePath)
}

Write-Host ("Built image: {0}" -f $imageRef)
