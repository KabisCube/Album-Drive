import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QSize
from PySide6.QtGui import QIcon, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app_theme import simplify_theme_colors
from first_run import FirstRunDialog, theme_save_image
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog
from themes import COLOR_SETTINGS, ThemeSaveIcon


app = QApplication([])
app.setStyle('Fusion')


def pixels(image):
    return image.convertToFormat(QImage.Format_RGBA8888).constBits().tobytes()


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    colors = {key: default for _, _, key, _, default in COLOR_SETTINGS}
    colors.update(theme_background_color='#3b2422', theme_accent_color='#a99b3e', theme_text_color='#d5be55')
    settings.setValue('custom_theme_colors', json.dumps(colors))
    window = PlayerWindow(settings)
    window.resize(1400, 900)
    window.show()
    QTest.qWait(100)
    dialog = ThemeSettingsDialog(settings, window)
    dialog.show()
    guide = FirstRunDialog(settings, dialog)
    guide.show()
    guide.advance()
    guide.advance()
    with patch('first_run.example_image', side_effect=AssertionError('Step 4 used the illustration')):
        guide.advance()
        QTest.qWait(50)
        image = guide.save_preview.image.toImage()
        assert pixels(image) == pixels(theme_save_image(window).toImage())
        assert image.pixelColor(2, 2).name() == app.property('themeBackground')
        updated = {prop: app.property(prop) for _, _, _, prop, _ in COLOR_SETTINGS}
        updated.update(themeBackground='#d8c8a4', themeAccent='#577c83', textColor='#344151')
        window.set_theme('chunky', simplify_theme_colors(updated), False)
        QTest.qWait(100)
        current = guide.save_preview.image.toImage()
        assert current != image
        assert current.pixelColor(2, 2).name() == app.property('themeBackground')
        assert pixels(current) == pixels(theme_save_image(window).toImage())
        fallback = theme_save_image(None).toImage()
        assert fallback.pixelColor(2, 2).name() == app.property('themeBackground')
    icon = ThemeSaveIcon().pixmap(QSize(128, 128), QIcon.Normal, QIcon.Off).toImage()
    assert any(icon.pixelColor(x, y).alpha() for y in range(128) for x in range(60))
    assert any(icon.pixelColor(x, y).alpha() for y in range(128) for x in range(75, 128))
    assert all(icon.pixelColor(x, y).alpha() == 0 for y in range(128) for x in range(74, 83))
    guide.reject()
    assert not guide.save_preview.refresh_timer.isActive()
    dialog.reject()
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    QTest.qWait(100)
print('PASS: nested setup captures the actual toolbar, follows theme changes, uses themed fallback and separates brush/save glyphs')
