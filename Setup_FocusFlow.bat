@echo off
Title Focus Flow Settings
color 0b

echo ===================================================
echo      FOCUS FLOW - PROFESSIONAL INSTALLER
echo ===================================================
echo.
echo [1/4] Checking System Requirements...

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ! Python not found. Downloading Python 3.12 installer...
    curl -o python_installer.exe https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe
    echo    ! Installing Python (Please click 'Install Now' and 'Add to PATH' in the window)...
    start /wait python_installer.exe
    del python_installer.exe
    echo    + Python Installed.
) else (
    echo    + Python is already installed.
)

echo.
echo [2/4] Installing Application Dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo    ! Identifying missing pip... trying ensurepip...
    python -m ensurepip
    python -m pip install -r requirements.txt
)

echo.
echo [3/4] Creating Desktop Shortcut...
set SCRIPT="%TEMP%\CreateShortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\Focus Flow.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%~dp0start_app_monolith.py" >> %SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %SCRIPT%
echo oLink.Description = "Launch Focus Flow" >> %SCRIPT%
echo oLink.IconLocation = "%~dp0assets\icon.ico" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%
cscript /nologo %SCRIPT%
del %SCRIPT%
echo    + Shortcut created on Desktop.

echo.
echo [4/4] Installation Complete!
echo.
echo ===================================================
echo    Ready to Launch!
echo    You can now open 'Focus Flow' from your Desktop.
echo ===================================================
echo.
pause
