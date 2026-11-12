"""Case cues, playback completion, settings dismissal, device choice and highlights."""

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import Mock, patch

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider
from app_identity import APP_NAME
from app_theme import artwork_theme_colors
from audio_devices import selected_output
from main import PlayerWindow
from open_case import color_contrast
from test_library import make_wave
from theme_settings import ThemeSettingsDialog
from themes import control_face


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    for name, color in (('Blue', '#183c72'), ('Gold', '#e0b558')):
        make_wave(root / 'Music' / name / '1.wav')
        Image.new('RGB', (32, 32), color).save(root / 'Music' / name / 'cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('welcome_complete', True)
    settings.setValue('continuous_playback', False)
    window = PlayerWindow(settings)
    try:
        window.show()
        wait_until(lambda: len(window.albums) == 2 and not window.scanners)
        assert not hasattr(window, 'refresh_button')
        album = window.albums[0]
        header_controls = (window.album_size, window.sort_albums, window.save_theme_button,
                           window.tidy_button)
        option = QStyleOptionSlider()
        window.album_size.initStyleOption(option)
        handle = window.album_size.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, window.album_size)
        knob = control_face(QRectF(handle), widget=window.album_size).center().toPoint()
        active_knob = window.album_size.grab().toImage().pixelColor(knob)
        with patch('main.play_case_sound') as sound:
            window.show_album(album)
            sound.assert_called_once_with('open')
            assert window.settings_button.isEnabled()
            assert all(not control.isEnabled() for control in header_controls)
            assert window.album_size.grab().toImage().pixelColor(knob) != active_knob
            assert all(effect.opacity() == .2 for effect in window.album_header_opacities)
            value = window.album_size.value()
            QTest.mouseClick(window.album_size, Qt.LeftButton, pos=window.album_size.rect().topRight())
            assert window.album_size.value() == value
            for control in header_controls[1:]:
                signal = control.activated if control is window.sort_albums else control.clicked
                clicks = QSignalSpy(signal)
                QTest.mouseClick(control, Qt.LeftButton)
                assert clicks.count() == 0
            window.grid.tidyStateChanged.emit(False)
            assert not window.tidy_button.isEnabled()
            window.show_album(album)
            assert sound.call_count == 1
            window.show_albums()
            assert sound.call_args.args == ('close',)
            assert all(control.isEnabled() for control in header_controls)
            assert window.album_size.grab().toImage().pixelColor(knob) == active_knob
            window.show_album(album)
            window.queue = [(track, album) for track in album.tracks]
            window.play_index(0, autoplay=False)
            assert window.windowTitle() == f'{APP_NAME} — {album.tracks[0].title}'
            window.save_session()
            sound.reset_mock()
            window.media_status_changed(QMediaPlayer.EndOfMedia)
            sound.assert_called_once_with('close')
            assert window.viewed_album is None and not window.album_page.isVisible()
            assert not window.queue and window.queue_index == -1
            assert window.player.source().isEmpty()
            assert window.windowTitle() == APP_NAME
            assert not settings.contains('session/track')
            assert window.view_fade is not None
            window.view_fade.setCurrentTime(window.view_fade.duration())
            if window.theme_fade is not None:
                window.theme_fade.setCurrentTime(window.theme_fade.duration())
            assert window.library_opacity.opacity() == 1
            assert not app.property('artworkTheme')
            assert app.property('themeBackground') == window.saved_theme_colors()['themeBackground']

            ordered = [window.albums[window.grid.item(i).data(Qt.UserRole)] for i in range(window.grid.count())]
            settings.setValue('continuous_playback', True)
            window.show_album(ordered[0])
            window.queue = [(track, ordered[0]) for track in ordered[0].tracks]
            window.play_index(0, autoplay=False)
            assert window.next.isEnabled()
            window.next.click()
            window.player.pause()
            assert window.queue[0][1].folder == ordered[1].folder
            assert window.viewed_album.folder == ordered[1].folder
            assert not window.next.isEnabled()
            sound.reset_mock()
            window.media_status_changed(QMediaPlayer.EndOfMedia)
            sound.assert_called_once_with('close')
            assert not window.queue and window.viewed_album is None

        window.edit_theme_settings()
        dialog = window.settings_dialog
        assert not dialog.isModal()
        assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == [
            'General', 'Style', 'Audio', 'File browser', 'Album list', 'Track list']
        assert dialog.tabs.widget(2).isAncestorOf(dialog.audio_output_choice)
        assert all(dialog.tabs.widget(2).isAncestorOf(dialog.numbers[key]) for key in
                   ('button_sound_volume', 'case_open_volume', 'case_close_volume'))
        dialog.numbers['ui_thickness'].setValue(200)
        window.show_album(album)
        QTest.mouseClick(window.album_page, Qt.LeftButton)
        assert window.settings_dialog is None and not dialog.isVisible()
        assert settings.value('ui_thickness', 100, type=int) == 200
        assert window.viewed_album is album  # The release must not dismiss its track view.
        window.show_albums()

        # An explicit device survives persistence and unplugging falls back to OS default.
        chosen = Mock()
        chosen.id.return_value = QByteArray(b'headphones')
        chosen.description.return_value = 'Example headphones'
        with patch('theme_settings.QMediaDevices.audioOutputs', return_value=[chosen]):
            dialog = ThemeSettingsDialog(settings, window)
            dialog.audio_output_choice.setCurrentIndex(1)
            dialog.save()
            identity = settings.value('audio_output_device')
            assert identity == b'headphones'.hex()
            app.setProperty('audioOutputDevice', identity)
            assert selected_output() is chosen
            dialog.close()
        fallback = Mock()
        with patch('audio_devices.QMediaDevices.audioOutputs', return_value=[]), patch(
                'audio_devices.QMediaDevices.defaultAudioOutput', return_value=fallback):
            assert selected_output() is fallback
        app.setProperty('audioOutputDevice', '')
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        QTest.qWait(200)

# A prominent low-contrast orange must remain orange in every brightness mode.
image = Image.new('RGB', (64, 64), '#fafcfb')
image.paste('#d49850', (0, 0, 22, 64))
output = BytesIO()
image.save(output, format='PNG')
for mode in ('any', 'dark', 'light'):
    colors = artwork_theme_colors(output.getvalue(), mode)
    accent, background = QColor(colors['themeAccent']), QColor(colors['themeBackground'])
    assert .05 < accent.hslHueF() < .15
    assert accent.hslSaturationF() > .6
    assert color_contrast(accent, background) >= 1.3
    assert color_contrast(accent, QColor(colors['buttonTextColor'])) >= 4.5
print('PASS: case cues, end-of-album/list reset and fade, title order, outside-click save, audio routing, saturated highlight hue')
