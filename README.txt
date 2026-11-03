ALBUM DRIVE
===========

Album Drive is a simple local music player that uses your folder structure instead 
of meta data to organize your music.

Albums are displayed in CD cases, and uses the cover image you've stored in your 
album's folder for the album art.
By default Album Drive dynamically changes themes based on the album art.
There are no playlists, accounts, or servers.

Album Round uses bundled Resource Han Rounded Bold glyphs for Japanese, Korean,
and Chinese text. The fonts work offline and retain their separate licenses in
assets/fonts/. Other scripts use fonts available on the operating system.



REQUIREMENTS
------------
Unexpected Python errors are recorded in logs/errors.log beside the app.
Native crash details are recorded in logs/crash.log. If that folder is not
writable, logs use the operating system's local app-data folder instead.

Packaged builds include Python and the app dependencies; no Python installation
is needed. Windows builds target 64-bit Windows. Linux builds need a compatible
glibc-based graphical desktop and system audio/XCB libraries (CI uses Ubuntu
22.04). Physical audio-CD support is currently Windows-only and needs a drive
that supports digital audio reading. Playback support depends on the bundled
Qt/FFmpeg backend and the individual file.

Source runs need Python 3.10+ and the packages in requirements.txt:
    python -m pip install -r requirements.txt
    python src/main.py
Native executable builds must run on the target operating system:
    python -m pip install -r requirements-build.txt
    python scripts/build.py
On Linux, ./AlbumDrive --install-desktop-entry adds a launcher for the app's
current location; rerun it if you move the app.

PROJECT LAYOUT
--------------
src/              Application code
assets/           Fonts, icons, and sounds
scripts/          Build tools, asset generators, and the test runner
packaging/        PyInstaller build specification
tests/            Unit tests
tests/checks/     UI and integration checks
build/            Generated files and previews
dist/             Packaged releases
logs/             Runtime logs

Run the app with start-windows.bat or ./start-linux.sh after creating .venv
and installing requirements.txt. Direct launch: python src/main.py.
Run unit tests: python scripts/test.py
Run specific UI checks: python scripts/test.py check_settings check_sorting
Run all UI checks: python scripts/test.py --checks


FONT CREDITS
------------
Thanks to the designers who made these fonts available:

- Barato: Edson Silva (eddy.dsgn).
  Source: https://www.behance.net/eddy_dsgn
  License: SIL Open Font License 1.1, embedded in Barato.ttf.
  Notice: assets/fonts/handwriting/barato/readme.txt

- Elatox (regular and italic): GGBotNet.
  Source: https://ggbot.itch.io/elatox-font
  License: SIL Open Font License 1.1.
  License file: assets/fonts/handwriting/elatox/License.txt

- Mistral SingleLine Outline: Francois Chastanet, Elisa Garzelli,
  Anais Alves and Morgane Autin; isdaT-type. Based on Roger Excoffon's Mistral.
  Source: https://github.com/isdat-type/Mistral-SingleLine
  License: SIL Open Font License 1.1.
  License file: assets/fonts/handwriting/mistral_singleline/OFL.txt

- TMT Caffeine (Regular and Scrabble): Gabriel Drozdov / Too Much Type.
  Source: https://toomuchtype.com/
  License: SIL Open Font License 1.1.
  License file: assets/fonts/handwriting/TMT_caffeine/license.txt

- Resource Han Rounded SC Bold: Cyano Hao, with portions by Adobe.
  Source: https://github.com/CyanoHao/Resource-Han-Rounded
  License: SIL Open Font License 1.1.
  License file: assets/fonts/cjk/ResourceHanRounded-LICENSE.txt

These third-party fonts retain their own licenses. Album Round is the project's
original font; its notice is in assets/fonts/AlbumRound-LICENSE.txt.
