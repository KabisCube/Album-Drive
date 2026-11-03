import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog
from themes import button_text_sizing, font_sizes


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(100)
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.resize(850, 680)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(50)
    control = dialog.numbers['main_font_size']
    label = dialog.option_labels[control]
    button_size = button_text_sizing().pixel_size
    button_heights = [button.height() for button in dialog.action_buttons]
    sizes = {}
    for requested in (13, 17, 18, 19, 20, 24, 25, 19, 18):
        control.setValue(requested)
        QTest.qWait(100)
        assert label.font().pixelSize() == requested
        assert button_text_sizing().pixel_size <= min(25, font_sizes(settings)['button_font_size'])
        assert [button.height() for button in dialog.action_buttons] == button_heights
        assert all(button.height() == button.sizeHint().height() for button in dialog.action_buttons)
        sizes[requested] = QFontMetricsF(label.font()).tightBoundingRect(label.text()).height(), label.width()
    assert sizes[19][0] >= sizes[18][0]
    assert sizes[19][1] >= sizes[18][1]
    for smaller, larger in zip(sorted(sizes), sorted(sizes)[1:]):
        assert sizes[larger][0] >= sizes[smaller][0]
        assert sizes[larger][1] == sizes[smaller][1]
    dialog.reject()
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    QTest.qWait(100)
print('PASS: general text scales consistently, columns stay fixed, and footer heights remain stable')
