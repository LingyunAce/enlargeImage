# Run the EnlargeImage backend.
# Closing this window (X button, Ctrl+C, etc.) automatically kills the backend
# because the backend is launched inside a Windows Job Object.
# Usage: .\run.ps1 [--no-models-ok] [--port 9000] ...

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$wrapper = Join-Path $scriptDir "backend\run_with_job.ps1"

if (-not (Test-Path $wrapper)) {
    Write-Error "run_with_job.ps1 not found at $wrapper"
    exit 1
}

# Pass all args through
& $wrapper @args
