import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog
from themes import button_text_sizing


def wait_until(condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    (root / 'Music' / 'Selected').mkdir()
    (root / 'Other').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('folder', str(root / 'Music' / 'Selected'))
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(50)
    wait_until(lambda: not window.scanners)
    window.edit_theme_settings()
    dialog = window.settings_dialog
    QTest.qWait(50)
    opening_text_size = button_text_sizing().pixel_size
    assert not hasattr(dialog, 'apply_button')
    assert dialog.saved_theme_choice.itemText(0) == 'Default light'
    assert dialog.saved_theme_choice.findText('Custom colors') == -1
    assert dialog.tabs.widget(1).isAncestorOf(dialog.saved_theme_choice)
    assert dialog.option_labels[dialog.colors['theme_accent_color']].text() == 'Accent color'
    assert dialog.option_labels[dialog.colors['theme_highlight_color']].text() == 'Button color'
    for key, title in (('folder_vertical_spacing', 'Vertical spacing'), ('folder_font_size', 'Text scale'),
                       ('logo_font_size', 'Text scale'), ('button_size', 'Size'), ('ui_thickness', 'Thickness'),
                       ('button_sound_volume', 'Volume'), ('hover_rotation', 'Random rotation'), ('main_font_size', 'Text size')):
        assert dialog.option_labels[dialog.numbers[key]].text() == title
    for checkbox in (dialog.continuous_playback, dialog.artwork_theme, dialog.cleaning):
        label = dialog.option_labels[checkbox]
        assert checkbox.text() == ''
        assert label.property('settingFullName') == checkbox.accessibleName()
        index = next(index for index in range(dialog.tabs.count()) if dialog.tabs.widget(index).isAncestorOf(checkbox))
        dialog.tabs.setCurrentIndex(index)
        QTest.qWait(20)
        assert label.geometry().right() < checkbox.parentWidget().geometry().left()
        checked = checkbox.isChecked()
        QTest.mouseClick(label, Qt.LeftButton)
        assert checkbox.isChecked() != checked
        QTest.mouseClick(checkbox, Qt.LeftButton)
        assert checkbox.isChecked() == checked
    form = dialog.forms['Style']
    font_row = form.getWidgetPosition(dialog.ui_font_choice.parentWidget())[0]
    text_row = form.getWidgetPosition(dialog.numbers['main_font_size'].parentWidget())[0]
    assert text_row == font_row + 1
    round_row = form.getWidgetPosition(dialog.rounding_slider.parentWidget())[0]
    sections = [(row, form.itemAt(row, QFormLayout.SpanningRole)) for row in range(form.rowCount())]
    section = next(item.widget().text() for row, item in reversed(sections[:round_row])
                   if item is not None and item.widget() is not None and item.widget().objectName() == 'settingsSection')
    assert section == 'Interface'
    heading_row = next(row for row, item in sections if item is not None and item.widget() is not None
                       and item.widget().objectName() == 'settingsSection' and item.widget().text() == 'Interface')
    thickness_row = form.getWidgetPosition(dialog.numbers['ui_thickness'].parentWidget())[0]
    assert round_row == heading_row + 1
    assert thickness_row == round_row + 1
    assert font_row == thickness_row + 1
    original = dict(dialog.original_settings)
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(30)
    text_size = button_text_sizing().pixel_size
    assert text_size == opening_text_size
    dropdown_size = dialog.ui_font_choice.size()
    for index in (0, 1, 2, 3, 4, 5, 0, 1):
        dialog.tabs.setCurrentIndex(index)
        QTest.qWait(20)
        assert button_text_sizing().pixel_size == text_size
    for spacing in (-40, 40, -20, 0):
        dialog.numbers['settings_vertical_spacing'].setValue(spacing)
        wait_until(lambda: settings.value('settings_vertical_spacing', type=int) == spacing)
        QTest.qWait(30)
        assert button_text_sizing().pixel_size == text_size
        assert dialog.ui_font_choice.size() == dropdown_size
    dialog.numbers['button_size'].setValue(60)
    wait_until(lambda: app.property('buttonSize') == 60)
    dialog.artwork_theme.setChecked(False)
    dialog.set_setting_color(dialog.colors['theme_background_color'], QColor('#244050'))
    wait_until(lambda: settings.value('theme_background_color') == '#244050')
    dialog.save_current_colors()
    QTest.qWait(50)
    assert not list(root.glob('settings-themes/theme-*.ini'))
    dialog.library_folder = str(root / 'Other')
    dialog.queue_preview()
    wait_until(lambda: window.current_folder == root / 'Other')
    dialog.reject()
    assert not dialog.preview_timer.isActive()
    assert window.settings_dialog is None
    wait_until(lambda: window.current_folder == root / 'Music' / 'Selected' and not window.scanners)
    for key in dialog.preview_keys:
        assert settings.value(key) == original.get(key), (key, settings.value(key), original.get(key))
    assert app.property('buttonSize') == int(original['button_size'])
    QTest.qWait(50)
    window.edit_theme_settings()
    dialog = window.settings_dialog
    dialog.numbers['button_size'].setValue(52)
    dialog.accept()
    assert settings.value('button_size', type=int) == 52
    assert app.property('buttonSize') == 52
    assert not hasattr(settings, '_preview_color_themes')
    window.close()
    QTest.qWait(100)
print('PASS: live settings, stable text through spacing, category order, Default first, OK commit and complete Cancel rollback')
