@echo off
setlocal EnableDelayedExpansion
title OFFLINE SHARE - Server Setup
cd /d "%~dp0"
net session >nul 2>&1 || (echo. & echo  Please right-click Install.bat and choose "Run as administrator". & echo. & pause & exit /b 1)

echo ================================================================
echo   OFFLINE SHARE - Local Data Transfer System (LAN) - Server Setup
echo ================================================================
echo.
for /f "tokens=1,2" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0detect_network.ps1"') do (set "DIP=%%a" & set "DNET=%%b")
if "%DIP%"=="" set "DIP=192.168.50.10"
if "%DNET%"=="" set "DNET=192.168.50.0/24"
echo  Detected this PC: IP %DIP%   network %DNET%
echo  Press Enter to accept a value shown in [brackets].
echo.
set "IP=%~1"
set "PORT=%~2"
set "SUBNET=%~3"
if "%IP%"=="" set /p "IP=  Server IP address [%DIP%]: "
if "%IP%"=="" set "IP=%DIP%"
if "%PORT%"=="" set /p "PORT=  Port [5000]: "
if "%PORT%"=="" set "PORT=5000"
if "%SUBNET%"=="" set /p "SUBNET=  Allowed LAN network [%DNET%]: "
if "%SUBNET%"=="" set "SUBNET=%DNET%"
echo.

echo [1/6] Saving configuration (%IP%:%PORT%, allowed %SUBNET%) ...
call "%~dp0OfflineShare.cmd" configure --ip %IP% --port %PORT% --subnet %SUBNET% || goto :fail

echo [2/6] Creating data folders and database in %ProgramData%\OfflineShare ...
call "%~dp0OfflineShare.cmd" init >nul || goto :fail

echo [3/6] Windows Firewall: allowing TCP %PORT% from %SUBNET% only ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0configure_firewall.ps1" -Port %PORT% -Subnet %SUBNET% || goto :fail

echo [4/6] Registering automatic start with Windows ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task.ps1" -InstallDir "%~dp0." || goto :fail

echo [5/6] Starting the server ...
powershell -NoProfile -Command "Start-ScheduledTask -TaskName OfflineShare" || goto :fail

echo [6/6] Waiting for the server to answer ...
set OK=
for /l %%i in (1,1,30) do (
  if not defined OK (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:%PORT%/api/health; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" && set OK=1
    if not defined OK timeout /t 1 /nobreak >nul
  )
)
if not defined OK (
  echo.
  echo  The server did not answer within 30 seconds.
  echo  Check the log: %ProgramData%\OfflineShare\logs\offline_share.log
  echo  Or run in a window to see errors:  OfflineShare.cmd serve
  goto :fail
)

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell); $l=$s.CreateShortcut([Environment]::GetFolderPath('CommonDesktopDirectory')+'\OFFLINE SHARE.url'); $l.TargetPath='http://127.0.0.1:%PORT%/'; $l.Save()" >nul 2>&1

echo.
echo ================================================================
echo   OFFLINE SHARE is running and will start automatically with Windows.
echo.
echo   On THIS PC open :  http://127.0.0.1:%PORT%
echo   On other PCs    :  http://%IP%:%PORT%
echo   Health page     :  http://%IP%:%PORT%/health
echo ================================================================
if exist "%ProgramData%\OfflineShare\INITIAL_ADMIN_PASSWORD.txt" (
  echo.
  type "%ProgramData%\OfflineShare\INITIAL_ADMIN_PASSWORD.txt"
  echo  ^(This file is in %ProgramData%\OfflineShare - delete it after signing in.^)
)
echo.
if /i not "%~4"=="/nopause" pause
start "" http://127.0.0.1:%PORT%/
exit /b 0

:fail
echo.
echo  *** Setup failed. See messages above. ***
if /i not "%~4"=="/nopause" pause
exit /b 1
