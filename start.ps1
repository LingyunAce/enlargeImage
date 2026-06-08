# Start both EnlargeImage backend and frontend in separate windows.
# Backend: http://localhost:8000
# Frontend: http://localhost:3000

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting EnlargeImage backend (new window)..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$scriptDir`" && call run.bat" `
    -WindowTitle "EnlargeImage Backend"

Write-Host "Starting EnlargeImage frontend (new window)..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$scriptDir\frontend`" && npm run dev" `
    -WindowTitle "EnlargeImage Frontend"

Write-Host ""
Write-Host "Both services are starting in separate windows."
Write-Host "  Backend:  http://localhost:8000  (API + Swagger at /docs)"
Write-Host "  Frontend: http://localhost:3000"
Write-Host ""
Write-Host "Close the individual windows to stop each service."
