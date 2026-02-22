@echo off
echo ============================================================
echo   FocusFlow — Building Single EXE
echo ============================================================
echo.

REM Install Requirements if not present
echo Installing dependencies...
pip install -r production_requirements.txt >nul 2>&1
pip install pyinstaller >nul 2>&1

echo Building FocusFlow.exe ...
echo This may take 1-2 minutes.
echo.

pyinstaller focusflow.spec --noconfirm

echo.
if exist "dist\FocusFlow.exe" (
    echo ============================================================
    echo   BUILD SUCCESSFUL!
    echo   Your EXE is at:  dist\FocusFlow.exe
    echo ============================================================
    echo.
    echo Give this single file to your client.
    echo They just double-click it, then open BlueMuse.
) else (
    echo BUILD FAILED - check the output above for errors.
)

echo.
pause
