@echo off
REM Restores a backup .zip created by OFFLINE SHARE. A safety backup is taken first.
REM Usage: Restore.bat "D:\Backups\offline_share_manual_20261123_200000.zip"
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
cd /d "%~dp0"
if "%~1"=="" (echo Usage: Restore.bat path\to\backup.zip & pause & exit /b 1)
echo This replaces ALL current OFFLINE SHARE data with "%~1".
set /p "OK=Type YES to continue: "
if /i not "%OK%"=="YES" exit /b 1
sc stop OfflineShare >nul 2>&1
timeout /t 4 /nobreak >nul
OfflineShare.exe restore "%~1"
sc start OfflineShare
pause
