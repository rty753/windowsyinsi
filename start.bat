@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found! Please install Python 3.10+ and add to PATH.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
if not exist ".deps_installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Install failed. Check your network.
        pause
        exit /b 1
    )
    echo. > .deps_installed
)
echo Starting Privacy Guard...
python main.py
if %errorlevel% neq 0 pause
