@echo off
title Just Dance Greatest Hits (Xbox 360) - Song Replacement Toolkit
cd /d "%~dp0"
python song_fix.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred during execution.
)
pause
