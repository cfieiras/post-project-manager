@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   Building Portable Standalone Executable (.exe)
echo ==========================================================
echo.

echo Checking requirements...
python -m pip install -r requirements.txt

echo.
echo Running PyInstaller...
pyinstaller --noconsole --onefile ^
    --name "PostProjectManager" ^
    --add-data "templates/default_template.json;templates" ^
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
echo   Executable created at: dist\PostProjectManager.exe
echo ==========================================================
pause
