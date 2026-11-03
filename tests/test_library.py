import base64
import os
import struct
import tempfile
import unittest
import wave
import zlib
from pathlib import Path
from unittest.mock import patch

from mutagen.id3 import APIC, TALB, TDRC, TIT2, TPE1, TRCK
from mutagen.wave import WAVE
from mutagen.flac import FLAC, Picture

import mutagen
from library import scan_library


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')


def bad_filter_png():
    # Valid PNG chunks/checksums, but filter 5 is invalid (only 0-4 exist).
    data = b'IDAT' + zlib.compress(b'\x05\xff\xff\xff')
    return PNG[:33] + struct.pack('>I', len(data) - 4) + data + struct.pack('>I', zlib.crc32(data)) + PNG[-12:]


def make_wave(path, title='', number=0, art=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x00\x00' * 8000)
    if title:
        audio = WAVE(path)
        audio.add_tags()
        audio.tags.add(TIT2(encoding=3, text=[title]))
        audio.tags.add(TALB(encoding=3, text=['Test Album']))
        audio.tags.add(TPE1(encoding=3, text=['Test Artist']))
        audio.tags.add(TRCK(encoding=3, text=[str(number)]))
        if art:
            audio.tags.add(APIC(encoding=3, mime='image/png', type=3, data=PNG if art is True else art))
        audio.save()


class LibraryTests(unittest.TestCase):
    def test_release_dates_use_tags_then_folder_year(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '1994 - Folder year' / '1.wav'
            make_wave(path)
            audio = WAVE(path)
            audio.add_tags()
            audio.tags.add(TDRC(encoding=3, text=['1997-09-22']))
            audio.save()
            make_wave(root / '2001 - Fallback' / '1.wav')
            make_wave(root / 'Unknown' / '1.wav')
            albums, _ = scan_library(root)
            dates = {album.folder.name: album.release_date for album in albums}
            self.assertEqual(dates, {'1994 - Folder year': '1997-09-22',
                                     '2001 - Fallback': '2001-01-01', 'Unknown': ''})

    def test_folder_tree_is_walked_once_for_nested_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(8):
                album = root / 'Artist' / str(number)
                make_wave(album / '01.wav')
                (album / 'Artwork' / 'Scans').mkdir(parents=True)
                (album / 'Artwork' / 'Scans' / 'front.png').write_bytes(PNG)
            with patch('library.os.walk', wraps=os.walk) as walk:
                albums, _ = scan_library(root)
            self.assertEqual(walk.call_count, 1)
            self.assertEqual(len(albums), 8)
            self.assertTrue(all(album.artwork == PNG for album in albums))

    def test_cached_metadata_is_reused_and_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'track.wav'
            make_wave(path, 'Original title', 1)
            with patch('library.mutagen.File', wraps=mutagen.File) as read:
                first, _ = scan_library(root)
                self.assertEqual(read.call_count, 1)
                first[0].tracks[0].title = 'Changed only in memory'
                second, _ = scan_library(root)
                self.assertEqual(read.call_count, 1)
                self.assertEqual(second[0].tracks[0].title, 'Original title')
                previous_stamp = path.stat()
                audio = WAVE(path)
                audio.tags.add(TIT2(encoding=3, text=['Updated on disk']))
                audio.save()
                os.utime(path, ns=(previous_stamp.st_atime_ns, previous_stamp.st_mtime_ns + 1_000_000_000))
                third, _ = scan_library(root)
                self.assertEqual(read.call_count, 2)
                self.assertEqual(third[0].tracks[0].title, 'Updated on disk')

    def test_bad_png_filter_falls_back_to_another_folder_image(self):
        with tempfile.TemporaryDirectory() as directory:
            album = Path(directory)
            make_wave(album / 'track.wav')
            (album / 'front.png').write_bytes(bad_filter_png())
            (album / 'cover.png').write_bytes(PNG)
            with self.assertLogs('library', level='WARNING') as messages:
                albums, _ = scan_library(album)
            self.assertEqual(albums[0].artwork, PNG)
            self.assertIn('front.png', '\n'.join(messages.output))

    def test_bad_embedded_png_uses_next_tracks_cover(self):
        with tempfile.TemporaryDirectory() as directory:
            album = Path(directory)
            make_wave(album / '01.wav', 'First track', 1, art=bad_filter_png())
            make_wave(album / '02.wav', 'Second track', 2, art=True)
            with self.assertLogs('library', level='WARNING') as messages:
                albums, _ = scan_library(album)
            self.assertEqual(albums[0].artwork, PNG)
            self.assertEqual(len(albums[0].tracks), 2)
            self.assertIn('01.wav', '\n'.join(messages.output))

    def test_unreadable_art_does_not_hide_tracks(self):
        with tempfile.TemporaryDirectory() as directory:
            album = Path(directory)
            make_wave(album / '01.wav', 'First track', 1, art=bad_filter_png())
            (album / 'front.png').write_bytes(bad_filter_png())
            with self.assertLogs('library', level='WARNING'):
                albums, _ = scan_library(album)
            self.assertEqual(albums[0].artwork, b'')
            self.assertEqual(len(albums[0].tracks), 1)

    def test_flac_metadata_and_embedded_cover(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '01 - fallback.flac'
            # A minimal FLAC STREAMINFO block is enough for metadata discovery.
            stream_info = (b'\x10\x00\x10\x00' + bytes(6)
                           + ((8000 << 44) | (15 << 36) | 8000).to_bytes(8, 'big')
                           + bytes(16))
            path.write_bytes(b'fLaC\x80\x00\x00\x22' + stream_info)
            audio = FLAC(path)
            audio.add_tags()
            audio['title'] = '19-2000 (Example remix)'
            audio['artist'] = 'Example Artist'
            audio['albumartist'] = 'Example Artist'
            audio['album'] = 'Example Album (Limited Edition)'
            audio['tracknumber'] = '01'
            picture = Picture()
            picture.type = 3
            picture.mime = 'image/png'
            picture.data = PNG
            audio.add_picture(picture)
            audio.save()
            albums, errors = scan_library(root)
            self.assertEqual(errors, [])
            self.assertEqual(albums[0].title, 'Example Album (Limited Edition)')
            self.assertTrue(albums[0].has_album_title)
            self.assertEqual(albums[0].artist, 'Example Artist')
            self.assertEqual(albums[0].artwork, PNG)
            self.assertEqual(albums[0].tracks[0].title, '19-2000 (Example remix)')
            self.assertEqual(albums[0].tracks[0].number, 1)
            self.assertAlmostEqual(albums[0].tracks[0].seconds, 1)

    def test_recursive_metadata_order_and_embedded_art(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in (10, 2, 1):
                make_wave(root / 'Artist' / 'Album' / f'{number}.wav', f'Track {number}', number, art=number == 2)
            make_wave(root / 'loose.wav')
            (root / 'Empty').mkdir()
            albums, errors = scan_library(root)
            self.assertEqual(errors, [])
            self.assertEqual(len(albums), 2)
            album = next(a for a in albums if a.title == 'Test Album')
            self.assertEqual([t.number for t in album.tracks], [1, 2, 10])
            self.assertEqual(album.artist, 'Test Artist')
            self.assertEqual(album.artwork, PNG)
            self.assertAlmostEqual(album.tracks[0].seconds, 1)

    def test_bad_tags_fall_back_and_case_insensitive_folder_art(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'broken.MP3').write_bytes(b'not an mp3')
            (root / 'COVER.PNG').write_bytes(PNG)
            albums, errors = scan_library(root)
            self.assertEqual(errors, [])
            self.assertEqual(albums[0].tracks[0].title, 'broken')
            self.assertEqual(albums[0].artwork, PNG)
            self.assertEqual(albums[0].title, root.name)

    def test_album_art_filename(self):
        for name in ('album art.png', 'Album Art.JPG', 'album art.jpeg'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_wave(root / 'track.wav')
                (root / name).write_bytes(PNG)
                albums, errors = scan_library(root)
                self.assertEqual(errors, [])
                self.assertEqual(albums[0].artwork, PNG)

    def test_cancellation_and_inaccessible_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_wave(root / 'test.wav')
            self.assertEqual(scan_library(root, cancelled=lambda: True), ([], []))
            albums, errors = scan_library(root / 'missing')
            self.assertEqual(albums, [])
            self.assertEqual(len(errors), 1)

    def test_disc_folders_share_parent_art_and_folder_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            album = root / 'Example Artist' / '1994 - Example Album Volume II'
            for disc in (2, 1):
                for track in (10, 2, 1):
                    make_wave(album / f'Disc {disc}' / f'{track}.wav')
            (album / 'cover.jpg').write_bytes(PNG)
            albums, errors = scan_library(root)
            self.assertEqual(errors, [])
            self.assertEqual(len(albums), 1)
            result = albums[0]
            self.assertEqual(result.folder, album)
            self.assertEqual(result.title, album.name)
            self.assertFalse(result.has_album_title)
            self.assertEqual(result.artist, 'Example Artist')
            self.assertEqual(result.artwork, PNG)
            self.assertEqual([(t.disc, t.path.stem) for t in result.tracks],
                             [(disc, str(track)) for disc in (1, 2) for track in (1, 2, 10)])
            self.assertTrue(all(t.artist == 'Example Artist' for t in result.tracks))
            # Selecting just a disc still finds the shared album cover.
            selected, _ = scan_library(album / 'Disc 2')
            self.assertEqual(selected[0].artwork, PNG)
            self.assertEqual(len(selected[0].tracks), 3)

    def test_regular_sibling_albums_stay_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('Album 1', 'Album 2'):
                make_wave(root / 'Artist' / name / 'track.wav')
            (root / 'Artist' / 'cover.jpg').write_bytes(PNG)
            albums, _ = scan_library(root)
            self.assertEqual(len(albums), 2)
            self.assertTrue(all(a.artist == 'Artist' for a in albums))
            self.assertTrue(all(not a.artwork for a in albums))

    def test_disc_metadata_and_embedded_art_take_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            album = Path(directory) / 'Folder Artist' / 'Folder Album'
            make_wave(album / 'CD1' / 'track.wav', 'Tagged Track', 1, art=True)
            (album / 'cover.png').write_bytes(b'other cover')
            albums, _ = scan_library(album)
            self.assertEqual(albums[0].title, 'Test Album')
            self.assertEqual(albums[0].artist, 'Test Artist')
            self.assertEqual(albums[0].artwork, PNG)

    def test_nested_front_art_wins_over_sleeves_discs_and_generic_cover(self):
        for name in ('1 Front.jpg', 'Front.jpeg', 'Exämple Artist - Example Album (front).jpg'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                album = Path(directory)
                make_wave(album / 'track.wav')
                art = album / 'Artwork' / 'Scans'
                art.mkdir(parents=True)
                for other in ('Disc A.jpg', '2 Sleeve.jpg', '3 Back.jpg', '._front.jpg'):
                    (art / other).write_bytes(b'not the front')
                (album / 'cover.jpg').write_bytes(b'generic cover')
                (art / name).write_bytes(PNG)
                albums, _ = scan_library(album)
                self.assertEqual(albums[0].artwork, PNG)

    def test_nested_front_art_for_multidisc_album(self):
        with tempfile.TemporaryDirectory() as directory:
            album = Path(directory)
            make_wave(album / 'CD1' / 'track.wav')
            make_wave(album / 'CD2' / 'track.wav')
            (album / 'CD1' / 'cover.jpg').write_bytes(b'disc scan')
            (album / 'Artwork').mkdir()
            (album / 'Artwork' / '1 Front.jpg').write_bytes(PNG)
            albums, _ = scan_library(album)
            self.assertEqual(len(albums), 1)
            self.assertEqual(albums[0].artwork, PNG)

    def test_parent_album_does_not_borrow_child_album_front(self):
        with tempfile.TemporaryDirectory() as directory:
            album = Path(directory)
            make_wave(album / 'track.wav')
            make_wave(album / 'Other Album' / 'track.wav')
            art = album / 'Other Album' / 'Artwork'
            art.mkdir()
            (art / 'front.jpg').write_bytes(PNG)
            albums, _ = scan_library(album)
            by_folder = {a.folder: a for a in albums}
            self.assertFalse(by_folder[album].artwork)
            self.assertEqual(by_folder[album / 'Other Album'].artwork, PNG)


if __name__ == '__main__':
    unittest.main()
