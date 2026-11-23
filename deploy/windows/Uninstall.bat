@echo off
REM Removes the service and firewall rule. Data in %ProgramData%\OfflineShare is KEPT
REM unless you pass /purge (take a backup first!).
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
cd /d "%~dp0"
sc stop OfflineShare >nul 2>&1
timeout /t 3 /nobreak >nul
OfflineShare.exe service remove
powershell -NoProfile -Command "Get-NetFirewallRule -DisplayName 'OFFLINE SHARE*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule"
if /i "%~1"=="/purge" (
  echo Deleting %ProgramData%\OfflineShare ...
  rmdir /s /q "%ProgramData%\OfflineShare"
) else (
  echo Data kept in %ProgramData%\OfflineShare
)
echo OFFLINE SHARE service removed.
pause
