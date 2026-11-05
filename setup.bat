@echo off
rem Windows: double-click to install the skill. Runs setup.ps1, then keeps the window open.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
pause
