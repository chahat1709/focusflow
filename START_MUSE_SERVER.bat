@echo off
echo ============================================================
echo   FocusFlow — BlueMuse EEG Server
echo ============================================================
echo.
echo  BEFORE running this, make sure:
echo.
echo  1. BlueMuse is OPEN and your Muse 2 is connected.
echo  2. Click "Start Streaming" in BlueMuse.
echo  3. Then come back here and press any key.
echo.
pause
echo.
echo Starting server ...
python production_server.py
pause
