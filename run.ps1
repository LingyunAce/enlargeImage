# Run the EnlargeImage backend using the project's virtualenv.
# Forwards all arguments to run.py.
# Usage: .\run.ps1 [--no-models-ok] [--port 9000] ...

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPy = Join-Path $scriptDir "backend\.venv\Scripts\python.exe"
$runPy = Join-Path $scriptDir "backend\run.py"

if (-not (Test-Path $venvPy)) {
    Write-Error "Python venv not found at: $venvPy"
    Write-Host ""
    Write-Host "Run setup first:"
    Write-Host "  cd backend"
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\pip install -r requirements.txt"
    Write-Host "  Invoke-WebRequest -Uri 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth' -OutFile models\SwinIR_REALSR_X4.pth"
    exit 1
}

if (-not (Test-Path $runPy)) {
    Write-Error "run.py not found at: $runPy"
    exit 1
}

& $venvPy $runPy @args
