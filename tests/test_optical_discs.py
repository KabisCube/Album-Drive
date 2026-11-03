"""CD table decoding, track preparation, cache reuse and read cancellation."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock
import wave

from optical_discs import Disc, WindowsDiscDevice, audio_album, cached_audio_valid, parse_toc, prepare_audio


def toc(entries):
    output = bytearray((0, 0, 1, len(entries) - 1))
    for number, start, control in entries:
        msf = start + 150
        minutes, remainder = divmod(msf, 60 * 75)
        seconds, frames = divmod(remainder, 75)
        output.extend((0, 0x10 | control, number, 0, 0, minutes, seconds, frames))
    output[:2] = (len(output) - 2).to_bytes(2, 'big')
    return bytes(output)


class DiscTests(unittest.TestCase):
    def test_eject_unlocks_before_requesting_media_ejection(self):
        device = WindowsDiscDevice.__new__(WindowsDiscDevice)
        calls = []
        device.ioctl = lambda code, size, request=None: calls.append((code, size, request))
        device.eject()
        self.assertEqual([(code, size) for code, size, _ in calls], [(0x2d4804, 0), (0x2d4808, 0)])
        self.assertEqual(calls[0][2].value, 0)

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.identity, self.tracks = parse_toc(toc(((1, 0, 0), (2, 32, 0), (0xaa, 64, 0))))
        disc = Disc(str(self.root / 'disc'), 'Example album', self.identity, self.tracks)
        self.album = audio_album(disc, self.root / 'cache')
        self.track = self.album.tracks[0]
        self.blocks = []
        test = self
        class Device:
            def __init__(self, root):
                test.assertEqual(root, test.track.cd_source)
            def toc(self):
                return test.identity, test.tracks
            def read_audio(self, start, count):
                test.blocks.append((start, count))
                return b'\x01\x00\xff\xff' * (count * 588)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        self.device = Device

    def test_toc_track_boundaries_and_data_track_exclusion(self):
        self.assertEqual(self.tracks, ((1, 0, 32), (2, 32, 32)))
        _, mixed = parse_toc(toc(((1, 0, 4), (2, 100, 0), (0xaa, 200, 0))))
        self.assertEqual(mixed, ((2, 100, 100),))
        for data in (b'', b'\0\0\1\1', b'\0\0\0\xff'):
            with self.assertRaises(ValueError):
                parse_toc(data)

    def test_native_raw_read_uses_logical_offset_and_full_audio_sectors(self):
        device = object.__new__(WindowsDiscDevice)
        device.ioctl = Mock(return_value=b'\0' * (16 * 2352))
        self.assertEqual(len(device.read_audio(123, 16)), 16 * 2352)
        code, size, request = device.ioctl.call_args.args
        self.assertEqual((code, size, request.offset, request.sectors, request.mode),
                         (0x2403e, 16 * 2352, 123 * 2048, 16, 2))
        device.ioctl.return_value = b'\0'
        with self.assertRaisesRegex(OSError, 'incomplete audio'):
            device.read_audio(123, 16)

    def test_audio_is_valid_stereo_pcm_and_reused_from_cache(self):
        progress = []
        path = prepare_audio(self.track, progress=progress.append, device_factory=self.device)
        self.assertTrue(cached_audio_valid(self.track))
        self.assertEqual(self.blocks, [(0, 16), (16, 16)])
        with wave.open(str(path)) as audio:
            self.assertEqual(audio.getparams()[:4], (2, 2, 44100, 32 * 588))
            self.assertEqual(audio.readframes(1), b'\x01\x00\xff\xff')
        self.assertEqual(progress[-1], 100)
        no_device = Mock(side_effect=AssertionError('Cached tracks must not read the CD again'))
        self.assertEqual(prepare_audio(self.track, device_factory=no_device), path)

    def test_cancel_cleans_partial_track(self):
        result = prepare_audio(self.track, cancelled=lambda: bool(self.blocks), device_factory=self.device)
        self.assertIsNone(result)
        self.assertFalse(self.track.path.exists())
        self.assertEqual(list(self.track.path.parent.glob('*.part')), [])

    def test_changed_disc_is_rejected(self):
        device = self.device
        class Changed(device):
            def toc(self):
                return 'another-disc', ()
        with self.assertRaisesRegex(OSError, 'disc has changed'):
            prepare_audio(self.track, device_factory=Changed)
        self.assertFalse(self.track.path.exists())
        self.assertEqual(list(self.track.path.parent.glob('*.part')), [])

    def test_missing_disc_art_uses_normal_missing_art_album(self):
        self.assertFalse(self.album.artwork)
        self.assertEqual(self.album.title, 'Example album')
        self.assertEqual(len(self.album.tracks), 2)
        self.assertEqual(self.track.seconds, 32 / 75)


if __name__ == '__main__':
    unittest.main()
