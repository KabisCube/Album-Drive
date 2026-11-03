@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run: follow the setup instructions in README.txt.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" src\main.py
if errorlevel 1 pause
