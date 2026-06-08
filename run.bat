@echo off
setlocal

rem Run the EnlargeImage backend using the project's virtualenv.
rem Forwards all arguments to run.py. Double-click or invoke from cmd/PowerShell.

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%backend\.venv\Scripts\python.exe"
set "RUN_PY=%SCRIPT_DIR%backend\run.py"

if not exist "%VENV_PY%" (
    echo ERROR: Python venv not found at:
    echo   %VENV_PY%
    echo.
    echo Run setup first:
    echo   cd backend
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   Invoke-WebRequest -Uri "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth" -OutFile models\SwinIR_REALSR_X4.pth
    exit /b 1
)

if not exist "%RUN_PY%" (
    echo ERROR: run.py not found at:
    echo   %RUN_PY%
    exit /b 1
)

"%VENV_PY%" "%RUN_PY%" %*
