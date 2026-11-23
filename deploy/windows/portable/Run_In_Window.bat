@echo off
REM Troubleshooting: runs the server in this window so you can see errors. Stop the background task first (Stop_Server.bat).
cd /d "%~dp0"
call "%~dp0OfflineShare.cmd" serve
pause
