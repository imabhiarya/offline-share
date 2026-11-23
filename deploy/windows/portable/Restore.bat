@echo off
REM Usage: Restore.bat "D:\Backups\offline_share_manual_YYYYMMDD_HHMMSS.zip"   (a safety backup is taken first)
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
cd /d "%~dp0"
if "%~1"=="" (echo Usage: Restore.bat path\to\backup.zip & pause & exit /b 1)
echo This replaces ALL current OFFLINE SHARE data with "%~1".
set /p "OK=Type YES to continue: "
if /i not "%OK%"=="YES" exit /b 1
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName OfflineShare" >nul 2>&1
timeout /t 3 /nobreak >nul
call OfflineShare.cmd restore "%~1"
powershell -NoProfile -Command "Start-ScheduledTask -TaskName OfflineShare"
pause
