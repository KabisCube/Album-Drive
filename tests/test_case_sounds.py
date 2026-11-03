"""Independent case effect volumes, mute, output changes and bundled PCM assets."""

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import unittest
import struct
from unittest.mock import MagicMock, patch
import wave
from PySide6.QtWidgets import QApplication
from case_sounds import CaseSounds, prepare_case_sounds

app = QApplication.instance() or QApplication([])


class CaseSoundTests(unittest.TestCase):
    def test_bundled_pcm_has_distinct_opening_and_closing_samples(self):
        contents = []
        for action in ('open', 'close'):
            path = Path(__file__).resolve().parents[1] / 'assets' / 'sounds' / f'case-{action}.wav'
            with wave.open(str(path)) as audio:
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 44100))
                self.assertGreater(audio.getnframes(), 1000)
                contents.append(audio.readframes(audio.getnframes()))
        self.assertNotEqual(*contents)

    def test_swooshes_are_quiet_with_smooth_fades(self):
        folder = Path(__file__).resolve().parents[1] / 'assets' / 'sounds'
        for action in ('open', 'close'):
            self.assertNotEqual((folder / f'case-{action}.wav').read_bytes(), (folder / 'button-12.wav').read_bytes())
            with wave.open(str(folder / f'case-{action}.wav')) as audio:
                count = audio.getnframes()
                self.assertTrue(.2 <= count / audio.getframerate() <= .4)
                samples = struct.unpack(f'<{count}h', audio.readframes(count))
            rms = (sum(sample * sample for sample in samples) / count) ** .5
            peak = max(abs(sample) for sample in samples)
            self.assertLessEqual(peak / 32767, .27)
            self.assertGreater(rms / 32767, .02)
            self.assertLess(rms / 32767, .1)
            self.assertEqual((samples[0], samples[-1]), (0, 0))
            self.assertLess(max(abs(sample) for sample in samples[:441] + samples[-441:]), peak * .1)

    def test_volumes_mute_and_output_are_independent_of_button_thickness(self):
        app.setProperty('caseOpenVolume', 50)
        app.setProperty('caseCloseVolume', 0)
        app.setProperty('uiThickness', 0)
        with patch('case_sounds.QSoundEffect') as effect, patch('case_sounds.selected_output') as output:
            voices = [MagicMock(), MagicMock()]
            for voice in voices:
                voice.status.return_value = effect.Ready
                voice.setVolume.side_effect = lambda value, voice=voice: setattr(voice.volume, 'return_value', value)
            effect.side_effect = voices
            bank = CaseSounds(app)
            bank.play('open')
            voices[0].play.assert_called_once()
            voices[0].setVolume.assert_called_with(.1)
            bank.play('close')
            voices[1].play.assert_not_called()
            changed = object()
            output.return_value = changed
            bank.prepare()
            for voice in voices:
                voice.setAudioDevice.assert_called_with(changed)
            bank.shutdown()
            for voice in voices:
                self.assertTrue(voice.setSource.call_args.args[0].isEmpty())
                voice.reset_mock()
            bank.shutdown()
            bank.prepare()
            bank.play('open')
            for voice in voices:
                self.assertEqual(voice.mock_calls, [])

    def test_headless_checks_never_initialize_audio(self):
        with patch('case_sounds.CaseSounds') as bank:
            self.assertIsNone(prepare_case_sounds())
            bank.assert_not_called()


if __name__ == '__main__':
    unittest.main()
