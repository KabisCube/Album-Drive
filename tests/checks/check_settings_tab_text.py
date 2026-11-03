import json
import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog
from themes import COLOR_SETTINGS, button_text_sizing


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('main_font_size', 20)
    settings.setValue('button_font_size', 30)
    settings.setValue('settings_vertical_spacing', -20)
    colors = {key: default for _, _, key, _, default in COLOR_SETTINGS}
    settings.setValue('saved_color_themes', json.dumps([dict(id='long', name='An album with a longer saved theme name', colors=colors)]))
    settings.setValue('selected_color_theme', 'long')
    settings.setValue('artwork_theme_enabled', False)
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(150)
    for width in (600, 850, 1100):
        dialog = ThemeSettingsDialog(settings, window)
        dialog.resize(width, 600)
        dialog.show()
        QTest.qWait(80)
        initial = button_text_sizing().pixel_size
        widths = set()
        for form in dialog.forms.values():
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.LabelRole)
                if item is not None and item.widget() is not None:
                    label = item.widget()
                    widths.add(label.width())
                    assert label.wordWrap()
                    assert label.height() >= label.heightForWidth(label.width())
        assert len(widths) == 1, (width, widths)
        for index in (1, 2, 3, 4, 5, 0, 1):
            dialog.tabs.setCurrentIndex(index)
            QTest.qWait(30)
            assert button_text_sizing().pixel_size == initial, (width, index, initial, button_text_sizing().pixel_size)
        dialog.reject()
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    QTest.qWait(100)
print('PASS: first visits to every settings tab retain the opening text size across widths, large fonts and long theme names')
