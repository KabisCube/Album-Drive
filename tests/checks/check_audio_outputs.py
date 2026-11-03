"""Offscreen audio device-change checks without changing the OS default."""

import os
import tempfile
import time
import wave
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices, QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PlayerWindow


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition(), 'Audio output check timed out'


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    track = root / 'Music' / 'Album' / '1.wav'
    track.parent.mkdir(parents=True)
    with wave.open(str(track), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(bytes(8000 * 2 * 6))
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('volume', 50)
    window = PlayerWindow(settings)
    assert abs(window.audio.volume() - .25) < .001
    window.show()
    wait_until(lambda: len(window.albums) == 1 and not window.scanners)
    window.play_album(window.albums[0], 0)
    wait_until(lambda: window.player.duration() == 6000 and window.player.isSeekable())
    window.player.pause()
    window.player.setPosition(1500)
    window.volume.setValue(37)
    assert abs(window.audio.volume() - .1369) < .001
    window.audio.setMuted(True)
    source = window.player.source()

    # Exercise the real signal connection and routing to available devices.
    for device in QMediaDevices.audioOutputs():
        with patch('main.QMediaDevices.defaultAudioOutput', return_value=device):
            window.media_devices.audioOutputsChanged.emit()
            wait_until(lambda: window.audio.device() == device)
            assert window.player.source() == source and window.queue_index == 0
            assert window.player.playbackState() == QMediaPlayer.PausedState
            assert window.player.position() == 1500
            assert abs(window.audio.volume() - .1369) < .001 and window.audio.isMuted()
            with patch.object(window.audio, 'setDevice') as set_device:
                window.media_devices.audioOutputsChanged.emit()
                QTest.qWait(40)
                set_device.assert_not_called()

    window.player.play()
    wait_until(lambda: window.player.playbackState() == QMediaPlayer.PlayingState)
    device = QMediaDevices.defaultAudioOutput()
    with patch('main.QMediaDevices.defaultAudioOutput', return_value=device):
        window.media_devices.audioOutputsChanged.emit()
        wait_until(lambda: window.audio.device() == device)
        QTest.qWait(60)
        assert window.player.playbackState() == QMediaPlayer.PlayingState
        assert window.player.position() >= 1500 and window.player.source() == source
        assert abs(window.audio.volume() - .1369) < .001 and window.audio.isMuted()

    # A temporary absence of devices requests the default/empty output too.
    with patch('main.QMediaDevices.defaultAudioOutput', return_value=QAudioDevice()), \
            patch.object(window.audio, 'device', return_value=object()), \
            patch.object(window.audio, 'setDevice') as set_device:
        window.media_devices.audioOutputsChanged.emit()
        wait_until(lambda: set_device.call_count == 1)
        assert set_device.call_args.args[0].isNull()

    window.close()
    assert window.playback_shutdown
    assert window.player.source().isEmpty()
    assert window.player.audioOutput() is None
    with patch.object(window.audio, 'setDevice') as set_device:
        window.refresh_audio_output()
        set_device.assert_not_called()
    window.shutdown_playback()

print('PASS: output notifications, device routing, duplicate events, no-device fallback and paused/playing state preservation')
