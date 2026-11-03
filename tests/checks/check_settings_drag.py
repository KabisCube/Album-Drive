import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider
from main import PlayerWindow
from themes import button_text_sizing


def handle_center(slider):
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    return slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider).center()


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', directory)
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(100)
    window.edit_theme_settings()
    dialog = window.settings_dialog
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(50)
    control = dialog.numbers['button_size']
    dialog.tabs.currentWidget().ensureWidgetVisible(control)
    QTest.qWait(20)
    original_size = app.property('buttonSize')
    original_app_height = window.settings_button.height()
    original_dialog_height = dialog.action_buttons[0].height()
    original_text_size = button_text_sizing().pixel_size
    original_style = app.styleSheet()
    applied = []
    dialog.applied.connect(lambda: applied.append(True))
    QTest.mousePress(control.slider, Qt.LeftButton, pos=handle_center(control.slider))
    control.setValue(60)
    QTest.qWait(100)
    assert not applied
    assert app.property('buttonSize') == original_size
    assert settings.value('button_size', original_size, type=int) == original_size
    assert window.settings_button.height() == original_app_height
    assert app.styleSheet() == original_style
    assert button_text_sizing().pixel_size == original_text_size
    assert dialog.action_buttons[0].height() > original_dialog_height
    assert dialog.property('settingsPreview')['buttonSize'] == 60
    QTest.mouseRelease(control.slider, Qt.LeftButton, pos=handle_center(control.slider))
    assert len(applied) == 1
    assert app.property('buttonSize') == control.value()
    assert not dialog.property('settingsPreview')
    QTest.qWait(50)
    control.setValue(52)
    QTest.qWait(100)
    assert app.property('buttonSize') == 52
    spacing = dialog.numbers['settings_vertical_spacing']
    spacing.slider.setSliderDown(True)
    spacing.setValue(-24)
    QTest.qWait(100)
    assert all(form.verticalSpacing() == -24 for form in dialog.forms.values())
    assert settings.value('settings_vertical_spacing', -12, type=int) == -12
    dialog.reject()
    assert app.property('buttonSize') == original_size
    assert not dialog.property('settingsPreview')
    assert not dialog.slider_preview_timer.isActive()
    window.edit_theme_settings()
    dialog = window.settings_dialog
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(30)
    font = dialog.numbers['main_font_size']
    font.slider.setSliderDown(True)
    font.setValue(21)
    QTest.qWait(100)
    assert dialog.option_labels[font].font().pixelSize() == 21
    assert app.property('mainFontSize') == 16
    dialog.accept()
    assert app.property('mainFontSize') == 21
    assert settings.value('main_font_size', type=int) == 21
    assert not dialog.property('settingsPreview')
    window.close()
    while window.scanners:
        QTest.qWait(10)
print('PASS: settings-only drag previews, unchanged app rendering, one release update, keyboard edits, local spacing, Cancel and OK during drag')
