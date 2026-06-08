@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

echo Starting EnlargeImage backend (new window)...
start "EnlargeImage Backend" cmd /k "cd /d "%SCRIPT_DIR%" && call run.bat"

echo Starting EnlargeImage frontend (new window)...
start "EnlargeImage Frontend" cmd /k "cd /d "%SCRIPT_DIR%frontend" && npm run dev"

echo.
echo Both services are starting in separate windows.
echo   Backend:  http://localhost:8000  (API + Swagger at /docs)
echo   Frontend: http://localhost:3000
echo.
echo Close the individual windows to stop each service.
endlocal
