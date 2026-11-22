@echo off
cd /d "%~dp0"
echo ==========================================================
echo   Pushing Post Project Manager (v1.3.0) to GitHub
echo ==========================================================
echo.
git push origin main --tags
if errorlevel 1 (
    echo.
    echo [ERROR] Push failed. Please check your internet connection or git credentials.
) else (
    echo.
    echo ==========================================================
    echo   SUCCESS! Pushed to https://github.com/cfieiras/post-project-manager
    echo   GitHub Actions will now build and publish the release.
    echo ==========================================================
)
pause
