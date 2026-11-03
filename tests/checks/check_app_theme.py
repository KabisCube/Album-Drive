"""Four-second color interpolation with independent UI movement and track lists."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QSplitterHandle

from app_theme import artwork_theme_colors
from color_rules import disabled_text_color, settings_title_color
from main import PlayerWindow
from open_case import color_contrast
from test_library import make_wave
from themes import accent_assets, button_paint_rect, control_face
from theme_settings import ThemeSettingsDialog


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for name, color in (('Blue', '#162b47'), ('Gold', '#e7c977'), ('Empty art', None)):
        make_wave(root / name / 'Album' / '1.wav')
        make_wave(root / name / 'Album' / '2.wav')
        if color:
            Image.new('RGB', (64, 64), color).save(root / name / 'Album' / 'cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Blue'))
    settings.setValue('theme_background_color', '#54585b')
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 1 and not window.scanners)
    assert not app.property('artworkTheme')
    assert app.property('themeBackground') == '#54585b'

    for theme in ('chunky', 'classic'):
        window.set_theme(theme)
        for name in ('Blue', 'Gold'):
            window.scan(root / name)
            wait_until(lambda: not window.scanners)
            previous_background = app.property('themeBackground')
            previous_logo = app.property('brandTextColor')
            album = window.albums[0]
            window.show_album(album)
            assert app.property('themeBackground') == previous_background
            window.queue = [(track, album) for track in album.tracks]
            browser_geometry = window.tree.geometry()
            window.play_index(0, autoplay=False)
            for mode in ('dark', 'light'):
                settings.setValue('artwork_theme_mode', mode)
                assert window.now_playing_theme_colors() == artwork_theme_colors(album.artwork, mode)
            settings.setValue('artwork_theme_mode', 'any')
            colors = artwork_theme_colors(album.artwork)
            assert colors
            assert app.property('artworkTheme')
            assert app.property('themeBackground') == previous_background
            assert not window.findChildren(QLabel, 'themeFadeOverlay')
            animation = window.theme_fade
            assert animation.duration() == 4000
            window.play_index(1, autoplay=False)
            assert window.theme_fade is animation  # Same album preserves progress.
            QTest.qWait(600)
            assert window.album_presentation.progress == 1.0
            assert window.album_presentation.paper_opacity.opacity() == 1.0
            assert window.theme_fade is animation
            animation.pause()  # Keep midpoint pixel checks deterministic.
            # The real color properties must interpolate, rather than jump to
            # the target beneath a fading screenshot of the previous UI.
            with patch.object(app, 'setStyleSheet', wraps=app.setStyleSheet) as restyle, \
                    patch('themes.accent_assets', wraps=accent_assets) as assets:
                animation.setCurrentTime(1000)
                animation.setCurrentTime(2000)
                app.processEvents()
                assert restyle.call_count == 0
                assert assets.call_count == 0
            first, last = QColor(previous_background), QColor(colors['themeBackground'])
            expected_midpoint = QColor(*(round((a + b) / 2) for a, b in
                                        zip(first.getRgb()[:3], last.getRgb()[:3])))
            assert QColor(app.property('themeBackground')) == expected_midpoint
            tree_image = window.tree.grab().toImage()
            assert window.tree.geometry() == browser_geometry
            for x, y in ((1, tree_image.height() // 2), (tree_image.width() - 2, tree_image.height() // 2),
                         (tree_image.width() // 2, 1), (tree_image.width() // 2, tree_image.height() - 2)):
                assert tree_image.pixelColor(x, y).getRgb() == expected_midpoint.darker(110).getRgb()
            for handle in window.findChildren(QSplitterHandle):
                if handle.isVisible():
                    grip = handle.grab().toImage()
                    assert all(grip.pixelColor(x, y) == expected_midpoint
                               for x in range(grip.width()) for y in range(grip.height()))
            image = window.centralWidget().grab().toImage()
            assert image.pixelColor(image.width() - 2, 2) == expected_midpoint
            assert app.property('brandTextColor') == app.property('themeHighlight')
            face = control_face(button_paint_rect(window.play), widget=window.play)
            play_image = window.play.grab().toImage()
            assert play_image.pixelColor(round(face.center().x()), round(face.top() + 5)).name() == app.property('themeHighlight'), theme
            assert window.findChild(QLabel, 'heading').palette().windowText().color().name() == app.property('brandTextColor')
            paper_color = window.album_table.property('paperBackgroundColor')
            window.show_albums(play_sound=False)
            assert not window.album_page.isVisible()
            assert window.theme_fade is animation
            window.show_album(album)
            assert window.album_table.property('paperBackgroundColor') == paper_color
            settings_dialog = ThemeSettingsDialog(settings, window)
            settings_dialog.show()
            animation.setCurrentTime(2200)
            title = settings_dialog.option_labels[settings_dialog.colors['theme_text_color']]
            disabled = title.palette().color(QPalette.Disabled, QPalette.WindowText)
            expected = disabled_text_color(settings_title_color(app.property('textColor'), app.property('themeBackground')))
            assert disabled.getRgb() == expected.getRgb()
            assert settings_dialog.palette().window().color() == QColor(app.property('themeBackground'))
            settings_dialog.reject()
            settings_dialog.deleteLater()
            animation.resume()
            animation.setCurrentTime(4000)
            assert window.theme_fade is None
            assert window.tree.geometry() == browser_geometry
            window_image = window.grab().toImage()
            for handle in window.findChildren(QSplitterHandle):
                if handle.isVisible():
                    origin = handle.mapTo(window, handle.rect().topLeft())
                    assert all(window_image.pixelColor(origin.x() + x, origin.y() + y).getRgb()
                               == QColor(app.property('themeBackground')).getRgb()
                               for x in range(handle.width()) for y in range(handle.height()))
            for prop, value in colors.items():
                assert app.property(prop) == value, prop
            background = QColor(colors['themeBackground'])
            for prop in ('textColor', 'secondaryTextColor'):
                assert color_contrast(background, QColor(colors[prop])) >= 4.5
            assert colors['brandTextColor'] == colors['themeHighlight']
            assert color_contrast(QColor(colors['themeAccent']), QColor(colors['buttonTextColor'])) >= 4.5
            window.play_index(1, autoplay=False)
            assert window.theme_fade is None  # Same album keeps its palette.
            # Browse a different album: only its track list changes color.
            other = 'Gold' if name == 'Blue' else 'Blue'
            window.scan(root / other)
            wait_until(lambda: not window.scanners)
            window.show_album(window.albums[0])
            assert app.property('themeBackground') == background.name()
            assert window.album_table.property('paperBackgroundColor') == (
                '#e7c977' if other == 'Gold' else '#162b47')
            window.show_albums()
            # Sample an unoccupied app surface after the completed fade.
            image = window.centralWidget().grab().toImage()
            assert image.pixelColor(image.width() - 2, 2) == background
            assert settings.value('theme_background_color') == '#54585b'
            assert not settings.contains('theme_button_fill')
            window.apply_settings()
            assert app.property('themeBackground') == background.name()

        # Interrupt a transition with a different Now Playing album.
        window.scan(root / 'Blue')
        wait_until(lambda: not window.scanners)
        window.queue = [(track, window.albums[0]) for track in window.albums[0].tracks]
        window.play_index(0, autoplay=False)
        assert window.theme_fade is not None
        window.theme_fade.setCurrentTime(2000)
        window.scan(root / 'Empty art')
        wait_until(lambda: not window.scanners)
        assert app.property('artworkTheme')  # Folder browsing cannot reset it.
        window.queue = [(track, window.albums[0]) for track in window.albums[0].tracks]
        interrupted_color = app.property('themeBackground')
        window.play_index(0, autoplay=False)
        assert app.property('themeBackground') != '#54585b'
        assert app.property('themeBackground') == interrupted_color
        window.theme_fade.setCurrentTime(4000)
        assert not app.property('artworkTheme')
        assert app.property('themeBackground') == '#54585b'
        assert window.theme_fade is None
        # Late results from previous folders may not change the theme.
        window.scan_complete(window.generation - 1, [], [])
        assert app.property('themeBackground') == '#54585b'

    cover = (root / 'Blue' / 'Album' / 'cover.png').read_bytes()
    assert artwork_theme_colors(cover)
    assert artwork_theme_colors(b'broken') is None
    assert artwork_theme_colors(b'') is None
    window.close()
    QTest.qWait(200)  # Allow the multimedia backend to release the last WAV.
    time.sleep(.05)

print('PASS: Now Playing palettes, independent browsing/track lists, both themes, readable text, 4s fade and missing-art fallback')
