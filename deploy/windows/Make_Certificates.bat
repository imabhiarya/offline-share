@echo off
REM Creates the internal root CA + server certificate and switches the server to HTTPS.
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
cd /d "%~dp0"
OfflineShare.exe make-certs || (pause & exit /b 1)
sc stop OfflineShare >nul 2>&1
timeout /t 4 /nobreak >nul
sc start OfflineShare
echo.
echo Copy %ProgramData%\OfflineShare\certs\OfflineShare-RootCA.cer to each client PC and run
echo   Install_Client_Certificate.bat  (see Network Configuration Guide).
pause
