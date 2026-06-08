@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "WRAPPER=%SCRIPT_DIR%backend\run_with_job.ps1"

if not exist "%WRAPPER%" (
    echo ERROR: run_with_job.ps1 not found at %WRAPPER%
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%WRAPPER%" %*
