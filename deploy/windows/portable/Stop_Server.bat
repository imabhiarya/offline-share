@echo off
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName OfflineShare; Start-Sleep 2; (Get-ScheduledTask -TaskName OfflineShare).State"
pause
