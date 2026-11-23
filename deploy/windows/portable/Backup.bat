@echo off
REM Consistent backup (database + files) while the server keeps running.   Usage: Backup.bat [folder] [--no-files]
cd /d "%~dp0"
if "%~1"=="" (call OfflineShare.cmd backup) else (call OfflineShare.cmd backup --dir "%~1" %2)
pause
