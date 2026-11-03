import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from test_library import make_wave


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    music = root / 'Music'
    for index in range(50):
        (music / f'Artist {index:02}').mkdir(parents=True)
    artist = music / 'Artist 24'
    for index in range(80):
        make_wave(artist / f'Album {index:02}' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('browser_root', str(music))
    settings.setValue('folder', str(artist))
    window = PlayerWindow(settings)
    window.resize(1100, 700)
    window.show()
    wait_until(lambda: len(window.albums) == 80 and not window.scanners and not window.browsing_restore_timer.isActive())
    index = window.files.index(str(artist))
    window.tree.expand(index)
    wait_until(lambda: window.files.rowCount(index) == 80 and window.tree.verticalScrollBar().maximum() > 740)
    window.tree.verticalScrollBar().setValue(740)
    window.grid.setCurrentRow(67)
    window.grid.finish_reflow()
    window.grid.verticalScrollBar().setValue(1700)
    selected = window.albums[window.grid.currentItem().data(Qt.UserRole)].folder
    album_scroll = window.grid.verticalScrollBar().value()
    browser_scroll = window.tree.verticalScrollBar().value()
    playing = window.albums[5]
    window.queue = [(playing.tracks[0], playing)]
    window.queue_index = 0
    window.show_album(playing, play_sound=False)
    window.close()
    QTest.qWait(80)
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    restored.show()
    wait_until(lambda: restored.queue_index == 0 and not restored.scanners and not restored.browsing_restore_timer.isActive())
    assert restored.current_folder == artist
    assert Path(restored.files.filePath(restored.tree.currentIndex())) == artist
    assert restored.tree.isExpanded(restored.files.index(str(artist)))
    assert restored.tree.verticalScrollBar().value() == browser_scroll
    assert restored.grid.verticalScrollBar().value() == album_scroll
    assert restored.albums[restored.grid.currentItem().data(Qt.UserRole)].folder == selected
    assert restored.queue[0][1].folder == playing.folder
    assert restored.viewed_album.folder == playing.folder
    QTest.qWait(100)
    assert restored.grid.verticalScrollBar().value() == album_scroll
    restored.close()
    wait_until(lambda: not restored.scanners)
    QTest.qWait(80)
print('PASS: browser selection, expanded folders, both scroll positions and selected album survive restart independently of playback')
