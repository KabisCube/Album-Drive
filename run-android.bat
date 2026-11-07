@echo off
rem Builds the Android APK, installs it on the phone connected by USB, and opens it.
rem Use "run-android.bat --skip-build" to reinstall the last build.
setlocal
cd /d "%~dp0"

set "PACKAGE=org.albumdrive.albumdrive"
set "APK=dist\AlbumDrive-android-arm64-debug.apk"
set "TOOLS=%LOCALAPPDATA%\AlbumDrive"
set "ADB_ZIP=https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

call :find_adb
if not defined ADB call :download_adb
if not defined ADB goto adb_missing

rem Check the phone first so a long build does not end with nowhere to install.
call :find_phone
if defined UNAUTHORIZED if not defined ANDROID_SERIAL goto phone_unauthorized
if not defined ANDROID_SERIAL goto phone_missing
echo Using phone %ANDROID_SERIAL%

if /i "%~1"=="--skip-build" goto install

where wsl.exe >nul 2>&1
if errorlevel 1 goto wsl_missing
wsl -- python3 scripts/build_android.py
if errorlevel 1 goto build_failed

:install
if not exist "%APK%" goto apk_missing
echo.
echo Installing on the phone...
"%ADB%" install -r "%APK%"
if errorlevel 1 goto install_failed
"%ADB%" shell monkey -p %PACKAGE% -c android.intent.category.LAUNCHER 1 >nul 2>&1
if errorlevel 1 goto launch_failed

echo.
echo Album Drive is running on the phone.
pause
exit /b 0

:find_adb
set "ADB="
for /f "delims=" %%p in ('where adb.exe 2^>nul') do if not defined ADB set "ADB=%%p"
if not defined ADB if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not defined ADB if exist "%TOOLS%\platform-tools\adb.exe" set "ADB=%TOOLS%\platform-tools\adb.exe"
exit /b 0

:download_adb
rem WSL cannot reach USB phones by default, so this needs the Windows version of adb.
echo Downloading Android platform tools from Google. This only happens once.
if not exist "%TOOLS%" mkdir "%TOOLS%"
"%SystemRoot%\System32\curl.exe" -fsSL -o "%TOOLS%\platform-tools.zip" "%ADB_ZIP%"
if errorlevel 1 exit /b 0
"%SystemRoot%\System32\tar.exe" -xf "%TOOLS%\platform-tools.zip" -C "%TOOLS%"
if errorlevel 1 exit /b 0
del "%TOOLS%\platform-tools.zip"
call :find_adb
exit /b 0

:find_phone
set "ANDROID_SERIAL="
set "UNAUTHORIZED="
"%ADB%" start-server >nul 2>&1
for /f "skip=1 tokens=1,2" %%a in ('"%ADB%" devices') do (
    if "%%b"=="device" if not defined ANDROID_SERIAL set "ANDROID_SERIAL=%%a"
    if "%%b"=="unauthorized" set "UNAUTHORIZED=1"
)
exit /b 0

:adb_missing
echo.
echo Could not find or download adb. Install Android platform tools, then try again.
pause
exit /b 1

:phone_missing
echo.
echo No phone found. Connect it by USB, turn on USB debugging, and set USB mode to file transfer.
pause
exit /b 1

:phone_unauthorized
echo.
echo The phone has not allowed this PC yet. Unlock it, accept the USB debugging prompt, and try again.
pause
exit /b 1

:wsl_missing
echo.
echo WSL is required. See the Android build instructions in README.md.
pause
exit /b 1

:build_failed
echo.
echo Android build failed. See the error above and the prerequisites in README.md.
pause
exit /b 1

:apk_missing
echo.
echo %APK% does not exist yet. Run this script without --skip-build first.
pause
exit /b 1

:install_failed
echo.
echo Install failed. If the error mentions a signature mismatch, uninstall Album Drive from the phone and try again.
pause
exit /b 1

:launch_failed
echo.
echo Album Drive was installed but did not open. Start it from the phone.
pause
exit /b 1
