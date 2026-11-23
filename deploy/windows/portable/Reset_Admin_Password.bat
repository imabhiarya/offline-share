@echo off
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
cd /d "%~dp0"
call OfflineShare.cmd reset-password admin
pause
