@echo off
net session >nul 2>&1 || (echo Run as administrator. & pause & exit /b 1)
sc stop OfflineShare
timeout /t 3 /nobreak >nul
sc query OfflineShare | find "STATE"
