@echo off
setlocal
cd /d "%~dp0"

where wsl.exe >nul 2>&1
if errorlevel 1 goto wsl_missing

wsl -- python3 scripts/build_android.py %*
if errorlevel 1 goto failed

echo.
echo Android APK ready in the dist folder.
pause
exit /b 0

:wsl_missing
echo.
echo WSL is required. See the Android build instructions in README.md.
pause
exit /b 1

:failed
echo.
echo Android build failed. See the error above and the prerequisites in README.md.
pause
exit /b 1
