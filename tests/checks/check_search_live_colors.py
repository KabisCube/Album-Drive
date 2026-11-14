"""Android's live theme colors survive the file browser's search bar restyling the browser."""
import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

app = QApplication([])
app.setStyle('Fusion')
from main import PlayerWindow


def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.01)


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music' / 'Artist').mkdir(parents=True)
    settings = QSettings(str(root / 's.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('button_sound_volume', 0)
    window = PlayerWindow(settings)
    window.first_run_needed = False
    window.resize(1100, 750)
    window.show()
    pump(.5)
    # Android's live theme, with a background that clearly differs from the default palette.
    window.enter_live_theme()
    app.setProperty('themeBackground', '#2e576a')
    window.theme_renderer.update_colors()
    pump(.2)
    tree = window.tree
    expected = QColor('#2e576a').darker(110).name()
    before = tree.palette().color(QPalette.Window).name(), tree.viewport().palette().color(QPalette.Base).name()
    tree.search_bar.set_expanded(True, animate=False)
    pump(.3)
    after = tree.palette().color(QPalette.Window).name(), tree.viewport().palette().color(QPalette.Base).name()
    print('expected', expected, 'before', before, 'after expanding', after)
    assert before == after == (expected, expected), 'expanding the search bar changed the browser colors'
    window.close()
    pump(.1)
    print('PASS: file browser keeps the live theme colors when the search bar expands')
