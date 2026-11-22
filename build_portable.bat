@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================================
echo   Building Portable Standalone Executable (.exe)
echo ==========================================================
echo.

:: Extract version from src/version.py
for /f "tokens=2 delims==" %%a in ('findstr "__version__" src\version.py') do (
    set raw_ver=%%a
    set ver=!raw_ver:"=!
    set ver=!ver: =!
)
if "!ver!"=="" set ver=1.0.3

echo Detected Version: !ver!
echo.

echo Checking requirements...
python -m pip install -r requirements.txt

echo.
echo Running PyInstaller...
pyinstaller --noconsole --onefile ^
    --name "PostProjectManager_v!ver!" ^
    --icon "src\ui\icons\app_icon.ico" ^
    --add-data "templates\default_template.json;templates" ^
    --add-data "src\ui\icons;src\ui\icons" ^
    --clean ^
    src\main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   BUILD SUCCESSFUL!
echo   Executable created at: dist\PostProjectManager_v!ver!.exe
echo ==========================================================
pause
