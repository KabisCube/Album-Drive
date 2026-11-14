"""Esc and the Back action close an open folder search before they leave the page."""
import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
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
    window.activateWindow()
    pump(.5)
    bar = window.tree.search_bar

    bar.set_expanded(True, animate=False)
    assert bar.field.hasFocus(), 'the field takes focus, which brings up a phone keyboard'
    assert window.back_action.isEnabled() and window.escape_action.isEnabled()
    QTest.keyClick(bar.field, Qt.Key_Escape)
    assert not bar.expanded, 'Esc while typing closes the search'

    bar.set_expanded(True, animate=False)
    bar.field.setText('art')
    window.grid.setFocus()
    pump(.05)
    QTest.keyClick(window.grid, Qt.Key_Escape)
    assert not bar.expanded, 'Esc closes the search wherever the focus is'
    assert not bar.field.text()

    bar.set_expanded(True, animate=False)
    window.back_action.trigger()
    assert not bar.expanded, 'Android Back closes the search'
    assert not window.back_action.isEnabled(), 'with the search closed, Back no longer stays in the app on the browser'
    window.close()
    pump(.1)
    print('PASS: Esc and Back close the folder search, from the field or anywhere else')
