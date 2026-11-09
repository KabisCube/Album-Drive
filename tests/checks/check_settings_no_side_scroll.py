"""Settings never scrolls sideways: rows stack their titles above controls instead."""
import os
from pathlib import Path
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout

app = QApplication([])
app.setStyle('Fusion')

from main import PlayerWindow, load_app_font
from theme_settings import ThemeSettingsDialog

load_app_font()
root = Path(tempfile.mkdtemp())
(root / 'Music').mkdir()
settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
settings.setValue('folder', str(root / 'Music'))
settings.setValue('welcome_complete', True)
window = PlayerWindow(settings)
window.show()
dialog = ThemeSettingsDialog(settings, window)
dialog.show()
stacked_widths = []
for master in (16, 25):
    dialog.numbers['main_font_size'].setValue(master)
    QTest.qWait(50)
    for width in range(560, 1100, 40):
        dialog.resize(width, 640)
        for index in range(dialog.tabs.count()):
            dialog.tabs.setCurrentIndex(index)
            QTest.qWait(30)
            area = dialog.tabs.currentWidget()
            assert not area.horizontalScrollBar().isVisible(), (master, width, dialog.tabs.tabText(index))
            assert area.widget().width() <= area.viewport().width(), (master, width, area.widget().width(), area.viewport().width())
        wrapped = next(iter(dialog.forms.values())).rowWrapPolicy() == QFormLayout.WrapAllRows
        if wrapped and width >= 640:
            stacked_widths.append((master, width))
dialog.resize(1040, 680)
QTest.qWait(50)
assert next(iter(dialog.forms.values())).rowWrapPolicy() == QFormLayout.DontWrapRows
dialog.reject()
window.close()
print('PASS: no sideways scrolling at any width or text size; wide windows keep side-by-side rows', stacked_widths[:3])
