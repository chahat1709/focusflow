@echo off
echo 🚀 Starting FocusFlow Dashboard...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python first.
    echo 📥 Download from: https://python.org
    pause
    exit /b 1
)

REM Start the server
echo 🌐 Starting web server...
python start_dashboard.py

pause
