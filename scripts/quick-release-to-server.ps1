param(
    [string]$ServerHost = "139.224.212.247",
    [string]$ServerUser = "root",
    [int]$ServerPort = 22,
    [string]$ServerProjectDir = "/srv/algowiki",
    [string]$EnvFile = "deploy/.env.production",
    [string]$ImageName = "algowiki-web",
    [string]$Tag = "",
    [string]$Release = "",
    [string]$RemoteArchiveDir = "/root",
    [string]$SshKeyPath = "",
    [switch]$NoCache,
    [switch]$KeepRemoteArchive
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $projectRoot "scripts\build_server_image.ps1"
$archiveUpdateScript = Join-Path $projectRoot "deploy\server-update-from-archive.sh"
$composeScript = Join-Path $projectRoot "deploy\server-compose-up.sh"
$composeFile = Join-Path $projectRoot "docker-compose.server.yml"

if (-not $Tag) {
    $gitSha = ""
    try {
        $gitSha = (git -C $projectRoot rev-parse --short HEAD).Trim()
    } catch {
        $gitSha = ""
    }

    if ($gitSha) {
        $Tag = "quick-$gitSha"
    } else {
        $Tag = Get-Date -Format "yyyyMMdd-HHmmss"
    }
}

if (-not $Release) {
    $Release = "archive-$Tag"
}

$archiveDir = Join-Path $projectRoot "storage\deploy"
$archivePath = Join-Path $archiveDir ("{0}-{1}.tar" -f $ImageName, $Tag)
$remoteArchivePath = "{0}/{1}" -f $RemoteArchiveDir.TrimEnd('/'), (Split-Path -Leaf $archivePath)
$imageRef = "{0}:{1}" -f $ImageName, $Tag

$buildArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $buildScript,
    "-ImageName", $ImageName,
    "-Tag", $Tag,
    "-OutputDir", $archiveDir
)

if ($NoCache) {
    $buildArgs += "-NoCache"
}

Write-Host ("[1/4] Building image {0}" -f $imageRef)
& powershell @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw ("build_server_image.ps1 failed with exit code {0}" -f $LASTEXITCODE)
}

$scpCommonArgs = @("-P", $ServerPort.ToString())
if ($SshKeyPath) {
    $scpCommonArgs += @("-i", $SshKeyPath)
}

Write-Host ("[2/4] Uploading image archive to {0}@{1}" -f $ServerUser, $ServerHost)
& scp @scpCommonArgs $archivePath ("{0}@{1}:{2}/" -f $ServerUser, $ServerHost, $RemoteArchiveDir)
if ($LASTEXITCODE -ne 0) {
    throw ("scp image archive failed with exit code {0}" -f $LASTEXITCODE)
}

Write-Host ("[3/4] Uploading deployment helpers to server project directory")
& scp @scpCommonArgs $archiveUpdateScript ("{0}@{1}:{2}/deploy/" -f $ServerUser, $ServerHost, $ServerProjectDir)
if ($LASTEXITCODE -ne 0) {
    throw ("scp archive update script failed with exit code {0}" -f $LASTEXITCODE)
}
& scp @scpCommonArgs $composeScript ("{0}@{1}:{2}/deploy/" -f $ServerUser, $ServerHost, $ServerProjectDir)
if ($LASTEXITCODE -ne 0) {
    throw ("scp compose helper failed with exit code {0}" -f $LASTEXITCODE)
}
& scp @scpCommonArgs $composeFile ("{0}@{1}:{2}/" -f $ServerUser, $ServerHost, $ServerProjectDir)
if ($LASTEXITCODE -ne 0) {
    throw ("scp compose file failed with exit code {0}" -f $LASTEXITCODE)
}

$cleanupFlag = ""
if (-not $KeepRemoteArchive) {
    $cleanupFlag = " --cleanup-archive"
}

$remoteCommand = @(
    "set -euo pipefail",
    ("cd {0}" -f $ServerProjectDir),
    "chmod +x deploy/server-compose-up.sh deploy/server-update-from-archive.sh",
    ("./deploy/server-update-from-archive.sh --env-file {0} --archive {1} --image {2} --release {3}{4}" -f $EnvFile, $remoteArchivePath, $imageRef, $Release, $cleanupFlag)
) -join "; "

$sshArgs = @("-p", $ServerPort.ToString())
if ($SshKeyPath) {
    $sshArgs += @("-i", $SshKeyPath)
}

Write-Host ("[4/4] Updating server containers")
& ssh @sshArgs ("{0}@{1}" -f $ServerUser, $ServerHost) $remoteCommand
if ($LASTEXITCODE -ne 0) {
    throw ("remote update failed with exit code {0}" -f $LASTEXITCODE)
}

Write-Host ""
Write-Host ("Finished quick release: {0}" -f $imageRef)
Write-Host ("Release label: {0}" -f $Release)
