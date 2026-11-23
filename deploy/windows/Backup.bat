@echo off
REM Creates a consistent backup (database + stored files) while the server keeps running.
REM Usage: Backup.bat [target-folder] [--no-files]
cd /d "%~dp0"
if "%~1"=="" (OfflineShare.exe backup) else (OfflineShare.exe backup --dir "%~1" %2)
pause
