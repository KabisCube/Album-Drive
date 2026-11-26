## Desktop (Windows and Linux)

You need Python 3.10 or later.

### Build a standalone app

- **Windows:** run `tools\build-windows.bat`. The app is written to the `dist` folder.
- **Linux:** run `tools/build-linux.sh`. The app is written to `dist/AlbumDrive-linux-x86_64`; run `install.sh` in that folder to add Album Drive to the app menu with its icon.

Both scripts create a Python environment (`.venv-windows` or `.venv-linux`) and install the dependencies the first time.

### Run from source

After building once, `start-windows.bat` or `start-linux.sh` runs the app straight from the source code using that same environment.

### Tests

`python scripts/test.py` runs the unit tests. `tools/verify.sh` checks the Linux build the same way GitHub does; add `--android` to also test on a phone connected by USB.


## Android

The experimental APK targets ARM64 devices running Android 9 or later.

Build on Linux or inside Ubuntu WSL. Install the native prerequisites once:

```sh
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential git curl unzip zip openjdk-17-jdk-headless ant autoconf automake libtool pkg-config cmake zlib1g-dev libffi-dev libssl-dev libltdl-dev patch ccache gettext
bash scripts/setup_android.sh
python3 scripts/build_android.py
```

The SDK, NDK, Python environment, and compiler cache stay in `~/.cache/album-drive-android`. The APK is written to `dist/AlbumDrive-android-arm64-debug.apk`.

After setting up WSL, Windows can also run `python scripts/build_android.py`, or `tools\run-android.bat` to build, install, and open the app on a phone connected by USB with USB debugging turned on. Add `--skip-build` to reinstall the last build. The script downloads Google's Android platform tools the first time if `adb` is not already installed.

The Android wheels and Python compiler revision are pinned together; do not update either independently. Debug builds are signed for local testing, not Play Store publication.


## Maintainers

Releasing and Android signing are covered in [tools/README.md](tools/README.md).
