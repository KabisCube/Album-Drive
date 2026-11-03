import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QAbstractAnimation, QPoint, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSplitter
from library import Album
from main import PlayerWindow


app = QApplication([])
with TemporaryDirectory() as directory:
    root = Path(directory)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', directory)
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(50)
    panel = window.now_playing
    empty_height = window.tree.height()
    assert panel.isHidden() and panel.height() == 0
    album = Album(root / 'Album', 'Album', 'Artist', [])
    window.update_now_playing_cover(album)
    panel.animation.pause()
    heights, positions = [], []
    assert panel.animation.duration() == 900
    for fraction in (0, .25, .5, .75, 1):
        panel.animation.setCurrentTime(round(panel.animation.duration() * fraction))
        app.processEvents()
        heights.append(window.tree.height())
        positions.append(window.cover.mapTo(window, QPoint()).y())
    assert heights[0] == empty_height
    assert all(first > second for first, second in zip(heights, heights[1:]))
    assert all(first > second for first, second in zip(positions, positions[1:]))
    assert not panel.isHidden() and panel.height() == panel.content.height()
    window.update_now_playing_cover(album)
    assert panel.animation.state() != QAbstractAnimation.Running
    window.findChild(QSplitter).setSizes([360, 800])
    app.processEvents()
    assert panel.height() == panel.content.height()
    assert window.cover.height() == window.cover.heightForWidth(window.cover.width())
    window.update_now_playing_cover()
    panel.animation.pause()
    panel.animation.setCurrentTime(panel.animation.duration() // 2)
    app.processEvents()
    intermediate = panel.height()
    window.update_now_playing_cover(album)
    panel.animation.pause()
    assert panel.height() == intermediate
    panel.animation.setCurrentTime(panel.animation.duration())
    app.processEvents()
    window.update_now_playing_cover()
    panel.animation.pause()
    panel.animation.setCurrentTime(panel.animation.duration())
    app.processEvents()
    assert panel.isHidden() and panel.height() == 0
    assert window.cover.pixmap().isNull()
    window.close()
    while window.scanners:
        QTest.qWait(10)
print('PASS: empty sidebar expansion, smooth cover entrance, stable album changes, resizing, interrupted animation and collapse')
