"""Development only: F7 saves a screenshot of the active window to build/screenshots/ in the repository."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

FOLDER = Path(__file__).resolve().parent.parent / 'build' / 'screenshots'


def save_screenshot(window):
    target = QApplication.activeWindow() or window
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / f'album-drive-{datetime.now():%Y%m%d-%H%M%S-%f}.png'
    if target.grab().save(str(path)):
        print(f'Screenshot saved: {path}', flush=True)
    return path


def install_dev_screenshot(window):
    shortcut = QShortcut(QKeySequence(Qt.Key_F7), window)
    shortcut.setContext(Qt.ApplicationShortcut)
    shortcut.activated.connect(lambda: save_screenshot(window))
    return shortcut
