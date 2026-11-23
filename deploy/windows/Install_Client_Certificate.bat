@echo off
REM Run on each CLIENT PC as Administrator, in the folder containing OfflineShare-RootCA.cer.
REM Adds the OFFLINE SHARE internal CA to "Trusted Root Certification Authorities" (Chrome and Edge use it).
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
certutil -addstore -f Root "%~dp0OfflineShare-RootCA.cer" && echo Certificate installed. Restart Chrome/Edge.
pause
