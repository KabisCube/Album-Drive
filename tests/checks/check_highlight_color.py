import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from color_rules import color_contrast
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog, capture_color_theme, saved_color_themes
from themes import COLOR_SETTINGS, button_paint_rect, button_text_color, control_face


def face_color(button):
    image = button.grab().toImage()
    face = control_face(button_paint_rect(button), widget=button)
    return image.pixelColor(round(face.center().x()), round(face.top() + 5)).name()


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    window = PlayerWindow(settings)
    window.show()
    for theme in ('chunky', 'classic'):
        window.set_theme(theme)
        app.processEvents()
        dialog = ThemeSettingsDialog(settings, window)
        dialog.show()
        app.processEvents()
        highlight = app.property('themeHighlight')
        assert highlight != app.property('themeAccent')
        assert app.property('brandTextColor') == app.property('headingTextColor') == highlight
        assert window.play.property('themeRole') == 'highlight'
        assert dialog.action_buttons[-1].property('themeRole') == 'highlight'
        assert face_color(window.play) == highlight, (theme, 'play', face_color(window.play), highlight)
        assert face_color(dialog.action_buttons[-1]) == highlight, (theme, 'OK', face_color(dialog.action_buttons[-1]), highlight)
        assert face_color(dialog.action_buttons[1]) != highlight
        assert color_contrast(QColor(highlight), button_text_color(highlight, highlighted=True)) >= 4.5
        heading = window.findChild(QLabel, 'heading')
        assert heading.palette().windowText().color().name() == app.property('brandTextColor')
        image = window.grab()
        if theme == 'chunky':
            image.save('build/debug/four-color-theme.png')
        preset = capture_color_theme(saved_color_themes(settings), 'Four colors')
        assert preset['colors']['theme_accent_color'] == highlight
        assert preset['colors']['theme_highlight_color'] == app.property('themeAccent')
        assert {prop for _, _, _, prop, _ in COLOR_SETTINGS} <= {bytes(name).decode() for name in app.dynamicPropertyNames()}
        dialog.reject()
        dialog.deleteLater()
        QTest.qWait(1)
    window.close()
    while window.scanners:
        QTest.qWait(10)
print('PASS: play and OK faces, logo and album heading share the fourth accent in both themes, with readable foregrounds and saved color support')
