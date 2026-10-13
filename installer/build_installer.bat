@echo off
REM Builds "FitBuddy Setup.exe" from the PyInstaller output using Inno Setup.
REM Requires Inno Setup 6 installed (https://jrsoftware.org/isinfo.php) with
REM ISCC.exe on PATH, and dist\FitBuddy\FitBuddy.exe already built (run
REM "python build.py" from the project root first).

where ISCC >nul 2>nul
if errorlevel 1 (
    echo ISCC.exe not found on PATH. Install Inno Setup 6 and add its folder
    echo ^(typically C:\Program Files ^(x86^)\Inno Setup 6^) to PATH, then retry.
    exit /b 1
)

ISCC fitbuddy.iss
echo.
echo Done. See installer\Output\FitBuddy Setup.exe
