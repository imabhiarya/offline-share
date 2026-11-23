@echo off
REM Runs the OFFLINE SHARE command line with the bundled Python (no Python install needed).
REM Examples:  OfflineShare.cmd init      OfflineShare.cmd backup      OfflineShare.cmd reset-password admin
"%~dp0python\python.exe" "%~dp0backend\offline_share.py" %*
