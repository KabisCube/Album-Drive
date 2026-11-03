import os
from pathlib import Path
import tempfile
import unittest
import wave

from file_paths import filesystem_path, library_path
from library import scan_library


class FilePathTests(unittest.TestCase):
    def test_library_paths_remove_windows_prefixes(self):
        self.assertEqual(library_path('\\\\?\\C:\\Music\\Example Artist.'), Path('C:\\Music\\Example Artist.'))
        self.assertEqual(library_path('\\\\?\\UNC\\server\\Music'), Path('\\\\server\\Music'))

    @unittest.skipUnless(os.name == 'nt', 'Windows filesystem paths')
    def test_scan_trailing_period_folder_and_reuse_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'Example Artist.'
            native = filesystem_path(folder)
            native.mkdir()
            try:
                with wave.open(str(native / '1.wav'), 'wb') as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(8000)
                    audio.writeframes(bytes(16000))
                for _ in range(2):
                    albums, skipped = scan_library(root, cache_path=root / 'albums.sqlite3')
                    self.assertEqual(skipped, [])
                    self.assertEqual(len(albums), 1)
                    self.assertEqual(albums[0].folder, folder)
                    self.assertEqual(albums[0].tracks[0].seconds, 1)
            finally:
                for path in native.iterdir():
                    path.unlink()
                native.rmdir()
