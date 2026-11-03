"""Shared interface/track fonts, button press travel, spacing and saved preferences."""

import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow
from test_library import make_wave
from theme_settings import ThemeSettingsDialog, saved_color_themes
from themes import COLOR_SETTINGS, ThemedButton, UI_FONT_DEFAULT, resolve_font


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    make_wave(root / 'Music/Album/1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    with patch('themes.play_button_sound') as button_sound:
        window = PlayerWindow(settings)
    window.show()
    deadline = time.monotonic() + 8
    while (not window.albums or window.scanners) and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert window.albums and not window.scanners
    assert window.album_scale_icon.x() < window.album_size.x() < window.sort_albums.x()
    assert window.album_scale_icon.isVisible()
    assert not window.album_scale_icon.grab().isNull()
    window.show_album(window.albums[0])
    QTest.qWait(20)
    assert not window.album_presentation.findChildren(ThemedButton)
    with patch('main.play_case_sound') as case_sound:
        button_sound.reset_mock()
        QTest.mouseClick(window.album_presentation, Qt.LeftButton, pos=QPoint(2, 2))
        assert window.viewed_album is None
        case_sound.assert_called_once_with('close')
        button_sound.assert_not_called()
    window.show_album(window.albums[0])
    track_family = window.album_table.font().family()
    original_ui = app.font().family()
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    folder_index = window.files.index(str(root / 'Music/Album'))
    original_row_height = window.tree.visualRect(folder_index).height()
    assert original_row_height > 0
    dialog.numbers['folder_vertical_spacing'].setValue(20)
    dialog.numbers['settings_vertical_spacing'].setValue(0)
    dialog.apply()
    QTest.qWait(20)
    assert window.tree.visualRect(folder_index).height() == original_row_height + 24
    assert all(form.verticalSpacing() == 0 for form in dialog.forms.values())
    spacing_control = dialog.numbers['settings_vertical_spacing']
    assert spacing_control.slider.minimum() == -spacing_control.slider.maximum()
    assert spacing_control.slider.value() == 0
    spacing_control.setValue(-8)
    dialog.apply()
    assert settings.value('settings_vertical_spacing', type=int) == -8
    assert all(form.verticalSpacing() == -8 for form in dialog.forms.values())
    dialog.numbers['folder_vertical_spacing'].setValue(-8)
    dialog.numbers['settings_vertical_spacing'].setValue(28)
    dialog.apply()
    QTest.qWait(20)
    assert 0 < window.tree.visualRect(folder_index).height() < original_row_height
    assert all(form.verticalSpacing() == 28 for form in dialog.forms.values())
    thickness_control = dialog.numbers['ui_thickness']
    assert thickness_control.label.text() == '4 px'
    assert thickness_control.slider.maximum() == 12
    assert thickness_control.slider.accessibleName() == 'Button thickness'
    thickness_control.slider.setValue(12)
    assert thickness_control.label.text() == '12 px'
    fonts = app.property('availableFonts')
    chosen = next(font for font in fonts if font['family'] != original_ui)
    dialog.select_ui_font(chosen['id'])
    dialog.numbers['ui_thickness'].setValue(200)
    dialog.numbers['button_sound_volume'].setValue(35)
    dialog.apply()
    assert app.font().family() == chosen['family']
    assert window.count_label.font().family() == chosen['family']
    assert window.album_table.font().family() == app.font().family()
    assert app.property('uiThickness') == 200
    assert app.property('buttonSoundVolume') == 35
    reopened = ThemeSettingsDialog(settings, window)
    assert reopened.ui_font_choice.currentData() == chosen['id']
    assert reopened.numbers['ui_thickness'].value() == 200
    assert reopened.numbers['button_sound_volume'].value() == 35
    assert reopened.numbers['folder_vertical_spacing'].value() == -8
    assert reopened.numbers['settings_vertical_spacing'].value() == 28
    assert all(form.verticalSpacing() == 28 for form in reopened.forms.values())
    reopened.select_ui_font(UI_FONT_DEFAULT)
    reopened.numbers['ui_thickness'].setValue(0)
    reopened.numbers['button_sound_volume'].setValue(0)
    reopened.numbers['folder_vertical_spacing'].setValue(40)
    reopened.numbers['settings_vertical_spacing'].setValue(0)
    reopened.reject()
    assert app.font().family() == chosen['family']
    assert settings.value('ui_thickness', type=int) == 200
    assert settings.value('button_sound_volume', type=int) == 35
    assert settings.value('folder_vertical_spacing', type=int) == -8
    assert all(form.verticalSpacing() == 28 for form in dialog.forms.values())
    dialog.save_current_colors()
    dialog.apply()
    saved_id = dialog.saved_theme_choice.currentData()
    saved = next(preset for preset in saved_color_themes(settings) if preset['id'] == saved_id)
    assert 'settings' not in saved
    dialog.saved_theme_choice.setCurrentIndex(0)
    dialog.select_ui_font(UI_FONT_DEFAULT)
    dialog.numbers['ui_thickness'].setValue(0)
    dialog.apply()
    current_family = app.font().family()
    dialog.saved_theme_choice.setCurrentIndex(dialog.saved_theme_choice.findData(saved_id))
    dialog.apply()
    assert app.font().family() == current_family
    assert app.property('uiThickness') == 0
    assert settings.value('settings_vertical_spacing', type=int) == 28
    assert window.album_table.font().family() == app.font().family()
    # Render actual control pixels: the face keeps its size and translates by
    # its depth, independently of button scale and outline width.
    button = ThemedButton()
    button.resize(100, 48)
    button.setProperty('swatchColor', '#ddaa77')
    app.setProperty('cornerRoundness', 0)
    def face_pixels():
        image = button.grab().toImage()
        return {(x, y) for x in range(image.width()) for y in range(image.height())
                if image.pixelColor(x, y).name() == '#ddaa77'}
    for scale in (75, 150):
        app.setProperty('buttonSize', round(scale * .44))
        for thickness, travel in ((0, 0), (50, 2), (100, 4), (200, 8), (300, 12)):
            app.setProperty('uiThickness', thickness)
            button.setDown(False)
            raised = face_pixels()
            button.setDown(True)
            pressed = face_pixels()
            assert raised
            assert pressed == {(x, y + travel) for x, y in raised}, (scale, thickness)
    button.close()
    dialog.restore_defaults()
    dialog.apply()
    expected = resolve_font(fonts, UI_FONT_DEFAULT)['family']
    assert app.font().family() == expected
    assert app.property('uiThickness') == 100
    assert app.property('buttonSoundVolume') == 100
    assert window.tree.visualRect(folder_index).height() == original_row_height
    assert all(form.verticalSpacing() == -12 for form in dialog.forms.values())
    window.show_albums()
    window.grab().save(str(Path('build/previews/customization-preview.png')))
    dialog.close()
    window.close()
    QTest.qWait(100)

print('PASS: album-size hint, shared interface/track font, Apply/Cancel/defaults and rendered press travel at all depths')
