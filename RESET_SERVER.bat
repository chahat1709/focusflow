@echo off
echo.
echo ═══ FOCUSFLOW RESET UTILITY ═══
echo.
echo [1/2] Killing any hanging Python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM production_server.exe /T 2>nul
echo.
echo [2/2] Starting Fresh Server...
echo.
echo Dashboard will open at: http://localhost:5077
start http://localhost:5077
python production_server.py
pause
