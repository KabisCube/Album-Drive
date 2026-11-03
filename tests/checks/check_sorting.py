"""Offscreen checks for release sorting, saved drag order and smooth row scrolling."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from mutagen.id3 import TDRC
from mutagen.wave import WAVE
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QDropEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from library import natural_key
from main import PlayerWindow
from test_library import make_wave


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


def titles(window):
    return [window.albums[window.grid.item(row).data(Qt.UserRole)].title
            for row in range(window.grid.count())]


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for name, released in [('Zulu', '2020-03-02'), ('Alpha', '1990-05-01'),
                           ('Beta', '2000-01-01'), ('2010 - Gamma', '')] + [(f'Other {i}', '') for i in range(14)]:
        path = root / 'Music' / name / '1.wav'
        make_wave(path)
        if released:
            audio = WAVE(path)
            audio.add_tags()
            audio.tags.add(TDRC(encoding=3, text=[released]))
            audio.save()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('album_sort', 'alphabetical')
    settings.setValue('hover_growth', 0)
    settings.setValue('hover_rotation', 0)
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 18 and not window.scanners)
    assert titles(window) == sorted(titles(window), key=natural_key)
    window.sort_albums.setCurrentIndex(window.sort_albums.findData('oldest'))
    assert titles(window)[:4] == ['Alpha', 'Beta', '2010 - Gamma', 'Zulu']
    window.sort_albums.setCurrentIndex(window.sort_albums.findData('newest'))
    assert titles(window)[:4] == ['Zulu', '2010 - Gamma', 'Beta', 'Alpha']
    window.sort_albums.setCurrentIndex(window.sort_albums.findData('custom'))
    QTest.qWait(40)

    # The native item view starts our drag handler after a real drag gesture.
    dragged = []
    original_drag = window.grid.startDrag
    window.grid.startDrag = lambda actions: dragged.append(True)
    start = window.grid.visualItemRect(window.grid.item(0)).center()
    finish = start + QPoint(40, 40)
    QTest.mousePress(window.grid.viewport(), Qt.LeftButton, pos=start)
    event = QMouseEvent(QEvent.MouseMove, QPointF(finish),
                        QPointF(window.grid.viewport().mapToGlobal(finish)),
                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    app.sendEvent(window.grid.viewport(), event)
    QTest.mouseRelease(window.grid.viewport(), Qt.LeftButton, pos=finish)
    window.grid.startDrag = original_drag
    assert dragged, 'The grid did not initiate a drag'
    window.show_albums()
    window.grid.set_hover(-1)
    QTest.qWait(220)
    captured = {}

    class PreviewDrag:
        def __init__(self, parent):
            pass

        def setMimeData(self, mime):
            pass

        def setPixmap(self, pixmap):
            captured['size'] = pixmap.deviceIndependentSize()
            captured['image'] = pixmap.toImage()

        def setHotSpot(self, point):
            pass

        def exec(self, actions):
            return Qt.IgnoreAction

    with patch('album_grid.QDrag', PreviewDrag):
        original_drag(Qt.MoveAction)
    assert window.grid.iconSize().width() <= captured['size'].width() <= window.grid.iconSize().width() + 42
    assert window.grid.iconSize().height() <= captured['size'].height() <= window.grid.iconSize().height() + 42
    image = captured['image']
    assert all(image.pixelColor(x, y).alpha() == 0
               for x in range(image.width()) for y in (0, image.height() - 1))
    assert all(image.pixelColor(x, y).alpha() == 0
               for y in range(image.height()) for x in (0, image.width() - 1))

    before = titles(window)
    mime = QMimeData()
    mime.setData('application/x-album-drive-album', b'0')

    class LocalDrop(QDropEvent):
        def source(self):
            return window.grid

    drop = LocalDrop(QPointF(window.grid.visualItemRect(window.grid.item(3)).center()),
                     Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.grid.dropEvent(drop)
    expected = before[1:4] + before[:1] + before[4:]
    assert drop.isAccepted() and titles(window) == expected
    assert settings.value(window.custom_order_key()) == [str(window.albums[window.grid.item(row).data(Qt.UserRole)].folder)
                                                         for row in range(18)]
    window.open_album(window.grid.item(3))
    assert window.viewed_album.title == expected[3]
    window.show_albums()
    bar = window.grid.verticalScrollBar()
    bar.setValue(0)
    pitch = window.grid.row_pitch()

    def wheel():
        point = window.grid.viewport().rect().center()
        event = QWheelEvent(QPointF(point), QPointF(window.grid.viewport().mapToGlobal(point)),
                            QPoint(), QPoint(0, -120), Qt.NoButton, Qt.NoModifier,
                            Qt.NoScrollPhase, False)
        app.sendEvent(window.grid.viewport(), event)

    wheel()
    QTest.qWait(60)
    assert 0 < bar.value() < pitch
    wheel()
    QTest.qWait(300)
    assert bar.value() == min(2 * pitch, bar.maximum())
    window.close()
    wait_until(lambda: not window.scanners)
    settings.sync()
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    restored.show()
    wait_until(lambda: len(restored.albums) == 18 and not restored.scanners)
    assert restored.sort_albums.currentData() == 'custom'
    assert titles(restored) == expected
    restored.close()

print('PASS: alphabetical/release sorting, native drag gesture, drop order, correct album activation, saved custom order and smooth row intervals')
