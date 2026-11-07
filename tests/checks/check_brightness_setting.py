"""Brightness picks the fixed dark or light theme when dynamic colors are off, and color resets follow it."""

import json
import os
from pathlib import Path
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

app = QApplication([])
app.setStyle('Fusion')

from first_run import FIXED_THEMES
from theme_settings import ThemeSettingsDialog

root = Path(tempfile.mkdtemp())
settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
settings.setValue('welcome_complete', True)
dialog = ThemeSettingsDialog(settings)
dialog.show()
combo = dialog.artwork_theme_mode
items = lambda: [combo.itemData(index) for index in range(combo.count())]
background = dialog.colors['theme_background_color']
reset = dialog.reset_buttons['theme_background_color']

assert dialog.artwork_theme.isChecked() and items() == ['any', 'dark', 'light'] and combo.isEnabled()
dialog.artwork_theme.setChecked(False)
assert items() == ['dark', 'light'] and combo.isEnabled()
assert combo.currentData() == dialog.colors_brightness()
custom = background.color().name()
combo.activated.emit(combo.currentIndex())
assert background.color().name() == custom

for mode in ('light', 'dark'):
    combo.setCurrentIndex(combo.findData(mode))
    combo.activated.emit(combo.currentIndex())
    colors = FIXED_THEMES[f'fixed_{mode}']
    assert background.color().name() == colors['theme_background_color']
    assert all(dialog.colors[key].color().name() == colors[key] for key in ('theme_text_color', 'theme_accent_color'))
    assert reset.isHidden()
    dialog.set_setting_color(background, QColor('#123456'))
    assert not reset.isHidden() and combo.currentData() == mode
    reset.click()
    assert background.color().name() == colors['theme_background_color']
    assert reset.isHidden()

saved = dialog.saved_theme_choice
assert [saved.itemText(index) for index in range(2)] == ['Default light', 'Default dark']
assert saved.findText('Default') < 0
assert saved.currentData() == 'album-drive-default-dark'
combo.setCurrentIndex(combo.findData('light'))
combo.activated.emit(combo.currentIndex())
assert saved.currentData() == 'album-drive-default-light'
dialog.set_setting_color(background, QColor('#ddeeff'))
assert saved.currentData() == 'album-drive-default-light' and dialog.active_color_choice == ''
saved.setCurrentIndex(saved.findData('album-drive-default-dark'))
assert background.color().name() == FIXED_THEMES['fixed_dark']['theme_background_color']
assert combo.currentData() == 'dark'
assert dialog.reset_buttons['artwork_theme_mode'].isHidden()
dialog.artwork_theme.setChecked(True)
assert items() == ['any', 'dark', 'light'] and combo.currentData() == 'any'

combo.setCurrentIndex(combo.findData('dark'))
dialog.artwork_theme.setChecked(False)
assert combo.currentData() == 'dark'
dialog.artwork_theme.setChecked(True)
assert combo.currentData() == 'dark'
dialog.artwork_theme.setChecked(False)
combo.setCurrentIndex(combo.findData('light'))
combo.activated.emit(combo.currentIndex())
dialog.save()
settings.sync()
reopened = QSettings(settings.fileName(), QSettings.IniFormat)
assert reopened.value('artwork_theme_mode') == 'light'
assert reopened.value('theme_background_color') == FIXED_THEMES['fixed_light']['theme_background_color']
assert json.loads(reopened.value('custom_theme_colors'))['theme_background_color'] == FIXED_THEMES['fixed_light']['theme_background_color']
opened = ThemeSettingsDialog(reopened)
assert opened.artwork_theme_mode.currentData() == 'light'
opened.artwork_theme.setChecked(True)
assert opened.artwork_theme_mode.currentData() == 'any'
print('PASS: Brightness drops any without dynamic colors, picks fixed themes, and color resets follow it')
