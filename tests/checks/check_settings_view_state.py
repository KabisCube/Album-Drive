import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow
from theme_settings import ThemeSettingsDialog


def opened(settings, window):
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.resize(560, 360)
    dialog.show()
    QTest.qWait(50)
    return dialog


def positions(dialog):
    return {dialog.tabs.tabText(index): [dialog.tabs.widget(index).horizontalScrollBar().value(),
                                        dialog.tabs.widget(index).verticalScrollBar().value()]
            for index in range(dialog.tabs.count())}


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    filename = str(Path(directory) / 'settings.ini')
    settings = QSettings(filename, QSettings.IniFormat)
    settings.setValue('folder', directory)
    window = PlayerWindow(settings)
    window.show()
    dialog = opened(settings, window)
    for index, offset in ((1, 180), (4, 95)):
        dialog.tabs.setCurrentIndex(index)
        QTest.qWait(20)
        area = dialog.tabs.currentWidget()
        area.verticalScrollBar().setValue(offset)
        area.horizontalScrollBar().setValue(35)
    assert dialog.tabs.tabText(dialog.tabs.currentIndex()) == 'Album list'
    expected = positions(dialog)
    assert expected['Style'][1] == 180 and expected['Album list'][1] == 95
    dialog.reject()
    saved = settings.value('settings_view_state')
    hidden = ThemeSettingsDialog(settings, window)
    hidden.reject()
    assert settings.value('settings_view_state') == saved
    restored_settings = QSettings(filename, QSettings.IniFormat)
    dialog = opened(restored_settings, window)
    assert dialog.tabs.tabText(dialog.tabs.currentIndex()) == 'Album list'
    assert positions(dialog) == expected, (positions(dialog), expected)
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(20)
    dialog.tabs.currentWidget().verticalScrollBar().setValue(230)
    expected = positions(dialog)
    dialog.accept()
    dialog = opened(settings, window)
    assert dialog.tabs.tabText(dialog.tabs.currentIndex()) == 'Style'
    assert positions(dialog) == expected
    dialog.tabs.setCurrentIndex(2)
    QTest.qWait(20)
    expected = positions(dialog)
    dialog.close()
    dialog = opened(settings, window)
    assert dialog.tabs.tabText(dialog.tabs.currentIndex()) == 'Audio'
    assert positions(dialog) == expected
    dialog.reject()
    settings.setValue('settings_view_state', json.dumps({'tab': 'Style', 'scroll': {'Style': [10 ** 100, -500]}}))
    dialog = opened(settings, window)
    area = dialog.tabs.currentWidget()
    assert area.horizontalScrollBar().value() == area.horizontalScrollBar().maximum()
    assert area.verticalScrollBar().value() == 0
    dialog.reject()
    settings.setValue('settings_view_state', '{invalid')
    dialog = opened(settings, window)
    assert dialog.tabs.currentIndex() == 0
    dialog.reject()
    window.close()
    while window.scanners:
        QTest.qWait(10)
print('PASS: settings tab and independent horizontal/vertical scroll positions persist through Cancel, OK, close and restart; invalid state clamps safely')
