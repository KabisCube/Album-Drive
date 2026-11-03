from pathlib import Path
import os
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app_theme import artwork_theme_colors
from library import scan_library
from main import PlayerWindow
from test_library import make_wave
from themes import button_paint_rect, control_face


def sample_cover(accent=None):
    image = Image.new('RGB', (128, 128), '#cea968')
    if accent:
        image.putdata([(5 + x * 80 // 127, 45 + y * 100 // 127, 90 + (x + y) * 120 // 254)
                       for y in range(128) for x in range(128)])
        image.paste(accent, (20, 55, 28, 63))
    else:
        image.paste('#091619', (0, 85, 128, 128))
        image.paste('#66aabb', (10, 8, 118, 42))
    return image


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    music = root / 'Music'
    references = (
        ('Orange sample', '#ec981f', .055, .125, {}),
        ('Yellow sample', '#e5d715', .13, .20, {}),
        ('Landscape sample', None, .52, .55,
         {'any': '#cea968', 'dark': '#091619', 'light': '#d3b278'}),
    )
    loaded = []
    for name, accent, minimum_hue, maximum_hue, backgrounds in references:
        folder = music / 'Example Artist' / name
        make_wave(folder / '1.wav')
        sample_cover(accent).save(folder / 'cover.png')
        albums, skipped = scan_library(folder)
        assert len(albums) == 1 and not skipped
        album = albums[0]
        loaded.append((album, minimum_hue, maximum_hue, backgrounds))
        for mode in ('any', 'dark', 'light'):
            colors = artwork_theme_colors(album.artwork, mode)
            highlight = QColor(colors['themeHighlight'])
            assert minimum_hue <= highlight.hslHueF() <= maximum_hue, (album.title, mode, highlight.name())
            assert highlight.hslSaturationF() >= (.35 if backgrounds else .65), (album.title, mode, highlight.name())
            if backgrounds:
                assert colors['themeBackground'] == backgrounds[mode]
                if mode != 'dark':
                    assert .47 <= QColor(colors['themeAccent']).hslHueF() <= .62
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(music))
    settings.setValue('theme_fade_seconds', 0)
    window = PlayerWindow(settings)
    try:
        window.show()
        for album, minimum_hue, maximum_hue, backgrounds in loaded:
            window.queue = [(track, album) for track in album.tracks]
            window.play_index(0, autoplay=False)
            for mode in ('any', 'dark', 'light'):
                settings.setValue('artwork_theme_mode', mode)
                window.theme_from_now_playing()
                app.processEvents()
                accent = QColor(app.property('themeHighlight'))
                assert app.property('brandTextColor') == app.property('headingTextColor') == accent.name()
                assert minimum_hue <= accent.hslHueF() <= maximum_hue
                if backgrounds:
                    assert app.property('themeBackground') == backgrounds[mode]
                    if mode != 'dark':
                        assert .47 <= QColor(app.property('themeAccent')).hslHueF() <= .62
                    button_face = control_face(button_paint_rect(window.previous), widget=window.previous)
                    image = window.previous.grab().toImage()
                    assert image.pixelColor(round(button_face.center().x()), round(button_face.top() + 5)).name() == app.property('themeAccent')
                face = control_face(button_paint_rect(window.play), widget=window.play)
                image = window.play.grab().toImage()
                assert image.pixelColor(round(face.center().x()), round(face.top() + 5)) == accent
                image = window.brand.grab().toImage()
                assert any(image.pixelColor(x, y) == accent
                           for y in range(image.height()) for x in range(image.width())), (album.title, mode)
    finally:
        window.close()
        while window.scanners:
            QTest.qWait(10)
print('PASS: three generated reference covers preserve accent hues, landscape backgrounds and blue cloud buttons')
