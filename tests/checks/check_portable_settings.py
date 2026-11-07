"""Portable settings, color-only theme files, migration, relocation and Linux launcher."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app_identity import install_desktop_entry
from main import PlayerWindow
from settings_store import APPEARANCE_DEFAULTS, create_app_settings, theme_directory, write_theme_files
from theme_settings import ThemeSettingsDialog, saved_color_themes
from themes import COLOR_SETTINGS, NUMERIC_DEFAULTS
from test_library import make_wave


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    make_wave(root / 'Music' / 'Album' / '1.wav')
    legacy = QSettings(str(root / 'legacy.ini'), QSettings.IniFormat)
    colors = {key: default for _, _, key, _, default in COLOR_SETTINGS}
    colors['theme_background_color'] = '#203c48'
    preset = dict(id='old-preset', name='AB/CD: A "theme"?', colors=colors,
                  settings=dict(APPEARANCE_DEFAULTS, corner_roundness=67, button_font_size=19))
    preset['settings'].pop('button_size')
    preset['settings']['button_scale'] = 125
    legacy.setValue('button_scale', 150)
    legacy.setValue('saved_color_themes', json.dumps([preset]))
    legacy.setValue('selected_color_theme', 'old-preset')
    legacy.setValue('artwork_theme_enabled', False)
    legacy.setValue('folder', str(root / 'Music'))
    legacy.setValue('volume', 43)
    legacy.sync()
    portable = create_app_settings(root / 'Release', legacy)
    folder = root / 'Release' / 'themes'
    assert Path(portable.fileName()).resolve() == (folder.parent / 'settings.ini').resolve()
    assert portable.value('volume', type=int) == 43
    assert legacy.contains('saved_color_themes')  # Migration is read-only at source.
    assert not portable.contains('saved_color_themes')
    files = list(folder.glob('theme-*.ini'))
    assert len(files) == 1 and files[0].resolve().is_relative_to(folder.resolve())
    text = files[0].read_text(encoding='utf-8')
    assert '[Colors]' in text and '[Settings]' not in text and '[Theme]' in text
    assert 'settings' not in saved_color_themes(portable)[2]

    # Changes to a theme INI are respected at startup, including its settings.
    theme = QSettings(str(files[0]), QSettings.IniFormat)
    theme.setValue('Colors/theme_background_color', '#27495a')
    theme.setValue('Settings/corner_roundness', 73)
    theme.remove('Settings/button_size')
    theme.setValue('Settings/button_scale', 150)
    theme.sync()
    window = PlayerWindow(portable)
    window.show()
    deadline = time.monotonic() + 8
    while (window.scanners or not window.albums) and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert app.property('themeBackground') == '#27495a'
    assert app.property('cornerRoundness') == NUMERIC_DEFAULTS['corner_roundness']
    assert app.property('buttonSize') == 66
    dialog = ThemeSettingsDialog(portable, window)
    dialog.applied.connect(window.apply_settings)
    dialog.numbers['button_font_size'].setValue(110)
    dialog.apply()
    assert portable.value('button_font_scale', type=int) == 110
    assert 'settings' not in saved_color_themes(portable)[2]
    count = len(list(folder.glob('theme-*.ini')))
    dialog.accept()
    cancelled = ThemeSettingsDialog(portable, window)
    cancelled.save_current_colors()
    cancelled.reject()
    assert len(list(folder.glob('theme-*.ini'))) == count
    window.close()
    QTest.qWait(100)
    portable.sync()

    shutil.copytree(root / 'Release', root / 'Moved app')
    moved = create_app_settings(root / 'Moved app', legacy)
    assert theme_directory(moved) == (root / 'Moved app' / 'themes').resolve()
    assert moved.value('volume', type=int) == 43
    assert saved_color_themes(moved)[2]['colors']['theme_background_color'] == '#27495a'
    assert moved.value('button_font_scale', type=int) == 110
    assert 'settings' not in saved_color_themes(moved)[2]
    # Migrating a newer source install copies its theme INIs too.
    next_install = create_app_settings(root / 'Next install', moved)
    assert saved_color_themes(next_install)[2]['id'] == 'old-preset'
    write_theme_files(next_install, saved_color_themes(next_install))
    assert len(list(theme_directory(next_install).glob('theme-*.ini'))) == 1

    shutil.copytree(root / 'Release', root / 'Old layout')
    (root / 'Old layout' / 'settings.ini').rename(root / 'Old layout' / 'themes' / 'settings.ini')
    migrated = create_app_settings(root / 'Old layout', legacy)
    assert Path(migrated.fileName()).resolve() == (root / 'Old layout' / 'settings.ini').resolve()
    assert migrated.value('button_font_scale', type=int) == 110
    assert migrated.value('volume', type=int) == 43
    assert saved_color_themes(migrated)[2]['colors']['theme_background_color'] == '#27495a'
    migrated.setValue('volume', 62)
    migrated.sync()
    assert create_app_settings(root / 'Old layout', legacy).value('volume', type=int) == 62

    executable = root / 'Moved app' / 'AlbumDrive'
    executable.write_text('placeholder')
    desktop = install_desktop_entry(executable, root / 'desktop-data')
    command = str(executable.resolve()).replace('\\', '\\\\\\\\')
    assert f'Exec="{command}"' in desktop.read_text()
    assert (root / 'desktop-data/icons/hicolor/scalable/apps/album-drive.svg').exists()

print('PASS: portable settings.ini, per-theme colors/options, legacy migration, external edits, Cancel, relocation and Linux launcher')
