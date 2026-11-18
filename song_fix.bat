@echo off
title Just Dance Greatest Hits (Xbox 360) - Song Replacement Toolkit
cd /d "%~dp0"
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python was not found in PATH. Install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
python song_fix.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred during execution.
)
pause
