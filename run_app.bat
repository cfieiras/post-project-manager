@echo off
title Post Project Manager
cd /d "%~dp0"
python src\main.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
