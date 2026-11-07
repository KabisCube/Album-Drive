import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow
from theme_settings import ThemeSettingsDialog


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(50)
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.resize(850, 560)
    dialog.show()
    QTest.qWait(30)
    for key, values in (('button_size', (66, 24, 44)), ('settings_vertical_spacing', (20, -8, 0))):
        control = dialog.numbers[key]
        index = next(i for i in range(dialog.tabs.count()) if dialog.tabs.widget(i).isAncestorOf(control))
        dialog.tabs.setCurrentIndex(index)
        area = dialog.tabs.currentWidget()
        bar = area.verticalScrollBar()
        for value in values:
            area.ensureWidgetVisible(control.slider, 0, 30)
            QTest.qWait(20)
            content_y = control.slider.mapTo(area.widget(), QPoint(0, control.slider.height() // 2)).y()
            bar.setValue(content_y - area.viewport().height() // 2)
            before = control.slider.mapTo(dialog, QPoint(0, control.slider.height() // 2)).y()
            control.setValue(value)
            dialog.apply()
            QTest.qWait(40)
            after = control.slider.mapTo(dialog, QPoint(0, control.slider.height() // 2)).y()
            assert abs(after - before) <= 2 or bar.value() in (bar.minimum(), bar.maximum()), (key, value, before, after)
            assert area.viewport().rect().contains(control.slider.mapTo(area.viewport(), control.slider.rect().center()))
            scroll = bar.value()
            QTest.qWait(30)
            assert bar.value() == scroll
    dialog.resize(480, 320)
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(30)
    area = dialog.tabs.currentWidget()
    horizontal, vertical = area.horizontalScrollBar(), area.verticalScrollBar()
    assert not horizontal.isVisible() and vertical.isVisible()
    dialog.reject()
    window.close()
    QTest.qWait(50)
print('PASS: active slider stays in place through button-size and spacing changes, including compact rows')
