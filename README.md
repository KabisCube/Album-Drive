![Album Drive preview](docs/preview1.png)
![Album Drive preview](docs/preview2.png)

Album Drive is a simple and cute local music player that uses your folder structure instead of metadata to organize your music. It supports music folders and audio CDs in a CD/DVD drive.

Each albums gets represented as CD cases using any album art stored in the metadata or the folder. Album Drive dynamically changes its theme to match the album art. And supports Dark themes, Light themes or full brightness range. If you find one you like, it can then be saved and used globally.


## Download

[Download Album Drive from GitHub Releases](https://github.com/KabisCube/Album-Drive/releases).


## Requirements

Packaged builds include Python and the app dependencies; no Python installation is needed.

- **Windows:** 64-bit Windows.
- **Linux:** 64-bit x86 Linux with a glibc-based graphical desktop and the required graphics, audio, and XCB libraries. CI targets Ubuntu 22.04.
- **Audio CDs:** currently Windows-only.

Playback support depends on the bundled Qt/FFmpeg backend and the individual file.

## Android build

The experimental debug APK targets ARM64 devices running Android 9 or later.

Build on Linux or inside Ubuntu WSL. Install the native prerequisites once:

```sh
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential git curl unzip zip openjdk-17-jdk-headless ant autoconf automake libtool pkg-config cmake zlib1g-dev libffi-dev libssl-dev libltdl-dev patch ccache gettext
bash scripts/setup_android.sh
python3 scripts/build_android.py
```

The SDK, NDK, Python environment, and compiler cache stay in `~/.cache/album-drive-android`. The APK is written to `dist/AlbumDrive-android-arm64-debug.apk`. After setting up WSL, Windows can also run `python scripts/build_android.py`, or `run-android.bat` to build, install, and open the app on a phone connected by USB with USB debugging turned on. Add `--skip-build` to reinstall the last build. The script downloads Google's Android platform tools the first time if `adb` is not already installed. The Android wheels and Python compiler revision are pinned together; do not update either independently. Debug builds are signed for local testing, not Play Store publication.


### Logs

Unexpected Python errors are recorded in `logs/errors.log` beside the app. Native crash details are recorded in `logs/crash.log`. If that folder is not writable, logs use the operating system's local app-data folder instead. If you run into bugs, please file a bug report with relevant crash and error logs.


## licenses
| Font | Use | License or notice |
| --- | --- | --- |
| Album Round Bold | Main interface; original for Album Drive | [GPLv3 notice](licenses/fonts/AlbumRound-LICENSE.txt) |
| Album Marker 01–03 | Handwritten sleeves; original for Album Drive | [GPL-3.0-or-later notice](licenses/fonts/handwriting/AlbumMarker-LICENSE.txt) |
| [Resource Han Rounded SC Bold](https://github.com/CyanoHao/Resource-Han-Rounded) | Japanese, Korean, and Chinese fallback; Cyano Hao, with portions by Adobe | [SIL Open Font License 1.1](licenses/fonts/cjk/ResourceHanRounded-LICENSE.txt) |

