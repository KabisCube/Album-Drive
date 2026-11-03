"""Persistent scan reuse and invalidation without writing to the music library."""

from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from mutagen.id3 import TIT2
from mutagen.wave import WAVE

import library
from test_library import make_wave


class LibraryCacheTests(unittest.TestCase):
    def test_reuses_metadata_covers_and_thumbnails_after_memory_cache_is_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            music = root / 'Music'
            make_wave(music / 'Album/1.wav', 'First', art=True)
            cache = root / 'cache/library.sqlite3'
            first, _ = library.scan_library(music, cache_path=cache)
            self.assertTrue(first[0].thumbnail)
            library._track_cache.clear()
            with patch('library._read_track', side_effect=AssertionError('Unchanged tags reopened')), \
                    patch('library.folder_art', side_effect=AssertionError('Unchanged cover reopened')), \
                    patch('library.cover_thumbnail', side_effect=AssertionError('Thumbnail regenerated')):
                second, _ = library.scan_library(music, cache_path=cache)
            self.assertEqual(first, second)

    def test_refreshes_only_changed_albums_and_finds_added_removed_tracks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            music = root / 'Music'
            for name in ('A', 'B'):
                make_wave(music / name / '1.wav', name)
            cache = root / 'cache.sqlite3'
            library.scan_library(music, cache_path=cache)
            track = WAVE(music / 'A/1.wav')
            track.tags.add(TIT2(encoding=3, text=['Edited title']))
            track.save()
            library._track_cache.clear()
            with patch('library._read_track', wraps=library._read_track) as reader:
                albums, _ = library.scan_library(music, cache_path=cache)
            self.assertEqual([call.args[0].parent.name for call in reader.call_args_list], ['A'])
            self.assertEqual(next(album for album in albums if album.folder.name == 'A').tracks[0].title, 'Edited title')
            make_wave(music / 'B/2.wav')
            make_wave(music / 'C/1.wav')
            (music / 'A/1.wav').unlink()
            albums, _ = library.scan_library(music, cache_path=cache)
            self.assertEqual({album.folder.name for album in albums}, {'B', 'C'})
            self.assertEqual(len(next(album for album in albums if album.folder.name == 'B').tracks), 2)
            (music / 'B/2.wav').unlink()
            albums, _ = library.scan_library(music, cache_path=cache)
            self.assertEqual(len(next(album for album in albums if album.folder.name == 'B').tracks), 1)

    def test_changed_cover_invalidates_cached_art_and_thumbnail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_wave(root / 'Music/Album/1.wav')
            cover = root / 'Music/Album/cover.png'
            Image.new('RGB', (2048, 2048), 'red').save(cover)
            cache = root / 'cache.sqlite3'
            first, _ = library.scan_library(root / 'Music', cache_path=cache)
            with Image.open(BytesIO(first[0].thumbnail)) as image:
                self.assertLessEqual(max(image.size), 512)
            stamp = cover.stat().st_mtime_ns
            Image.new('RGB', (2048, 2048), 'blue').save(cover)
            os.utime(cover, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
            second, _ = library.scan_library(root / 'Music', cache_path=cache)
            self.assertNotEqual(first[0].artwork, second[0].artwork)
            self.assertNotEqual(first[0].thumbnail, second[0].thumbnail)

    def test_corrupt_cache_falls_back_to_scanning_and_cancel_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_wave(root / 'Music/Album/1.wav')
            cache = root / 'bad.sqlite3'
            cache.write_bytes(b'not a database')
            albums, _ = library.scan_library(root / 'Music', cache_path=cache)
            self.assertEqual(len(albums), 1)
            good = root / 'cache.sqlite3'
            albums, _ = library.scan_library(root / 'Music', cancelled=lambda: True, cache_path=good)
            self.assertEqual(albums, [])
            albums, _ = library.scan_library(root / 'Music', cache_path=good)
            self.assertEqual(len(albums), 1)


if __name__ == '__main__':
    unittest.main()
