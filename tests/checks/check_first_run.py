"""Library and button setup, theme choices, previews and first-run persistence."""

import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QFormLayout

from themes import ChunkyCheckBox
from first_run import FIXED_THEMES, FirstRunDialog, needs_first_run, system_theme_choice
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog


app = QApplication([])
app.setStyle('Fusion')
Path('build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    fresh = QSettings(str(root / 'fresh.ini'), QSettings.IniFormat)
    assert needs_first_run(fresh)
    fresh.setValue('storage_version', 1)
    assert needs_first_run(fresh)
    fresh.setValue('window_geometry', b'old')
    assert not needs_first_run(fresh)
    fresh.setValue('welcome_started', True)
    assert needs_first_run(fresh)
    fresh.setValue('welcome_complete', True)
    assert not needs_first_run(fresh)

    settings = QSettings(str(root / 'window.ini'), QSettings.IniFormat)
    (root / 'empty').mkdir()
    settings.setValue('folder', str(root / 'empty'))
    settings.setValue('browser_root', str(root / 'empty'))
    window = PlayerWindow(settings)
    window.show()
    for scheme, mode in ((Qt.ColorScheme.Dark, 'fixed_dark'), (Qt.ColorScheme.Light, 'fixed_light'),
                         (Qt.ColorScheme.Unknown, 'any')):
        with patch('PySide6.QtGui.QStyleHints.colorScheme', return_value=scheme):
            assert system_theme_choice() == mode
    guide = FirstRunDialog(settings, window)
    guide.show()
    app.processEvents()
    assert guide.selected_mode() == 'any'
    assert guide.heading.text() == 'Choose your music library'
    assert guide.pages.currentIndex() == 0
    assert not guide.back_button.isVisible()
    (root / 'New music').mkdir()
    with patch('first_run.choose_music_directory', return_value=str(root / 'New music')):
        guide.library_button.click()
    assert guide.library_folder == str(root / 'New music')
    assert settings.value('browser_root') == str(root / 'empty')
    guide.grab().save('build/welcome-library.png')
    guide.advance()
    app.processEvents()
    assert not guide.heading.isVisible()
    assert not guide.reminder.isVisible()
    assert guide.dynamic_category.isAncestorOf(guide.subheading)
    assert all(isinstance(radio, ChunkyCheckBox) for radio in guide.choices.values())
    guide.choices['dark'].click()
    assert guide.selected_mode() == 'dark'
    assert sum(radio.isChecked() for radio in guide.choices.values()) == 1
    assert abs(guide.dynamic_category.width() - guide.fixed_category.width()) <= 1
    assert all(guide.dynamic_category.isAncestorOf(guide.choices[mode]) for mode in ('any', 'dark', 'light'))
    assert guide.fixed_category.isAncestorOf(guide.choices['fixed_dark'])
    assert guide.pages.currentIndex() == 1
    assert guide.back_button.isVisible()
    images = [label.pixmap().toImage() for label in guide.pages.widget(1).findChildren(QLabel)
              if not label.pixmap().isNull()]
    assert len(images) == 5
    assert all(image.width() == image.height() for image in images)
    assert all(a != b for i, a in enumerate(images) for b in images[i + 1:])
    assert any('Settings → Style' in label.text() for label in guide.findChildren(QLabel))
    guide.grab().save('build/welcome-colors.png')
    guide.choices['light'].setChecked(True)
    guide.advance()
    assert guide.heading.isVisible()
    assert guide.heading.text() == 'Make it feel right'
    before = {prop: app.property(prop) for prop in ('uiThickness', 'cornerRoundness', 'buttonSoundVolume')}
    guide.button_thickness.setValue(200)
    guide.button_roundness.setValue(75)
    guide.button_volume.setValue(30)
    assert app.property('uiThickness') == 200
    assert app.property('cornerRoundness') == 75
    assert app.property('buttonSoundVolume') == 30
    guide.grab().save('build/welcome-buttons.png')
    assert guide.pages.currentIndex() == 2
    assert guide.pages.count() == 3
    assert guide.step_label.text() == 'Step 3 of 3'
    assert guide.next_button.text() == 'Start listening'
    assert guide.next_button.property('themeRole') == 'highlight'
    assert guide.back_button.isVisible()
    guide.back_button.click()
    assert guide.selected_mode() == 'light'
    guide.reject()
    assert {prop: app.property(prop) for prop in before} == before
    assert not settings.contains('welcome_complete')
    assert not settings.contains('artwork_theme_enabled')
    assert settings.value('browser_root') == str(root / 'empty')

    for mode in ('any', 'dark', 'light', 'fixed_dark', 'fixed_light'):
        settings = QSettings(str(root / f'{mode}.ini'), QSettings.IniFormat)
        guide = FirstRunDialog(settings, window)
        assert guide.selected_mode() == 'any'
        guide.choices[mode].setChecked(True)
        guide.advance()
        guide.advance()
        guide.advance()
        settings.sync()
        reopened = QSettings(settings.fileName(), QSettings.IniFormat)
        assert not needs_first_run(reopened)
        assert reopened.value('artwork_theme_enabled', type=bool) == (not mode.startswith('fixed'))
        assert reopened.value('artwork_theme_mode') == mode.removeprefix('fixed_')
        if mode.startswith('fixed'):
            assert reopened.value('theme_background_color') == FIXED_THEMES[mode]['theme_background_color']
            assert json.loads(reopened.value('custom_theme_colors')) == FIXED_THEMES[mode]
        guide.deleteLater()
    window.settings.setValue('artwork_theme_enabled', True)
    window.settings.setValue('artwork_theme_mode', 'dark')
    settings_dialog = ThemeSettingsDialog(window.settings, window)
    settings_dialog.applied.connect(window.apply_settings)
    settings_dialog.show()
    settings_dialog.tabs.setCurrentIndex(0)
    app.processEvents()
    button = settings_dialog.guide_button
    assert button.isVisible() and button.text() == 'Start'
    form = settings_dialog.forms['General']
    assert form.itemAt(0, QFormLayout.SpanningRole).widget().text() == 'Music library'
    assert form.itemAt(1, QFormLayout.LabelRole).widget().text() == 'First time setup'
    assert form.itemAt(1, QFormLayout.FieldRole).widget() is button
    assert form.itemAt(2, QFormLayout.LabelRole).widget().text() == 'Root folder'
    assert form.itemAt(2, QFormLayout.FieldRole).widget() is settings_dialog.library_button
    assert settings_dialog.library_button.text() == 'Choose'
    assert not hasattr(settings_dialog, 'save_colors_button')
    opened = []
    def close_tutorial():
        guide = app.activeModalWidget()
        opened.append(isinstance(guide, FirstRunDialog) and guide.selected_mode() == 'dark')
        if guide:
            guide.reject()
    QTimer.singleShot(0, close_tutorial)
    QTest.mouseClick(settings_dialog.guide_button, Qt.LeftButton)
    assert opened == [True]
    assert window.settings.value('artwork_theme_mode') == 'dark'
    def finish_tutorial():
        guide = app.activeModalWidget()
        opened.append(isinstance(guide, FirstRunDialog))
        if isinstance(guide, FirstRunDialog):
            guide.choices['light'].setChecked(True)
            guide.advance()
            guide.advance()
            guide.advance()
        elif guide:
            guide.reject()
    QTimer.singleShot(0, finish_tutorial)
    QTest.mouseClick(settings_dialog.guide_button, Qt.LeftButton)
    assert opened == [True, True]
    assert window.settings.value('artwork_theme_mode') == 'light'
    assert settings_dialog.artwork_theme_mode.currentData() == 'light'
    settings_dialog.grab().save('build/settings-tutorial-access.png')
    settings_dialog.close()
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    app.processEvents()

print('PASS: five illustrated choices, default any, Back/Cancel and first-run completion/retry')
