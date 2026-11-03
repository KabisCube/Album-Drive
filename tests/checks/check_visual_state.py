"""Session colors, normal album fades, accent icons and connected logo depth."""

import os
from pathlib import Path
import tempfile
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow
from session_palette import load_session_palette
from test_library import make_wave
from themes import ChunkyBrand, COLOR_SETTINGS


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


def current_colors():
    return {prop: app.property(prop) for _, _, _, prop, _ in COLOR_SETTINGS}


def check_icon(window):
    for icon in (app.windowIcon(), window.windowIcon()):
        image = icon.pixmap(64, 64).toImage()
        assert image.pixelColor(32, 8).name() == app.property('themeAccent')
        assert image.pixelColor(0, 0).alpha() == 0
        assert image.pixelColor(32, 32).alpha() == 0


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    for name, color in (('Blue', '#234f79'), ('Gold', '#dccb8a')):
        make_wave(root / 'Music' / name / '1.wav')
        Image.new('RGB', (64, 64), color).save(root / 'Music' / name / 'cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 2 and not window.scanners)
    album = next(album for album in window.albums if album.folder.name == 'Blue')
    window.queue = [(track, album) for track in album.tracks]
    window.play_index(0, autoplay=False)
    window.theme_fade.setCurrentTime(4000)
    expected = current_colors()
    check_icon(window)
    window.close()
    wait_until(lambda: not window.scanners)
    settings.sync()
    assert load_session_palette(settings)['colors'] == expected
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    assert current_colors() == expected, 'Defaults flashed before the session loaded'
    restored.show()
    wait_until(lambda: restored.queue_index == 0 and not restored.scanners)
    assert current_colors() == expected
    assert getattr(restored, 'theme_fade', None) is None
    check_icon(restored)
    gold = next(album for album in restored.albums if album.folder.name == 'Gold')
    restored.queue = [(track, gold) for track in gold.tracks]
    restored.play_index(0, autoplay=False)
    assert restored.theme_fade is not None
    restored.theme_fade.pause()
    restored.theme_fade.setCurrentTime(2000)
    check_icon(restored)
    restored.theme_fade.setCurrentTime(4000)
    restored.close()
    wait_until(lambda: not restored.scanners)
    settings.sync()
    # External preference edits and malformed caches must not override choices.
    settings.setValue('artwork_theme_mode', 'dark')
    assert load_session_palette(settings) is None
    settings.setValue('session/palette', 'broken')
    assert load_session_palette(settings) is None

    app.setProperty('uiThickness', 300)
    app.setProperty('brandTextColor', '#00ff00')
    app.setProperty('brandLineColor', '#101010')
    brand = ChunkyBrand('Album Drive')
    brand.resize(320, 64)
    brand.setStyleSheet('background: #101010;')
    image = brand.grab().toImage()
    front = [(x, y) for x in range(image.width()) for y in range(image.height())
             if image.pixelColor(x, y).name() == '#00ff00']
    shadow = [(x, y) for x in range(image.width()) for y in range(image.height())
              if image.pixelColor(x, y).name() == QColor('#00ff00').darker(150).name()]
    assert front and shadow
    assert abs(max(y for _, y in shadow) - max(y for _, y in front) - 12) <= 1
    for x, y in front:
        assert all(image.pixelColor(x, y + offset).name() != '#101010' for offset in range(1, 13))
    Path('build').mkdir(exist_ok=True)
    image.save('build/logo-thick.png')
    brand.close()
    QTest.qWait(100)

print('PASS: startup palette before/after resume, later album fades, live accent icon and bridged 12px logo')
