@echo off
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0release.ps1" %*
set "releaseResult=%errorlevel%"
pause
exit /b %releaseResult%
