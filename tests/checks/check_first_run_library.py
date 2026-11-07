"""The library opens once setup ends, not while a first start is still waiting on it."""

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication([])
app.setStyle('Fusion')

from main import PlayerWindow

root = Path(tempfile.mkdtemp())
default = root / 'Default music'
(default / 'Default artist').mkdir(parents=True)
chosen = root / 'Chosen music'
(chosen / 'Chosen artist').mkdir(parents=True)


def finish_setup(folder):
    guide = app.activeModalWidget()
    if folder:
        guide.library_folder = str(folder)
    for _ in range(3):
        guide.advance()


def cancel_setup():
    app.activeModalWidget().reject()


def names(window):
    deadline = 200
    while deadline:
        QTest.qWait(20)
        deadline -= 1
        model, parent = window.files, window.tree.rootIndex()
        rows = [model.index(row, 0, parent).data() for row in range(model.rowCount(parent))]
        if rows:
            return rows
    return []


with patch('main.music_directory', return_value=str(default)), patch('first_run.music_directory', return_value=str(default)):
    for name, action, expected in (('chosen', lambda: finish_setup(chosen), chosen),
                                   ('skipped', lambda: finish_setup(None), default),
                                   ('cancelled', cancel_setup, default)):
        settings = QSettings(str(root / f'{name}.ini'), QSettings.IniFormat)
        window = PlayerWindow(settings)
        window.show()
        QTest.qWait(50)
        assert window.current_folder is None, name
        assert not settings.contains('browser_root'), name
        QTimer.singleShot(0, action)
        window.show_first_run_setup()
        assert Path(window.files.filePath(window.tree.rootIndex())) == expected, name
        assert names(window) == [expected.name.split()[0] + ' artist'], name
        assert not window.first_run_needed, name
        window.close()
print('PASS: setup chooses, skips or cancels the library, and the file browser fills straight away')
