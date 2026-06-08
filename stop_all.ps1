# stop_all.ps1
# Kill any EnlargeImage backend or frontend processes that are still running.
# Use this when the normal window-close path didn't clean up.

Write-Host "Killing EnlargeImage backend (python) processes..."
Get-Process python* -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*enlargeimage*" -or
    $_.CommandLine -like "*EnlargeImage*" -or
    $_.CommandLine -like "*run.py*" -or
    $_.CommandLine -like "*uvicorn*"
} | ForEach-Object {
    Write-Host "  PID $($_.Id)  $($_.ProcessName)  started $($_.StartTime)"
    Stop-Process -Id $_.Id -Force
}

Write-Host ""
Write-Host "Killing EnlargeImage frontend (node/next) processes on port 3000..."
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($p) {
        Write-Host "  PID $($p.Id)  $($p.ProcessName)  on port 3000"
        Stop-Process -Id $p.Id -Force
    }
}

Write-Host ""
Write-Host "Done. Port 8000 and 3000 should now be free."
