import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from PIL import Image
from app_theme import artwork_theme_colors
from color_rules import timeline_colors
from main import PlayerWindow


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    window = PlayerWindow(settings)
    window.show()
    app.processEvents()
    window.seek.setRange(0, 100000)
    window.seek.setValue(50000)

    for background in ('#d0b090', '#203070', '#503020'):
        start = window.seek.colors()
        settings.setValue('theme_background_color', background)
        cover = root / 'cover.png'
        Image.new('RGB', (64, 64), background).save(cover)
        colors = artwork_theme_colors(cover.read_bytes()) if background != '#d0b090' else None
        with patch.object(window, 'now_playing_theme_colors', return_value=colors):
            window.theme_from_now_playing()
        animation = window.theme_fade
        animation.pause()
        assert window.seek.colors() == start
        target = timeline_colors(window.theme_target['themeBackground'], window.theme_target['themeAccent'])
        end = 2000 if background == '#203070' else 4000
        previous = start
        for elapsed in range(0, end + 1, 40):
            animation.setCurrentTime(elapsed)
            expected = tuple(QColor(*(round(a + (b - a) * elapsed / 4000) for a, b in
                                      zip(first.getRgb()[:3], second.getRgb()[:3])))
                             for first, second in zip(start, target))
            actual = window.seek.colors()
            assert actual == expected, (background, elapsed)
            assert actual[2:] == (actual[0], actual[1])
            assert all(abs(a - b) <= 3 for first, second in zip(previous, actual)
                       for a, b in zip(first.getRgb()[:3], second.getRgb()[:3]))
            image = window.seek.grab().toImage()
            assert image.pixelColor(60, image.height() // 2) == expected[1]
            assert image.pixelColor(image.width() - 60, image.height() // 2) == expected[0]
            previous = actual
        if end == 4000:
            assert window.seek.fade_colors is None
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    app.processEvents()
print('PASS: smooth timeline colors, exact color swap, endpoints and interrupted fades')
