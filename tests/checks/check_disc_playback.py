"""Disc browser isolation/removal, native transport regression and fade settings."""

import ctypes as ct
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import Mock, patch

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow
from themes import THEME_FADE_MAX_SECONDS, THEME_FADE_MS
from optical_discs import Disc, prepare_audio
from test_library import make_wave
from test_optical_discs import toc
from optical_discs import parse_toc
from theme_settings import ThemeSettingsDialog


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
    music = root / 'Music'
    for name, color in (('Blue', '#183c72'), ('Gold', '#e0b558')):
        make_wave(music / name / '1.wav')
        Image.new('RGB', (32, 32), color).save(music / name / 'cover.png')
    data_disc = root / 'Data CD'
    make_wave(data_disc / 'Disc album' / '1.wav')
    Image.new('RGB', (32, 32), '#2d803f').save(data_disc / 'Disc album' / 'cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(music))
    settings.setValue('browser_root', str(music))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    try:
        window.show()
        wait_until(lambda: len(window.albums) == 2 and not window.scanners)
        # Enable the real native transport logic while replacing only its shell calls.
        # The player is a real QMediaPlayer instance (which has no .PlayingState).
        toolbar = window.taskbar
        toolbar.enabled = True
        toolbar.interface = ct.c_void_p(1)
        toolbar.hwnd = 1
        toolbar.icons = dict(previous=1, play=2, pause=3, next=4)
        toolbar.call = Mock(return_value=0)
        blue, gold = sorted(window.albums, key=lambda album: album.folder.name)
        for album in (blue, gold, blue):
            window.queue = [(track, album) for track in album.tracks]
            window.play_index(0, autoplay=False)
            assert window.theme_fade is not None
            window.theme_fade.setCurrentTime(window.theme_fade.duration())
            assert app.property('themeBackground') == window.now_playing_theme_colors()['themeBackground']
        assert toolbar.call.called

        dialog = ThemeSettingsDialog(settings, window)
        fade = dialog.numbers['theme_fade_seconds']
        assert fade.value() == THEME_FADE_MS / 1000 and fade.maximum() == THEME_FADE_MAX_SECONDS
        fade.setValue(0)
        dialog.apply()
        assert settings.value('theme_fade_seconds', type=float) == 0
        window.queue = [(track, gold) for track in gold.tracks]
        window.play_index(0, autoplay=False)
        assert window.theme_fade is None
        assert app.property('themeBackground') == window.now_playing_theme_colors()['themeBackground']
        fade.setValue(5)
        dialog.apply()
        window.queue = [(track, blue) for track in blue.tracks]
        window.play_index(0, autoplay=False)
        assert window.theme_fade.duration() == 5000
        before = app.property('themeBackground')
        window.theme_fade.setCurrentTime(2500)
        assert app.property('themeBackground') != before
        window.theme_fade.setCurrentTime(5000)
        reopened = ThemeSettingsDialog(settings, window)
        assert reopened.numbers['theme_fade_seconds'].value() == 5
        reopened.close()
        dialog.close()

        disc = Disc(str(data_disc), 'Music compilation', 'data-disc')
        window.update_optical_discs([disc])
        assert window.disc_list.isVisible() and window.disc_list.count() == 1
        window.disc_list.setCurrentRow(0)
        wait_until(lambda: not window.scanners and len(window.albums) == 1)
        assert window.albums[0].folder == data_disc / 'Disc album'
        assert window.albums[0].artwork
        assert settings.value('browser_root') == str(music)
        assert settings.value('folder') == str(music)
        window.queue = [(track, window.albums[0]) for track in window.albums[0].tracks]
        window.play_index(0, autoplay=False)
        window.update_optical_discs([])
        wait_until(lambda: not window.scanners and len(window.albums) == 2)
        wait_until(lambda: not window.disc_list.isVisible())
        assert not window.queue
        assert window.player.source().isEmpty()

        # Audio CD discovery produces a normal album; preparation is asynchronous.
        audio_root = root / 'Audio CD'
        audio_root.mkdir()
        Image.new('RGB', (32, 32), '#e0b558').save(audio_root / 'cover.png')
        identity, audio_tracks = parse_toc(toc(((1, 0, 0), (0xaa, 32, 0))))
        audio_disc = Disc(str(audio_root), 'Audio CD', identity, audio_tracks)
        window.update_optical_discs([audio_disc])
        window.disc_list.setCurrentRow(0)
        wait_until(lambda: not window.scanners and len(window.albums) == 1)
        album = window.albums[0]
        assert album.artwork and album.tracks[0].cd_source == str(audio_root)
        class Device:
            def __init__(self, source):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def toc(self):
                return identity, audio_tracks
            def read_audio(self, start, count):
                return b'\0' * (count * 2352)
        def prepare(track, cancelled, progress):
            return prepare_audio(track, cancelled, progress, device_factory=Device)
        with patch('optical_discs.prepare_audio', side_effect=prepare):
            window.play_album(album, 0)
            wait_until(lambda: not window.scanners and not window.cd_loading)
        assert Path(window.player.source().toLocalFile()).resolve() == album.tracks[0].path.resolve()
        window.update_optical_discs([])
        wait_until(lambda: not window.scanners)
        assert not window.queue
    finally:
        window.taskbar.enabled = False
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        QTest.qWait(200)
print('PASS: real-player native taskbar theme updates, 0–5s fades, data/audio CD isolation, cached preparation, art and removal')
