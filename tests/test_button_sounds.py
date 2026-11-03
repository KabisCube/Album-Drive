"""Verify button activation, silence, sound selection and bundled PCM assets."""

import os
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import wave

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import button_sounds
from themes import ChunkyCheckBox, ChunkyTabBar, ThemedButton
from scripts.make_button_sounds import pitched_samples


app = QApplication.instance() or QApplication([])


class ButtonSoundTests(unittest.TestCase):
    def setUp(self):
        app.setProperty('uiThickness', 100)
        app.setProperty('buttonSoundVolume', 100)

    def test_pitch_shift_lowers_frequency_as_thickness_increases(self):
        tone = [math.sin(2 * math.pi * 1000 * i / 44100) for i in range(4410)]
        crossings = []
        for depth in range(1, 13):
            samples = list(pitched_samples(tone, depth))[:2205]
            crossings.append(sum(a <= 0 < b for a, b in zip(samples, samples[1:])))
        self.assertTrue(all(a >= b for a, b in zip(crossings, crossings[1:])), crossings)
        self.assertGreater(crossings[0], crossings[-1] * 1.4)

    def test_each_depth_has_a_distinct_short_unclipped_sample(self):
        data = []
        for depth in range(1, 13):
            path = Path(__file__).resolve().parents[1] / 'assets' / 'sounds' / f'button-{depth:02}.wav'
            with wave.open(str(path), 'rb') as clip:
                self.assertEqual((clip.getnchannels(), clip.getsampwidth(), clip.getframerate()), (1, 2, 44100))
                self.assertAlmostEqual(clip.getnframes() / clip.getframerate(), .11, places=3)
                payload = clip.readframes(clip.getnframes())
            samples = struct.unpack('<' + 'h' * (len(payload) // 2), payload)
            self.assertTrue(0 < max(abs(sample) for sample in samples) < 32767)
            data.append(payload)
        self.assertEqual(len(set(data)), 12)
        thin = struct.unpack('<' + 'h' * (len(data[0]) // 2), data[0])
        thick = struct.unpack('<' + 'h' * (len(data[-1]) // 2), data[-1])
        # The switch reset adds a short follow-up after the mouse transient.
        self.assertGreater(sum(sample ** 2 for sample in thick[1323:]),
                           sum(sample ** 2 for sample in thin[1323:]) * 100)

    def test_zero_never_initializes_or_plays_audio(self):
        app.setProperty('uiThickness', 0)
        with patch('button_sounds.sound_bank') as bank:
            button_sounds.play_button_sound()
            button_sounds.prepare_button_sounds()
            bank.assert_not_called()

    def test_muted_sound_volume_never_initializes_audio(self):
        app.setProperty('buttonSoundVolume', 0)
        with patch('button_sounds.sound_bank') as bank:
            button_sounds.play_button_sound()
            button_sounds.prepare_button_sounds()
            bank.assert_not_called()

    def test_bank_preloads_reuses_voices_and_follows_depth_and_output(self):
        with patch('button_sounds.QSoundEffect') as effect, patch('button_sounds.QMediaDevices') as devices, patch('button_sounds.selected_output') as output:
            # Independent voices permit rapid presses without cutting off tails.
            from unittest.mock import MagicMock
            voices = [MagicMock() for _ in range(4)]
            effect.side_effect = voices
            for voice in voices:
                voice.status.return_value = effect.Ready
            bank = button_sounds.ButtonSounds(app)
            bank.prepare(4)
            for voice in voices:
                self.assertTrue(voice.setSource.call_args.args[0].toLocalFile().endswith('button-04.wav'))
            bank.play()
            bank.play()
            voices[0].play.assert_called_once()
            voices[1].play.assert_called_once()
            app.setProperty('buttonSoundVolume', 50)
            for voice in voices:
                voice.setSource.reset_mock()
            bank.prepare(4)
            for voice in voices:
                voice.setVolume.assert_called_with(.055)
                voice.setSource.assert_not_called()
            app.setProperty('uiThickness', 300)
            bank.play()
            self.assertEqual(bank.depth, 12)
            self.assertTrue(voices[2].setSource.call_args.args[0].toLocalFile().endswith('button-12.wav'))
            new_device = object()
            output.return_value = new_device
            bank.update_output()
            for voice in voices:
                voice.setAudioDevice.assert_called_with(new_device)
                voice.play.reset_mock()
            app.setProperty('uiThickness', 0)
            bank.prepare(0)
            bank.play()
            for voice in voices:
                voice.play.assert_not_called()
                self.assertGreaterEqual(voice.stop.call_count, 3)
            bank.shutdown()
            for voice in voices:
                self.assertTrue(voice.setSource.call_args.args[0].isEmpty())
                voice.reset_mock()
            bank.shutdown()
            bank.prepare(4)
            bank.play()
            bank.update_output()
            for voice in voices:
                self.assertEqual(voice.mock_calls, [])

    def test_mouse_keyboard_and_disabled_buttons(self):
        with patch('themes.play_button_sound') as sound:
            button = ThemedButton('Test')
            button.resize(120, 48)
            button.show()
            QTest.mousePress(button, Qt.LeftButton)
            self.assertEqual(sound.call_count, 1)
            QTest.mouseRelease(button, Qt.LeftButton)
            self.assertEqual(sound.call_count, 1)
            QTest.keyClick(button, Qt.Key_Space)
            self.assertEqual(sound.call_count, 2)
            button.setEnabled(False)
            QTest.mouseClick(button, Qt.LeftButton)
            self.assertEqual(sound.call_count, 2)
            button.close()
            checkbox = ChunkyCheckBox('Test')
            checkbox.resize(120, 48)
            checkbox.show()
            QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(10, 20))
            self.assertEqual(sound.call_count, 3)
            checkbox.close()

    def test_settings_tabs_sound_on_activation_not_programmatic_changes(self):
        with patch('themes.play_button_sound') as sound:
            tabs = ChunkyTabBar()
            tabs.addTab('One')
            tabs.addTab('Two')
            tabs.resize(240, 50)
            tabs.show()
            tabs.setCurrentIndex(1)
            sound.assert_not_called()
            QTest.mouseClick(tabs, Qt.LeftButton, pos=tabs.tabRect(0).center())
            sound.assert_called_once()
            QTest.keyClick(tabs, Qt.Key_Right)
            self.assertEqual(sound.call_count, 2)
            tabs.close()


if __name__ == '__main__':
    unittest.main()
