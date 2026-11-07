"""Text scaling, button geometry, settings layout and saved preferences."""

import os
from pathlib import Path
import tempfile
import time
from io import BytesIO
from PIL import Image

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QFormLayout, QToolButton

from main import PlayerWindow, cd_case_pixmap
from themes import THEME_FADE_MS
from theme_settings import ThemeSettingsDialog, saved_color_themes
from themes import FONT_SCALE_KEYS, font_sizes, NUMERIC_DEFAULTS, MERGED_NUMERIC_SETTINGS, MERGED_COLOR_SETTINGS, ThemedButton, ThemedComboBox
from test_library import make_wave


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    make_wave(root / 'Music' / 'Album' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('button_font_size', 96)
    window = PlayerWindow(settings)
    assert app.property('buttonFontSize') == font_sizes(settings)['button_font_size']
    window.show()
    deadline = time.monotonic() + 8
    while not window.albums and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert window.albums
    dialog = ThemeSettingsDialog(settings, window)
    general = dialog.forms['Style']
    keys = [general.itemAt(row, QFormLayout.FieldRole).widget().objectName()
            for row in range(general.rowCount())
            if general.itemAt(row, QFormLayout.FieldRole) is not None and general.itemAt(row, QFormLayout.FieldRole).widget() is not None]
    assert keys.index('corner_roundnessRow') < keys.index('button_sizeRow')
    assert keys.index('ui_thicknessRow') == keys.index('button_sizeRow') + 1
    assert keys.index('button_font_sizeRow') == keys.index('button_icon_sizeRow') + 1
    assert dialog.numbers['button_font_size'].maximum() == 125
    assert dialog.numbers['button_size'].label.text() == '44 px'
    assert dialog.numbers['button_size'].slider.minimum() == 20
    for alias, canonical in MERGED_NUMERIC_SETTINGS.items():
        assert dialog.numbers[alias] is dialog.numbers[canonical]
    for alias, canonical in MERGED_COLOR_SETTINGS.items():
        assert dialog.colors[alias] is dialog.colors[canonical]
    names = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
    assert names == ['General', 'Style', 'Audio', 'File browser', 'Album list', 'Track list']
    assert not any(key in dialog.numbers for key in ('now_playing_font_size', 'now_playing_heading_font_size', 'timeline_font_size'))
    assert NUMERIC_DEFAULTS['now_playing_font_size'] == 18
    assert NUMERIC_DEFAULTS['now_playing_heading_font_size'] == 13
    assert NUMERIC_DEFAULTS['timeline_font_size'] == 20
    assert dialog.tabs.widget(names.index('File browser')).isAncestorOf(dialog.numbers['logo_font_size'])
    dialog.applied.connect(window.apply_settings)
    dialog.show()
    QTest.qWait(30)
    assert not any(button.isVisible() for button in dialog.tabs.tabBar().findChildren(QToolButton))
    controls = (window.play, window.previous, window.next, window.settings_button,
                window.refresh_button, window.sort_albums, dialog.action_buttons[-1], dialog.library_button)
    original_sizes = [control.size() for control in controls]
    original_hints = [control.sizeHint() for control in controls]
    original_tabs = [dialog.tabs.tabBar().tabSizeHint(i) for i in range(dialog.tabs.count())]
    for text_size, icon_size in ((75, 96), (125, 8), (125, 96)):
        dialog.numbers['button_font_size'].setValue(text_size)
        assert dialog.numbers['button_font_size'].value() == text_size
        dialog.numbers['button_icon_size'].setValue(icon_size)
        dialog.apply()
        QTest.qWait(30)
        assert [control.size() for control in controls] == original_sizes
        assert [control.sizeHint() for control in controls] == original_hints
        assert [dialog.tabs.tabBar().tabSizeHint(i) for i in range(dialog.tabs.count())] == original_tabs
    dialog.numbers['button_font_size'].setValue(100)
    dialog.numbers['button_icon_size'].setValue(NUMERIC_DEFAULTS['button_icon_size'])
    dialog.apply()
    for key in NUMERIC_DEFAULTS:
        if key.endswith('_font_size') and not key.startswith(('now_playing_', 'timeline_')):
            assert key in dialog.numbers, key
    sections = [label.text() for label in dialog.findChildren(QLabel, 'settingsSection')]
    assert {'Music library', 'Saved themes', 'Buttons', 'Playback', 'Tracks', 'Grid', 'Folders'} <= set(sections)
    Path('build').mkdir(exist_ok=True)
    for index, name in enumerate(('general', 'style', 'audio', 'file-browser', 'album-list', 'track-list')):
        dialog.tabs.setCurrentIndex(index)
        QTest.qWait(20)
        dialog.grab().save(f'build/settings-{name}.png')

    for key, control in dialog.numbers.items():
        if key not in MERGED_NUMERIC_SETTINGS and key.endswith('_font_size'):
            control.setValue(110 if key in FONT_SCALE_KEYS else min(25, NUMERIC_DEFAULTS[key] + 3))
    dialog.apply()
    sizes = font_sizes(settings)
    for widget, key in ((window.tree, 'folder_font_size'), (window.brand, 'logo_font_size'),
                        (window.count_label, 'secondary_font_size'), (window.track_title, 'now_playing_font_size'),
                        (window.now_playing_heading, 'now_playing_heading_font_size'),
                        (window.sort_albums, 'dropdown_font_size'), (dialog.tabs.tabBar(), 'button_font_size'),
                        (dialog.library_label, 'main_font_size'), (dialog.action_buttons[-1], 'button_font_size'),
                        (window.album_table, 'track_list_font_size')):
        assert widget.font().pixelSize() == sizes.get(key, NUMERIC_DEFAULTS[key]), (key, widget.font().pixelSize())
    heading = next(label for label in window.findChildren(QLabel, 'heading'))
    assert heading.font().pixelSize() == sizes['heading_font_size']
    section = dialog.findChildren(QLabel, 'settingsSection')[0]
    assert section.font().pixelSize() == sizes['settings_heading_font_size']
    assert window.seek.timestamp_path().boundingRect().height() > 0
    app.setProperty('handwritingFontSize', 12)
    small_title = cd_case_pixmap(b'', 'A').toImage()
    app.setProperty('handwritingFontSize', 48)
    large_title = cd_case_pixmap(b'', 'A').toImage()
    assert small_title != large_title

    heights = []
    for scale in (20, 44, 66):
        dialog.numbers['button_size'].setValue(scale)
        dialog.apply()
        QTest.qWait(30)
        assert all(control.width() <= 300 for control in dialog.findChildren(ThemedButton) + dialog.findChildren(ThemedComboBox))
        assert not any(button.isVisible() for button in dialog.tabs.tabBar().findChildren(QToolButton))
        assert all(dialog.tabs.tabBar().tabSizeHint(index).width() <= 300 for index in range(dialog.tabs.count()))
        heights.append((window.play.height(), window.previous.height(), dialog.library_button.sizeHint().height(),
                        window.sort_albums.height(), dialog.tabs.tabBar().tabSizeHint(0).height()))
    assert all(a < b < c for a, b, c in zip(*heights)), heights
    dialog.tabs.setCurrentIndex(3)
    dialog.grab().save('build/settings-large-buttons.png')
    artwork = BytesIO()
    Image.new('RGB', (16, 16), '#162b47').save(artwork, format='PNG')
    album = window.albums[0]
    album.artwork = artwork.getvalue()
    window.queue = [(track, album) for track in album.tracks]
    window.play_index(0, autoplay=False)
    QTest.qWait(30)
    assert window.play.height() == heights[-1][0], 'Button size changed when the color fade started'
    window.theme_fade.setCurrentTime(THEME_FADE_MS)
    QTest.qWait(30)
    assert window.play.height() == heights[-1][0], 'Button size changed when the color fade finished'

    # All new values travel with saved INI themes and survive reopening.
    dialog.save_current_colors()
    dialog.apply()
    preset = next(preset for preset in saved_color_themes(settings) if preset['id'] == dialog.saved_theme_choice.currentData())
    assert 'settings' not in preset
    assert settings.value('button_size', type=int) == 66
    assert font_sizes(settings)['folder_font_size'] == sizes['folder_font_size']
    dialog.accept()
    cancelled = ThemeSettingsDialog(settings, window)
    cancelled.numbers['button_size'].setValue(20)
    cancelled.reject()
    assert settings.value('button_size', type=int) == 66
    window.close()
    restored = PlayerWindow(settings)
    restored.show()
    QTest.qWait(30)
    assert restored.play.height() == heights[-1][0], (restored.play.height(), restored.play.minimumHeight(), restored.play.maximumHeight(), restored.previous.height(), heights[-1], app.property('buttonSize'), settings.value('button_size'))
    defaults = ThemeSettingsDialog(settings, restored)
    defaults.restore_defaults()
    for key, control in defaults.numbers.items():
        assert control.value() == (100 if key in FONT_SCALE_KEYS and key not in ('secondary_font_size', 'menu_font_size') else NUMERIC_DEFAULTS[key]), key
    defaults.reject()
    restored.close()
    for scanner in list(restored.scanners):
        scanner.requestInterruption()
        scanner.wait()
    QTest.qWait(200)

print('PASS: every text size, button scaling, section layout, Apply/Cancel, defaults and per-theme INI persistence')
