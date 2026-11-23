@echo off
REM Removes the startup task and firewall rule. Data in %ProgramData%\OfflineShare is KEPT unless you pass /purge.
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName OfflineShare -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName OfflineShare -Confirm:$false -ErrorAction SilentlyContinue; Get-NetFirewallRule -DisplayName 'OFFLINE SHARE*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule" >nul 2>&1
del "%PUBLIC%\Desktop\OFFLINE SHARE.url" >nul 2>&1
if /i "%~1"=="/purge" (rmdir /s /q "%ProgramData%\OfflineShare" & echo Data deleted.) else (echo Data kept in %ProgramData%\OfflineShare)
echo OFFLINE SHARE startup task and firewall rule removed.
if /i not "%~2"=="/nopause" pause
