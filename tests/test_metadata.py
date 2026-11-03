from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from mutagen import asf, id3
from mutagen.flac import VCFLACDict
from mutagen.mp4 import MP4Cover, MP4FreeForm, MP4Tags
from mutagen.wave import WAVE
from PIL import Image

from library import Track, embedded_art, scan_library
from metadata import decode_value, encode_value, read_documents, read_field, replace_artwork, set_field, write_metadata
from test_library import make_wave


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.folder = self.root / 'Album'
        make_wave(self.folder / '1.wav', 'First song', 1)
        make_wave(self.folder / '2.wav', 'Second song', 2)
        self.album = scan_library(self.folder)[0][0]

    def tearDown(self):
        self.directory.cleanup()

    def pcm(self, path):
        with wave.open(str(path), 'rb') as audio:
            return audio.getparams(), audio.readframes(audio.getnframes())

    def test_album_edits_preserve_distinct_titles_numbers_audio_and_other_tags(self):
        audio = WAVE(self.folder / '1.wav')
        audio.tags.add(id3.TXXX(encoding=3, desc='Keep me', text=['Original']))
        audio.save()
        before = {track.path: self.pcm(track.path) for track in self.album.tracks}
        documents = read_documents(self.album.tracks)
        saved, errors = write_metadata(documents, {'album': 'Renamed album', 'artist': 'New artist'}, {})
        self.assertEqual(len(saved), 2)
        self.assertFalse(errors)
        updated = scan_library(self.folder)[0][0]
        self.assertEqual(updated.title, 'Renamed album')
        self.assertEqual([track.title for track in updated.tracks], ['First song', 'Second song'])
        self.assertEqual([track.number for track in updated.tracks], [1, 2])
        self.assertTrue(all(track.artist == 'New artist' for track in updated.tracks))
        self.assertEqual(WAVE(self.folder / '1.wav').tags['TXXX:Keep me'].text, ['Original'])
        self.assertEqual(before, {track.path: self.pcm(track.path) for track in updated.tracks})

    def test_single_track_native_tags_and_removal(self):
        documents = read_documents(self.album.tracks[:1])
        saved, errors = write_metadata(documents, {'title': 'Edited song'}, {'TXXX:Custom': json.dumps(['One', 'Two'])})
        self.assertFalse(errors)
        self.assertEqual(len(saved), 1)
        audio = WAVE(self.folder / '1.wav')
        self.assertEqual(audio.tags['TXXX:Custom'].text, ['One', 'Two'])
        self.assertEqual(WAVE(self.folder / '2.wav').tags['TIT2'].text, ['Second song'])
        write_metadata(read_documents(self.album.tracks[:1]), {}, {'TXXX:Custom': None})
        self.assertNotIn('TXXX:Custom', WAVE(self.folder / '1.wav').tags)

    def test_artwork_replace_and_remove_preserve_audio(self):
        cover = self.root / 'cover.png'
        Image.new('RGB', (16, 16), '#336699').save(cover)
        before = self.pcm(self.album.tracks[0].path)
        write_metadata(read_documents(self.album.tracks), {}, {}, str(cover))
        documents = read_documents(self.album.tracks)
        self.assertTrue(all(document.artwork == cover.read_bytes() for document in documents))
        self.assertEqual(self.pcm(self.album.tracks[0].path), before)
        write_metadata(documents, {}, {}, '')
        self.assertTrue(all(not document.artwork for document in read_documents(self.album.tracks)))

    def test_external_changes_abort_before_any_writes(self):
        documents = read_documents(self.album.tracks)
        path = self.album.tracks[1].path
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        with self.assertRaisesRegex(ValueError, 'changed outside'):
            write_metadata(documents, {'album': 'Do not write'}, {})
        self.assertTrue(all(WAVE(track.path).tags['TALB'].text == ['Test Album'] for track in self.album.tracks))

    def test_native_values_roundtrip_with_binary_and_chapters(self):
        values = [id3.TDRC(text=['2024-05-03']), id3.APIC(mime='image/png', data=b'bytes'),
                  id3.CHAP(element_id='chapter', start_time=0, end_time=100,
                           sub_frames=[id3.TIT2(text=['Chapter title'])]),
                  MP4Cover(b'cover', imageformat=MP4Cover.FORMAT_PNG), MP4FreeForm(b'custom'),
                  asf.ASFUnicodeAttribute('Text'), asf.ASFByteArrayAttribute(b'binary')]
        for value in values:
            encoded = encode_value(value)
            restored = decode_value(json.loads(json.dumps(encoded)))
            self.assertEqual(encode_value(restored), encoded)

    def test_mp4_and_vorbis_common_fields(self):
        mp4 = SimpleNamespace(tags=MP4Tags())
        set_field(mp4, 'mp4', 'tracknumber', '2/12')
        set_field(mp4, 'mp4', 'publisher', 'Label')
        self.assertEqual(mp4.tags['trkn'], [(2, 12)])
        self.assertEqual(read_field(mp4.tags, 'mp4', 'tracknumber'), '2/12')
        self.assertEqual(read_field(mp4.tags, 'mp4', 'publisher'), 'Label')
        vorbis = SimpleNamespace(tags=VCFLACDict())
        set_field(vorbis, 'vorbis', 'tracknumber', '3/10')
        self.assertEqual(vorbis.tags['tracknumber'], ['3'])
        self.assertEqual(vorbis.tags['tracktotal'], ['10'])
        self.assertEqual(read_field(vorbis.tags, 'vorbis', 'tracknumber'), '3/10')

    def test_asf_fields_and_artwork(self):
        audio = SimpleNamespace(tags=asf.ASFTags())
        set_field(audio, 'asf', 'artist', 'WMA artist')
        self.assertEqual(read_field(audio.tags, 'asf', 'artist'), 'WMA artist')
        data = BytesIO()
        Image.new('RGB', (8, 8), '#336699').save(data, format='PNG')
        replace_artwork(audio, 'asf', data.getvalue(), 'image/png')
        self.assertEqual(embedded_art(audio), data.getvalue())
        replace_artwork(audio, 'asf', b'')
        self.assertFalse(embedded_art(audio))

    def test_partial_write_errors_report_each_file(self):
        documents = read_documents(self.album.tracks)
        original_save = WAVE.save
        def save(audio, *args, **kwargs):
            if Path(audio.filename).name == '2.wav':
                raise PermissionError('Read-only file')
            return original_save(audio, *args, **kwargs)
        with patch.object(WAVE, 'save', save):
            saved, errors = write_metadata(documents, {'artist': 'Updated'}, {})
        self.assertEqual([path.name for path in saved], ['1.wav'])
        self.assertEqual(len(errors), 1)
        self.assertIn('2.wav', errors[0])
        self.assertEqual(WAVE(self.folder / '1.wav').tags['TPE1'].text, ['Updated'])
        self.assertEqual(WAVE(self.folder / '2.wav').tags['TPE1'].text, ['Test Artist'])

    def test_audio_cd_metadata_can_be_viewed_but_not_written(self):
        track = Track(Path('unprepared-cd-track.wav'), 'CD Track', number=2, cd_source='D:/')
        document = read_documents([track])[0]
        self.assertEqual(document.fields['title'], 'CD Track')
        self.assertEqual(document.fields['tracknumber'], '2')
        self.assertFalse(document.writable)
        with self.assertRaisesRegex(ValueError, 'read-only'):
            write_metadata([document], {'title': 'Do not write'}, {})
