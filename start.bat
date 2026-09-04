@echo off
title College Attendance System - Server
cd /d "%~dp0"

if not exist venv (
    echo Virtual environment not found. Please run install.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo ================================================================
echo   Starting College Attendance System...
echo   Once you see "Running on http://...", open your browser to:
echo       http://localhost:5000
echo   Other PCs on the same WiFi/LAN can use your PC's IP address
echo   instead of "localhost" (see README section 5).
echo   Keep this window open while using the system.
echo   Close this window (or press CTRL+C) to stop the server.
echo ================================================================
echo.

start "" http://localhost:5000
python app.py

pause
