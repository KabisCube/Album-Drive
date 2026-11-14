"""Desktop identity shared by source runs and standalone executables."""

import sys
import os
import shutil
from pathlib import Path

from app_paths import ASSETS_DIR

from PySide6.QtGui import QIcon

APP_NAME = 'Album Drive'


def configure_app(app):
    if sys.platform == 'win32' and not getattr(sys, 'frozen', False):
        # A built exe keeps Windows' own identity so a pin made by dragging the exe groups with it.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('AlbumDrive.MusicPlayer')
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName('album-drive')
    # PyInstaller preserves __file__ relative to its bundled data directory.
    app.setWindowIcon(QIcon(str(ASSETS_DIR / 'icons' / 'album-drive.png')))


def install_desktop_entry(executable=None, data_directory=None):
    """Register a Linux portable app where it lives, keeping themes beside it."""
    executable = Path(executable or sys.executable).resolve()
    data = Path(data_directory or os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    icons = data / 'icons' / 'hicolor' / 'scalable' / 'apps'
    applications = data / 'applications'
    icons.mkdir(parents=True, exist_ok=True)
    applications.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSETS_DIR / 'icons' / 'album-drive.svg', icons / 'album-drive.svg')
    command = str(executable).replace('\\', '\\\\\\\\').replace('"', '\\\\"').replace('`', '\\\\`').replace('$', '\\\\$').replace('%', '%%')
    (applications / 'album-drive.desktop').write_text(
        f'[Desktop Entry]\nType=Application\nName={APP_NAME}\nComment=Play your music collection\n'
        f'Exec="{command}"\nIcon=album-drive\nTerminal=false\nCategories=AudioVideo;Audio;Player;\n'
        f'StartupNotify=true\nStartupWMClass={APP_NAME}\n', encoding='utf-8')
    return applications / 'album-drive.desktop'
