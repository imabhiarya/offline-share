@echo off
REM ====================================================================
REM  OFFLINE SHARE - server installation (run as Administrator)
REM  Usage: Install.bat [SERVER_IP] [PORT] [SUBNET]
REM  Defaults: 192.168.50.10 5000 192.168.50.0/24
REM ====================================================================
setlocal
cd /d "%~dp0"
net session >nul 2>&1 || (echo Please right-click Install.bat and choose "Run as administrator". & pause & exit /b 1)

set "IP=%~1"
set "PORT=%~2"
set "SUBNET=%~3"
if "%IP%"=="" set /p "IP=Server static IP [192.168.50.10]: "
if "%IP%"=="" set "IP=192.168.50.10"
if "%PORT%"=="" set /p "PORT=Port [5000]: "
if "%PORT%"=="" set "PORT=5000"
if "%SUBNET%"=="" set /p "SUBNET=LAN subnet [192.168.50.0/24]: "
if "%SUBNET%"=="" set "SUBNET=192.168.50.0/24"

echo.
echo [1/6] Writing configuration ...
OfflineShare.exe configure --ip %IP% --port %PORT% --subnet %SUBNET% || goto :fail

echo [2/6] Creating data folders and database (C:\ProgramData\OfflineShare) ...
OfflineShare.exe init || goto :fail

echo [3/6] Configuring Windows Firewall (TCP %PORT% from %SUBNET% only) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0configure_firewall.ps1" -Port %PORT% -Subnet %SUBNET% || goto :fail

echo [4/6] Installing Windows Service "OfflineShare" (automatic start) ...
OfflineShare.exe service install || goto :fail

echo [5/6] Starting service ...
OfflineShare.exe service start || goto :fail
timeout /t 4 /nobreak >nul

echo [6/6] Checking health ...
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%PORT%/api/health).Content } catch { Write-Host 'Health check failed:' $_ ; exit 1 }"

echo.
echo ====================================================================
echo  OFFLINE SHARE is running.  Client PCs open:  http://%IP%:%PORT%
echo  Health page:  http://%IP%:%PORT%/health
if exist "%ProgramData%\OfflineShare\INITIAL_ADMIN_PASSWORD.txt" (
  echo.
  type "%ProgramData%\OfflineShare\INITIAL_ADMIN_PASSWORD.txt"
)
echo ====================================================================
pause
exit /b 0
:fail
echo Installation failed. See %ProgramData%\OfflineShare\logs\offline_share.log
pause
exit /b 1
