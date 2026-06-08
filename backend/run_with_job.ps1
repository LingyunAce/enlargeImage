# run_with_job.ps1
# Wrapper that runs run.py inside a Windows Job Object.
# Closing this window kills the backend (and any subprocesses uvicorn spawned).

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunArgs = @()
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPy = Join-Path $scriptDir ".venv\Scripts\python.exe"
$runPy = Join-Path $scriptDir "run.py"

if (-not (Test-Path $venvPy)) {
    Write-Error "venv not found at $venvPy"
    exit 1
}
if (-not (Test-Path $runPy)) {
    Write-Error "run.py not found at $runPy"
    exit 1
}

# Run in job
& "$scriptDir\_job.ps1" -FilePath $venvPy -ArgumentList (@($runPy) + $RunArgs) -WorkingDirectory $scriptDir
