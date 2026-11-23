@echo off
REM ====================================================================
REM  Builds OFFLINE_SHARE_Server_Setup.exe and OFFLINE_SHARE_Client_Agent_Setup.exe
REM  on a Windows build PC. Requires: Python 3.12 x64, Node.js 20+, Inno Setup 6.
REM  Run from the repository root:  deploy\windows\build_windows.bat
REM ====================================================================
setlocal
cd /d "%~dp0\..\.."
echo [1/5] Frontend build
pushd frontend && call npm ci && call npm run build || (popd & goto :fail)
popd
echo [2/5] Python environment
py -3.12 -m venv .build-venv || goto :fail
call .build-venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt pyinstaller || goto :fail
echo [3/5] Tests
pip install pytest httpx && python -m pytest -q backend\tests || goto :fail
echo [4/5] PyInstaller
pyinstaller deploy\windows\offline_share_server.spec --noconfirm --distpath build\dist --workpath build\work || goto :fail
pyinstaller deploy\windows\offline_share_agent.spec --noconfirm --distpath build\dist --workpath build\work-agent || goto :fail
echo [5/5] Installers (Inno Setup)
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
"%ISCC%" deploy\windows\OFFLINE_SHARE_Server_Setup.iss || goto :fail
"%ISCC%" deploy\windows\OFFLINE_SHARE_Client_Agent_Setup.iss || goto :fail
echo.
echo Done. Installers are in build\installer\
exit /b 0
:fail
echo BUILD FAILED
exit /b 1
