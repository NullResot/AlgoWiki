$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $projectRoot "frontend")

npm run dev
