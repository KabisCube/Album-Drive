![Album Drive preview](docs/preview1.png)
![Album Drive preview](docs/preview2.png)

Album Drive is a simple local music player that uses your folder structure instead of metadata to organize your music. It supports music folders and audio CDs in a CD/DVD drive.

Albums are displayed in CD cases, using the cover image stored in each album's folder. By default, Album Drive changes its theme to match the album art with additional settings for if you prefer to only get dark or light themes. If you find one you like, it can then be saved and used globally.


## Download

[Download Album Drive from GitHub Releases](https://github.com/KabisCube/Album-Drive/releases).

Release packages include a `licenses/` folder with dependency and font notices, plus an editable `fonts/handwriting/` folder beside the executable.

## Requirements

Packaged builds include Python and the app dependencies; no Python installation is needed.

- **Windows:** 64-bit Windows.
- **Linux:** a compatible glibc-based graphical desktop and system audio/XCB libraries. CI uses Ubuntu 22.04.
- **Audio CDs:** currently Windows-only, with a drive that supports digital audio reading.

Playback support depends on the bundled Qt/FFmpeg backend and the individual file.

### Run from source

Source runs need Python 3.10+ and the packages in [requirements.txt](requirements.txt):

Use a separate virtual environment for each operating system. On Windows, create `.venv-windows` in PowerShell:

```powershell
py -3 -m venv .venv-windows
.venv-windows\Scripts\python.exe -m pip install -r requirements.txt
```

Then run `start-windows.bat`.

On Linux, create `.venv-linux`:

```sh
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -r requirements.txt
./start-linux.sh
```

The launchers keep the Windows and Linux environments separate. `start-linux.sh` also supports an existing `.venv` for compatibility.

### Build executables

Native executable builds must run on the target operating system:

On Windows:

```powershell
.venv-windows\Scripts\python.exe -m pip install -r requirements-build.txt
.venv-windows\Scripts\python.exe scripts/build.py
```

On Linux:

```sh
.venv-linux/bin/python -m pip install -r requirements-build.txt
.venv-linux/bin/python scripts/build.py
```

On Linux, this command adds a launcher for the app's current location. Rerun it if you move the app:

```sh
./AlbumDrive --install-desktop-entry
```

### Logs

Unexpected Python errors are recorded in `logs/errors.log` beside the app. Native crash details are recorded in `logs/crash.log`. If that folder is not writable, logs use the operating system's local app-data folder instead.

## Project layout

| Folder | Contents |
| --- | --- |
| `src/` | Application code |
| `assets/` | Fonts, icons, and sounds |
| `scripts/` | Build tools, asset generators, and the test runner |
| `packaging/` | PyInstaller build specification |
| `tests/` | Unit tests |
| `tests/checks/` | UI and integration checks |
| `licenses/` | Bundled third-party license texts and notices |
| `build/` | Generated files and previews |
| `dist/` | Packaged releases |
| `logs/` | Runtime logs |

## Tests

Run unit tests:

```sh
python scripts/test.py
```

Run specific UI checks:

```sh
python scripts/test.py check_settings check_sorting
```

Run all UI checks:

```sh
python scripts/test.py --checks
```

## licenses
| Font | Use | License or notice |
| --- | --- | --- |
| Album Round Bold | Main interface; original for Album Drive | [GPLv3 notice](licenses/fonts/AlbumRound-LICENSE.txt) |
| Album Marker 01–03 | Handwritten sleeves; original for Album Drive | [GPL-3.0-or-later notice](licenses/fonts/handwriting/AlbumMarker-LICENSE.txt) |
| [Resource Han Rounded SC Bold](https://github.com/CyanoHao/Resource-Han-Rounded) | Japanese, Korean, and Chinese fallback; Cyano Hao, with portions by Adobe | [SIL Open Font License 1.1](licenses/fonts/cjk/ResourceHanRounded-LICENSE.txt) |

