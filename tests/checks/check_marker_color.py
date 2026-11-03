import os
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app_theme import artwork_theme_colors
from main import PlayerWindow, cd_case_pixmap
from theme_settings import ThemeSettingsDialog, capture_color_theme
from themes import MARKER_COLOR_DEFAULT


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    original = cd_case_pixmap(b'', 'Marker title', case_key='marker').toImage()
    assert app.property('handwritingColor') == MARKER_COLOR_DEFAULT
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.show()
    index = next(index for index in range(dialog.tabs.count()) if dialog.tabs.tabText(index) == 'Album list')
    dialog.tabs.setCurrentIndex(index)
    assert dialog.tabs.currentWidget().isAncestorOf(dialog.marker_color)
    assert dialog.marker_color.isEnabled() and dialog.artwork_theme.isChecked()
    dialog.marker_color.set_color('#254c8a')
    QTest.qWait(60)
    assert app.property('handwritingColor') == '#254c8a'
    assert cd_case_pixmap(b'', 'Marker title', case_key='marker').toImage() != original
    artwork = BytesIO()
    Image.new('RGB', (16, 16), '#d68b40').save(artwork, format='PNG')
    colors = artwork_theme_colors(artwork.getvalue())
    assert 'handwritingColor' not in colors
    window.set_theme('chunky', colors, True)
    assert app.property('handwritingColor') == '#254c8a'
    preset = capture_color_theme([], 'Album colors')
    assert 'marker_text_color' not in preset['colors']
    dialog.presets.append(preset)
    dialog.saved_theme_choice.addItem(preset['name'], preset['id'])
    dialog.saved_theme_choice.setCurrentIndex(dialog.saved_theme_choice.count() - 1)
    assert dialog.marker_color.color().name() == '#254c8a'
    dialog.reject()
    assert app.property('handwritingColor') == MARKER_COLOR_DEFAULT
    assert not settings.contains('marker_text_color')
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.marker_color.set_color('#5a254e')
    dialog.reset_buttons['marker_text_color'].click()
    assert dialog.marker_color.color().name() == MARKER_COLOR_DEFAULT
    dialog.marker_color.set_color('#5a254e')
    dialog.accept()
    restored = ThemeSettingsDialog(QSettings(settings.fileName(), QSettings.IniFormat), window)
    assert restored.marker_color.color().name() == '#5a254e'
    restored.reject()
    window.close()
    while window.scanners:
        QTest.qWait(10)
print('PASS: marker color appears in Album list, redraws sleeves live, survives theme changes, resets, cancels and persists')
