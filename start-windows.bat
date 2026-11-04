@echo off
cd /d "%~dp0"
set "PYTHON=.venv-windows\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" goto system_python

"%PYTHON%" -c "import sys" >nul 2>&1
if errorlevel 1 goto system_python
"%PYTHON%" -c "import PySide6, mutagen, PIL" >nul 2>&1
if errorlevel 1 goto dependencies_missing

"%PYTHON%" src\main.py
if errorlevel 1 pause
exit /b

:system_python
where py >nul 2>&1
if errorlevel 1 goto python_missing
set "PYTHONPATH=%CD%\.venv\Lib\site-packages;%PYTHONPATH%"
py -3 -c "import PySide6, mutagen, PIL" >nul 2>&1
if errorlevel 1 goto dependencies_missing
py -3 src\main.py
if errorlevel 1 pause
exit /b

:dependencies_missing
echo Python was found, but the source dependencies are missing.
echo Create .venv-windows using the Windows setup instructions in README.md.
pause
exit /b 1

:python_missing
echo No usable Python was found. See README.md for Windows setup instructions.
    pause
    exit /b 1
