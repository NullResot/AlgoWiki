param(
    [string]$ServerHost = "139.224.212.247",
    [string]$ServerUser = "root",
    [int]$ServerPort = 22,
    [string]$ServerProjectDir = "/srv/algowiki",
    [string]$EnvFile = "deploy/.env.test",
    [string]$ImageName = "algowiki-web-test",
    [string]$Tag = "",
    [string]$Release = "",
    [string]$RemoteArchiveDir = "/root",
    [string]$SshKeyPath = "",
    [switch]$NoCache,
    [switch]$KeepRemoteArchive
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$baseScript = Join-Path $PSScriptRoot "quick-release-to-server.ps1"

if (-not $Tag) {
    $gitSha = ""
    try {
        $gitSha = (git -C $projectRoot rev-parse --short HEAD).Trim()
    } catch {
        $gitSha = ""
    }

    if ($gitSha) {
        $Tag = "test-$gitSha"
    } else {
        $Tag = "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    }
}

if (-not $Release) {
    $Release = "quick-test-$Tag"
}

$forwardArgs = @{
    ServerHost = $ServerHost
    ServerUser = $ServerUser
    ServerPort = $ServerPort
    ServerProjectDir = $ServerProjectDir
    EnvFile = $EnvFile
    ImageName = $ImageName
    Tag = $Tag
    Release = $Release
    RemoteArchiveDir = $RemoteArchiveDir
    SshKeyPath = $SshKeyPath
}

if ($NoCache) {
    $forwardArgs.NoCache = $true
}

if ($KeepRemoteArchive) {
    $forwardArgs.KeepRemoteArchive = $true
}

Write-Host ("[test-fast] Forwarding to {0}" -f $baseScript)
& $baseScript @forwardArgs
