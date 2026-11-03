"""Desktop identity shared by source runs and standalone executables."""

import sys
import os
import shutil
from pathlib import Path

from app_paths import ASSETS_DIR

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

APP_NAME = 'Album Drive'


def update_theme_icon(app, accent):
    """Tint the running app's icon, keeping the disc's transparent silhouette."""
    color = QColor(accent)
    if not color.isValid() or app.property('themeIconAccent') == color.name():
        return
    if not hasattr(app, '_theme_icon_masks'):
        source = QPixmap(str(ASSETS_DIR / 'icons' / 'album-drive.png'))
        if source.isNull():
            return
        app._theme_icon_masks = [source.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                 for size in (16, 24, 32, 48, 64, 128, 256)]
    icon = QIcon()
    for mask in app._theme_icon_masks:
        pixmap = QPixmap(mask)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()
        icon.addPixmap(pixmap)
    app.setWindowIcon(icon)
    for window in app.topLevelWidgets():
        window.setWindowIcon(icon)
    app.setProperty('themeIconAccent', color.name())
    if sys.platform == 'win32' and app.platformName() == 'windows':
        if not hasattr(app, '_theme_icon_timer'):
            from windows_identity import update_windows_identity
            app._theme_icon_timer = QTimer(app)
            app._theme_icon_timer.setSingleShot(True)
            app._theme_icon_timer.timeout.connect(lambda: update_windows_identity(app))
        app._theme_icon_timer.start(180)


def configure_app(app):
    if sys.platform == 'win32':
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
