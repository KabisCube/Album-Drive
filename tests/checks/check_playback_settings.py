"""Playback ordering, dynamic-setting dependencies and smooth Apply transitions."""

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app_theme import artwork_theme_colors
from color_rules import disabled_text_color, settings_title_color
from main import PlayerWindow
from themes import THEME_FADE_MS
from test_library import make_wave
from theme_settings import ThemeSettingsDialog, default_color_themes, saved_color_themes
from themes import FONT_SCALE_KEYS, font_sizes, COLOR_SETTINGS, NUMERIC_DEFAULTS


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


def finish(window):
    if getattr(window, 'theme_fade', None) is not None:
        window.theme_fade.setCurrentTime(THEME_FADE_MS)


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    for title, color in (('A', '#183c72'), ('B', '#e0b558'), ('C', '#256e40')):
        make_wave(root / 'Music' / title / '1.wav')
        make_wave(root / 'Music' / title / '2.wav')
        Image.new('RGB', (64, 64), color).save(root / 'Music' / title / 'cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    try:
        window.show()
        wait_until(lambda: len(window.albums) == 3 and not window.scanners)
        # Intentionally reverse the underlying album sequence in the grid.
        for row, index in enumerate((2, 1, 0)):
            window.grid.item(row).setData(Qt.UserRole, index)
        ordered = [window.albums[i] for i in (2, 1, 0)]
        album = ordered[0]
        assert settings.value('continuous_playback', True, type=bool)
        settings.setValue('continuous_playback', False)
        window.queue = [(track, album) for track in album.tracks]
        window.queue_index = 1
        with patch.object(window, 'play_album') as play, patch.object(window, 'show_album') as show:
            window.media_status_changed(QMediaPlayer.EndOfMedia)
            play.assert_not_called()
            assert not window.queue
            window.queue = [(track, album) for track in album.tracks]
            window.queue_index = 1
            settings.setValue('continuous_playback', True)
            window.media_status_changed(QMediaPlayer.EndOfMedia)
            play.assert_called_once_with(ordered[1], 0)
            show.assert_called_once_with(ordered[1])
            play.reset_mock()
            window.queue = [(track, ordered[-1]) for track in ordered[-1].tracks]
            window.media_status_changed(QMediaPlayer.EndOfMedia)
            play.assert_not_called()  # Last album does not wrap.
        window.queue = [(track, album) for track in album.tracks]
        window.queue_index = 0
        with patch.object(window, 'next_track') as next_track:
            window.media_status_changed(QMediaPlayer.EndOfMedia)
            next_track.assert_called_once()

        settings.setValue('artwork_theme_enabled', False)
        window.apply_settings()
        finish(window)
        before = app.property('themeBackground')
        settings.setValue('artwork_theme_enabled', True)
        window.apply_settings()
        assert app.property('themeBackground') == before
        assert window.theme_fade is not None
        window.theme_fade.setCurrentTime(THEME_FADE_MS // 2)
        assert app.property('themeBackground') not in (before, window.now_playing_theme_colors()['themeBackground'])
        finish(window)

        dialog = ThemeSettingsDialog(settings, window)
        assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == ['General', 'Style', 'Audio', 'File browser', 'Album list', 'Track list']
        assert dialog.tabs.widget(0).isAncestorOf(dialog.continuous_playback)
        assert dialog.tabs.widget(1).isAncestorOf(dialog.saved_theme_choice)
        assert dialog.tabs.widget(1).isAncestorOf(dialog.numbers['ui_thickness'])
        assert dialog.colors['theme_folder_arrow_color'].isHidden()
        assert dialog.tabs.widget(3).isAncestorOf(dialog.numbers['folder_font_size'])
        assert dialog.colors['theme_paper_text_color'].isHidden()
        assert not hasattr(dialog, 'font_choice')
        assert app.property('trackListFamily') == app.property('uiFontFamily')
        title = dialog.option_labels[dialog.colors['theme_text_color']]
        assert not title.isEnabled()
        title.ensurePolished()
        assert title.palette().color(QPalette.Disabled, QPalette.WindowText).getRgb() == disabled_text_color(
            settings_title_color(app.property('textColor'), app.property('themeBackground'))).getRgb()
        assert dialog.continuous_playback.isChecked()
        assert dialog.artwork_theme_mode.isEnabled()
        assert not dialog.colors['theme_brand_text_color'].isEnabled()
        assert dialog.colors['theme_brand_text_color'].property('previewSwatchColor') == app.property('brandTextColor')
        assert not dialog.colors['theme_paper_text_color'].isEnabled()
        base = {key: button.color().name() for key, button in dialog.colors.items()}
        dialog.apply()
        assert {key: button.color().name() for key, button in dialog.colors.items()} == base
        finish(window)
        dialog.artwork_theme.setChecked(False)
        assert title.isEnabled()
        assert dialog.option_labels[dialog.artwork_theme_mode].isEnabled()
        assert dialog.artwork_theme_mode.isEnabled()
        assert dialog.artwork_theme_mode.findData('any') < 0
        assert all(button.isEnabled() for button in dialog.colors.values())
        assert dialog.colors['theme_brand_text_color'].property('previewSwatchColor') is None
        before = app.property('themeBackground')
        dialog.applied.connect(window.apply_settings)
        dialog.apply()
        assert app.property('themeBackground') == before
        assert window.theme_fade is not None
        finish(window)
        dialog.numbers['ui_thickness'].setValue(0)
        assert not dialog.numbers['button_sound_volume'].isEnabled()
        assert not dialog.option_labels[dialog.numbers['button_sound_volume']].isEnabled()
        dialog.numbers['ui_thickness'].setValue(100)
        assert dialog.numbers['button_sound_volume'].isEnabled()
        assert dialog.option_labels[dialog.numbers['button_sound_volume']].isEnabled()
        default_id = default_color_themes()[0]['id']
        assert dialog.saved_theme_choice.findData(default_id) == 0
        dialog.saved_theme_choice.setCurrentIndex(dialog.saved_theme_choice.findData(default_id))
        dialog.rounding_slider.setValue(20)
        dialog.apply()
        assert next(p for p in saved_color_themes(settings) if p['id'] == default_id) == default_color_themes()[0]
        dialog.restore_defaults()
        assert dialog.continuous_playback.isChecked()
        assert dialog.artwork_theme.isChecked()
        assert all(control.value() == (100 if key in FONT_SCALE_KEYS and key not in ('secondary_font_size', 'menu_font_size') else NUMERIC_DEFAULTS[key]) for key, control in dialog.numbers.items())
        dialog.close()
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        QTest.qWait(200)

# Tiny pink cover details should not turn an otherwise blue/gold app pink.
image = Image.new('RGB', (64, 64), '#183c72')
image.paste('#e0b558', (0, 0, 20, 64))
image.paste('#ff00ff', (30, 30, 33, 33))
output = BytesIO()
image.save(output, format='PNG')
for mode in ('any', 'dark', 'light'):
    colors = artwork_theme_colors(output.getvalue(), mode)
    hue = QColor(colors['brandTextColor']).hslHueF()
    assert not .75 < hue < .95
print('PASS: continuous album order/stop, settings dependencies, live logo swatch, immutable Default, smooth Apply, cover accent selection')
