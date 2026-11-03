import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow
from theme_settings import ThemeSettingsDialog
from themes import NUMERIC_DEFAULTS, UI_FONT_DEFAULT


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(50)
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.resize(850, 560)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(30)
    control = dialog.numbers['button_size']
    area = dialog.tabs.currentWidget()
    area.ensureWidgetVisible(control)
    QTest.qWait(20)
    geometry = control.slider.geometry()
    assert dialog.reset_buttons['button_size'].isHidden()
    assert dialog.reset_buttons['button_size'].text() == ''
    assert not dialog.reset_buttons['button_size'].icon().isNull()
    assert dialog.reset_buttons['button_size'].accessibleName() == 'Reset button size to default'
    control.setValue(66)
    QTest.qWait(20)
    assert not dialog.reset_buttons['button_size'].isHidden()
    assert control.slider.geometry() == geometry
    assert settings.value('button_size', type=int) == 44
    dialog.numbers['button_icon_size'].setValue(32)
    dialog.reset_buttons['button_size'].click()
    assert control.value() == 44
    assert dialog.numbers['button_icon_size'].value() == 32
    assert dialog.reset_buttons['button_size'].isHidden()
    QTest.qWait(20)
    assert control.slider.geometry() == geometry
    assert dialog.reset_buttons['button_size'].x() > control.x()
    dialog.numbers['settings_vertical_spacing'].setValue(-8)
    dialog.reset_buttons['settings_vertical_spacing'].click()
    assert dialog.numbers['settings_vertical_spacing'].value() == -12
    dialog.rounding_slider.setValue(0)
    assert not dialog.reset_buttons['corner_roundness'].isHidden()
    dialog.reset_buttons['corner_roundness'].click()
    assert dialog.rounding_slider.value() == NUMERIC_DEFAULTS['corner_roundness']
    dialog.continuous_playback.setChecked(False)
    assert not dialog.reset_buttons['continuous_playback'].isHidden()
    dialog.reset_buttons['continuous_playback'].click()
    assert dialog.continuous_playback.isChecked()
    alternate = next(i for i in range(dialog.ui_font_choice.count()) if dialog.ui_font_choice.itemData(i) != UI_FONT_DEFAULT)
    dialog.ui_font_choice.setCurrentIndex(alternate)
    assert not dialog.reset_buttons['ui_font'].isHidden()
    dialog.reset_buttons['ui_font'].click()
    assert dialog.ui_font_choice.currentData() == UI_FONT_DEFAULT
    dialog.audio_output_choice.addItem('Test output', 'test-output')
    dialog.audio_output_choice.setCurrentIndex(dialog.audio_output_choice.count() - 1)
    dialog.reset_buttons['audio_output_device'].click()
    assert dialog.audio_output_choice.currentData() == ''
    color = dialog.colors['theme_background_color']
    dialog.set_setting_color(color, QColor('#123456'))
    assert not dialog.reset_buttons['theme_background_color'].isHidden()
    dialog.reset_buttons['theme_background_color'].click()
    assert color.color().name() == '#393939'
    assert dialog.reset_buttons['theme_background_color'].isHidden()
    dialog.set_setting_color(color, QColor('#123456'))
    dialog.artwork_theme.setChecked(True)
    assert dialog.reset_buttons['theme_background_color'].isHidden()
    dialog.artwork_theme_mode.setCurrentIndex(dialog.artwork_theme_mode.findData('dark'))
    assert not dialog.reset_buttons['artwork_theme_mode'].isHidden()
    dialog.reset_buttons['artwork_theme_mode'].click()
    assert dialog.artwork_theme_mode.currentData() == 'any'
    dialog.artwork_theme.setChecked(False)
    assert not dialog.reset_buttons['artwork_theme_enabled'].isHidden()
    dialog.reset_buttons['artwork_theme_enabled'].click()
    assert dialog.artwork_theme.isChecked()
    dialog.apply()
    assert settings.value('button_icon_size', type=int) == 32
    dialog.accept()
    reopened = ThemeSettingsDialog(settings, window)
    assert not reopened.reset_buttons['button_icon_size'].isHidden()
    reopened.reset_buttons['button_icon_size'].click()
    assert reopened.numbers['button_icon_size'].value() == 28
    reopened.reject()
    assert settings.value('button_icon_size', type=int) == 32
    dialog = ThemeSettingsDialog(settings, window)
    dialog.restore_defaults()
    assert all(button.isHidden() for button in dialog.reset_buttons.values())
    dialog.show()
    QTest.qWait(20)
    dialog.numbers['button_font_size'].setValue(25)
    dialog.numbers['button_size'].setValue(60)
    area = dialog.tabs.currentWidget()
    area.ensureWidgetVisible(dialog.numbers['button_size'])
    QTest.qWait(20)
    dialog.grab().save('build/setting-reset-preview.png')
    dialog.reject()
    window.close()
    QTest.qWait(50)
print('PASS: per-setting defaults, stable rows, dynamic dependencies, Apply/Cancel and saved changes')
