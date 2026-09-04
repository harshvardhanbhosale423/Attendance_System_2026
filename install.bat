@echo off
title College Attendance System - Setup
echo ================================================================
echo   College Attendance System - First Time Setup
echo ================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo IMPORTANT: During install, check "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv

echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/4] Installing required packages (this may take a few minutes)...
pip install -r requirements.txt

echo [4/4] Setting up configuration...
if not exist .env (
    copy .env.example .env
    echo Created .env file with default settings (SQLite, works immediately).
) else (
    echo .env already exists, leaving it as-is.
)

echo.
echo ================================================================
echo   Setup complete!
echo   Double-click "start.bat" any time to run the system.
echo ================================================================
pause
