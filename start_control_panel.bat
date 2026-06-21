@echo off
title GPM Chatbot Control Panel
:: Set active directory to script directory
cd /d "%~dp0"

echo ==========================================================
echo           GPM Chatbot Control Panel Launcher
echo ==========================================================
echo.

:: Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
    echo Please make sure you have installed requirements and set up Python.
    pause
    exit /b 1
)

echo [INFO] Starting Web Server...
echo [INFO] Auto-opening Control Panel in your default browser...
echo.

:: Launch the browser URL after a short delay (2 seconds)
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"

:: Start Flask server
.venv\Scripts\python.exe src\web_server.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Web Server stopped with error code %errorlevel%
    pause
)
