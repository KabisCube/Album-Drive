import json
import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from settings_store import APPEARANCE_DEFAULTS
from theme_settings import ThemeSettingsDialog, saved_color_themes
from themes import COLOR_SETTINGS


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    values = dict(button_size=48, ui_thickness=150, corner_roundness=42, settings_vertical_spacing=8,
                  folder_vertical_spacing=-4, album_scale=85, main_font_size=15, button_sound_volume=25)
    for key, value in values.items():
        settings.setValue(key, value)
    colors = {key: default for _, _, key, _, default in COLOR_SETTINGS}
    colors['theme_background_color'] = '#203c48'
    preset = dict(id='legacy', name='Legacy album', colors=colors, settings=dict(APPEARANCE_DEFAULTS))
    settings.setValue('saved_color_themes', json.dumps([preset]))
    settings.setValue('selected_color_theme', 'legacy')
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(50)
    deadline = time.monotonic() + 5
    while window.scanners and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert all(settings.value(key, type=int) == value for key, value in values.items())
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.show()
    before = {key: control.value() for key, control in dialog.numbers.items()}
    fonts = dialog.ui_font_choice.currentData()
    for identity in ('album-drive-default', 'legacy'):
        dialog.saved_theme_choice.setCurrentIndex(dialog.saved_theme_choice.findData(identity))
        assert {key: control.value() for key, control in dialog.numbers.items()} == before
        assert (dialog.ui_font_choice.currentData()) == fonts
        assert dialog.rounding_slider.value() == values['corner_roundness']
        dialog.apply()
        assert all(settings.value(key, type=int) == value for key, value in values.items())
    dialog.numbers['button_size'].setValue(52)
    dialog.save_current_colors()
    assert dialog.numbers['button_size'].value() == 52
    window.album_size.setValue(125)
    dialog.apply()
    assert settings.value('album_scale', type=int) == 125
    assert all('settings' not in preset for preset in saved_color_themes(settings))
    dialog.accept()
    window.close()
    QTest.qWait(100)
    restored = PlayerWindow(settings)
    assert app.property('buttonSize') == 52
    assert settings.value('settings_vertical_spacing', type=int) == 8
    restored.close()
    QTest.qWait(100)
    for scanner in list(restored.scanners):
        scanner.requestInterruption()
        scanner.wait()
    QTest.qWait(50)
print('PASS: legacy, Default and saved themes preserve global preferences on select, save, Apply and restart')
