import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from test_library import make_wave
from theme_settings import ThemeSettingsDialog, saved_color_themes
from themes import COLOR_SETTINGS


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    make_wave(root / 'Music' / 'Test Album' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    deadline = time.monotonic() + 5
    while (not window.albums or window.scanners) and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert window.albums and not window.scanners
    album = window.albums[0]
    window.queue = [(album.tracks[0], album)]
    window.queue_index = 0
    snapshot = {key: app.property(prop) for _, _, key, prop, _ in COLOR_SETTINGS}
    dynamic = settings.value('artwork_theme_enabled')
    selected = settings.value('selected_color_theme')
    assert not window.save_theme_button.icon().isNull()
    assert window.save_theme_button.width() > window.settings_button.width()
    assert window.save_theme_button.iconSize().width() > window.save_theme_button.iconSize().height()
    QTest.mouseClick(window.save_theme_button, Qt.LeftButton)
    presets = saved_color_themes(settings)
    assert len(presets) == 3
    assert presets[-1]['name'] == album.title
    assert presets[-1]['colors'] == snapshot
    assert window.theme_toast.isVisible()
    assert window.theme_toast.text() == f'Theme Saved as "{album.title}"'
    assert window.rect().contains(window.theme_toast.geometry())
    assert settings.value('artwork_theme_enabled') == dynamic
    assert settings.value('selected_color_theme') == selected
    dialog = ThemeSettingsDialog(settings, window)
    window.settings_dialog = dialog
    dialog.show()
    window.save_current_theme()
    assert len(saved_color_themes(settings)) == 4
    assert dialog.saved_theme_choice.findText(f'{album.title} (2)') >= 0
    dialog.reject()
    window.settings_dialog = None
    window.theme_toast_timer.setInterval(1)
    QTest.qWait(30)
    assert not window.theme_toast.isVisible()
    window.close()
    QTest.qWait(100)
print('PASS: one-click theme capture, persistence, album names, duplicates, toast, settings sync and setup picture')
