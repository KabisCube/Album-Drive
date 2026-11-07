@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv-windows\Scripts\python.exe"
if exist "%PYTHON%" goto dependencies

py -3 -c "import sys" >nul 2>&1
if errorlevel 1 (
    python -m venv .venv-windows
) else (
    py -3 -m venv .venv-windows
)
if errorlevel 1 goto failed

:dependencies
"%PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto failed

"%PYTHON%" scripts\build.py
if errorlevel 1 goto failed

echo.
echo Windows build ready in the dist folder.
pause
exit /b 0

:failed
echo.
echo Windows build failed. See the error above.
pause
exit /b 1
