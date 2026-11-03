import base64
from dataclasses import dataclass
from io import BytesIO
import json
import os
from pathlib import Path
import struct
import time

import mutagen
from mutagen import asf, id3
from mutagen.apev2 import APEValue, APEv2, _APEValue
from mutagen.flac import Picture
from mutagen.mp4 import MP4Cover, MP4FreeForm, MP4Tags
from PIL import Image

from file_paths import filesystem_path
from library import MAX_ART_BYTES, embedded_art, invalidate_track_metadata


FIELDS = (
    ('title', 'Title', 'TIT2', '\xa9nam', 'title', 'Title'),
    ('artist', 'Artist', 'TPE1', '\xa9ART', 'artist', 'Author'),
    ('albumartist', 'Album artist', 'TPE2', 'aART', 'albumartist', 'WM/AlbumArtist'),
    ('album', 'Album', 'TALB', '\xa9alb', 'album', 'WM/AlbumTitle'),
    ('date', 'Release date', 'TDRC', '\xa9day', 'date', 'WM/Year'),
    ('originaldate', 'Original release date', 'TDOR', '----:com.apple.iTunes:ORIGINALDATE', 'originaldate', 'WM/OriginalReleaseTime'),
    ('tracknumber', 'Track number / total', 'TRCK', 'trkn', 'tracknumber', 'WM/TrackNumber'),
    ('discnumber', 'Disc number / total', 'TPOS', 'disk', 'discnumber', 'WM/PartOfSet'),
    ('genre', 'Genre', 'TCON', '\xa9gen', 'genre', 'WM/Genre'),
    ('composer', 'Composer', 'TCOM', '\xa9wrt', 'composer', 'WM/Composer'),
    ('conductor', 'Conductor', 'TPE3', '----:com.apple.iTunes:CONDUCTOR', 'conductor', 'WM/Conductor'),
    ('lyricist', 'Lyricist', 'TEXT', '----:com.apple.iTunes:LYRICIST', 'lyricist', 'WM/Writer'),
    ('grouping', 'Grouping', 'TIT1', '\xa9grp', 'grouping', 'WM/ContentGroupDescription'),
    ('bpm', 'BPM', 'TBPM', 'tmpo', 'bpm', 'WM/BeatsPerMinute'),
    ('isrc', 'ISRC', 'TSRC', '----:com.apple.iTunes:ISRC', 'isrc', 'WM/ISRC'),
    ('copyright', 'Copyright', 'TCOP', 'cprt', 'copyright', 'Copyright'),
    ('publisher', 'Publisher / label', 'TPUB', '----:com.apple.iTunes:LABEL', 'label', 'WM/Publisher'),
    ('comment', 'Comment', 'COMM', '\xa9cmt', 'comment', 'Description'),
    ('lyrics', 'Lyrics', 'USLT', '\xa9lyr', 'lyrics', 'WM/Lyrics'),
)
FIELD_MAP = {row[0]: row for row in FIELDS}


@dataclass
class MetadataDocument:
    path: Path
    family: str
    fields: dict
    tags: dict
    artwork: bytes
    stamp: tuple
    writable: bool
    reason: str = ''


def file_stamp(path):
    stat = filesystem_path(path).stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def encode_value(value):
    if isinstance(value, id3.Frame):
        return {'frame': value.FrameID, 'fields': {key: encode_value(item) for key, item in value.__dict__.items()}}
    if isinstance(value, MP4FreeForm):
        return {'base64': base64.b64encode(value).decode(), 'mp4_freeform': int(value.dataformat), 'version': value.version}
    if isinstance(value, MP4Cover):
        return {'base64': base64.b64encode(value).decode(), 'mp4_cover': int(value.imageformat)}
    if isinstance(value, bytes):
        return {'base64': base64.b64encode(value).decode()}
    if isinstance(value, asf.ASFBaseAttribute):
        return {'asf_type': type(value).__name__, 'fields': {key: encode_value(item) for key, item in value.__dict__.items()}}
    if isinstance(value, _APEValue):
        return {'ape_kind': value.kind, 'value': encode_value(value.value)}
    if isinstance(value, (dict, id3.ID3Tags)):
        return {str(key): encode_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def decode_value(value):
    if isinstance(value, list):
        return [decode_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    if 'frame' in value:
        frame = id3.Frames.get(value['frame'])
        if frame is None:
            raise ValueError('Unknown ID3 frame: ' + str(value['frame']))
        fields = {key: decode_value(item) for key, item in value['fields'].items()}
        if isinstance(fields.get('sub_frames'), dict):
            fields['sub_frames'] = list(fields['sub_frames'].values())
        return frame(**fields)
    if 'base64' in value:
        data = base64.b64decode(value['base64'], validate=True)
        if 'mp4_cover' in value:
            return MP4Cover(data, imageformat=value['mp4_cover'])
        if 'mp4_freeform' in value:
            return MP4FreeForm(data, dataformat=value['mp4_freeform'], version=value.get('version', 0))
        return data
    if 'asf_type' in value:
        allowed = {name: getattr(asf, name) for name in (
            'ASFUnicodeAttribute', 'ASFByteArrayAttribute', 'ASFBoolAttribute', 'ASFDWordAttribute',
            'ASFWordAttribute', 'ASFQWordAttribute', 'ASFGUIDAttribute')}
        cls = allowed.get(value['asf_type'])
        if cls is None:
            raise ValueError('Unknown ASF attribute type')
        fields = {key: decode_value(item) for key, item in value['fields'].items()}
        return cls(**fields)
    if 'ape_kind' in value:
        return APEValue(decode_value(value['value']), value['ape_kind'])
    return {key: decode_value(item) for key, item in value.items()}


def tag_family(tags):
    if isinstance(tags, id3.ID3Tags):
        return 'id3'
    if isinstance(tags, MP4Tags):
        return 'mp4'
    if isinstance(tags, asf.ASFTags):
        return 'asf'
    if isinstance(tags, APEv2):
        return 'ape'
    return 'vorbis'


def field_key(family, field):
    return FIELD_MAP[field][{'id3': 2, 'mp4': 3, 'vorbis': 4, 'ape': 4, 'asf': 5}[family]]


def delete_tag(tags, key):
    if key in tags:
        del tags[key]


def read_field(tags, family, field):
    key = field_key(family, field)
    if family == 'id3':
        values = tags.getall(key)
        if not values:
            return ''
        frame = next((item for item in values if not getattr(item, 'desc', '')), values[0])
        value = getattr(frame, 'text', '')
    else:
        value = tags.get(key, [])
    if family == 'mp4' and key in ('trkn', 'disk'):
        if not value:
            return ''
        number, total = value[0]
        return f'{number}/{total}' if total else str(number)
    if family == 'vorbis' and field in ('tracknumber', 'discnumber') and value:
        total = tags.get('tracktotal' if field == 'tracknumber' else 'disctotal', [])
        if total and '/' not in str(value[0]):
            return f'{value[0]}/{total[0]}'
    if not isinstance(value, (list, tuple)):
        value = [value]
    return '\n'.join((item.decode('utf-8', errors='replace') if isinstance(item, bytes) else str(item)) for item in value)


def set_field(audio, family, field, text):
    tags = audio.tags
    key = field_key(family, field)
    if family == 'id3':
        existing = tags.getall(key)
        frame = next((item for item in existing if not getattr(item, 'desc', '')), existing[0] if existing else None)
        if frame is not None:
            del tags[frame.HashKey]
        if text:
            options = {'encoding': 3, 'text': text if key == 'USLT' else text.splitlines()}
            if key in ('COMM', 'USLT'):
                options.update(lang=getattr(frame, 'lang', 'eng'), desc=getattr(frame, 'desc', ''))
            tags.add(id3.Frames[key](**options))
        return
    if not text:
        delete_tag(tags, key)
        if family == 'vorbis' and field in ('tracknumber', 'discnumber'):
            delete_tag(tags, 'tracktotal' if field == 'tracknumber' else 'disctotal')
    elif family == 'mp4':
        if key in ('trkn', 'disk'):
            parts = text.split('/')
            if len(parts) > 2:
                raise ValueError('Use number or number/total')
            number, total = int(parts[0]), int(parts[1]) if len(parts) == 2 else 0
            if min(number, total) < 0 or max(number, total) > 65535:
                raise ValueError('Track and disc numbers must be between 0 and 65535')
            tags[key] = [(number, total)]
        elif key == 'tmpo':
            tags[key] = [int(text)]
        elif key.startswith('----:'):
            tags[key] = [MP4FreeForm(item.encode('utf-8')) for item in text.splitlines()]
        else:
            tags[key] = text.splitlines()
    elif family == 'ape':
        tags[key] = text
    elif family == 'vorbis' and field in ('tracknumber', 'discnumber'):
        number, separator, total = text.partition('/')
        tags[key] = [number]
        total_key = 'tracktotal' if field == 'tracknumber' else 'disctotal'
        if separator:
            tags[total_key] = [total]
        else:
            delete_tag(tags, total_key)
    else:
        tags[key] = text.splitlines()


def set_native_tag(audio, family, key, serialized):
    if serialized is None:
        delete_tag(audio.tags, key)
        return
    value = decode_value(json.loads(serialized))
    if family == 'id3':
        if not isinstance(value, id3.Frame):
            frame_id = key.split(':', 1)[0]
            cls = id3.Frames.get(frame_id)
            if cls is None:
                raise ValueError('Unknown ID3 frame: ' + frame_id)
            options = {'encoding': 3, 'text': value if isinstance(value, list) else [str(value)]}
            if frame_id == 'TXXX':
                options['desc'] = key.partition(':')[2]
            value = cls(**options)
        if value.HashKey != key:
            raise ValueError(f'The tag name must be {value.HashKey}')
        audio.tags.add(value)
    else:
        if family == 'mp4' and key in ('trkn', 'disk'):
            value = [tuple(item) for item in value]
        audio.tags[key] = value


def replace_artwork(audio, family, data, mime='image/jpeg'):
    tags = audio.tags
    if not data:
        for key in ('metadata_block_picture', 'coverart', 'coverartmime'):
            delete_tag(tags, key)
    if family == 'id3':
        for frame in list(tags.getall('APIC')):
            if not data or frame.type == 3:
                del tags[frame.HashKey]
        if data:
            description = 'Front cover'
            number = 2
            while 'APIC:' + description in tags:
                description = f'Front cover ({number})'
                number += 1
            tags.add(id3.APIC(encoding=3, mime=mime, type=3, desc=description, data=data))
    elif family == 'mp4':
        if data:
            tags['covr'] = [MP4Cover(data, imageformat=MP4Cover.FORMAT_PNG if mime == 'image/png' else MP4Cover.FORMAT_JPEG)] + list(tags.get('covr', []))[1:]
        else:
            delete_tag(tags, 'covr')
    elif hasattr(audio, 'clear_pictures'):
        remaining = [picture for picture in audio.pictures if data and picture.type != 3]
        audio.clear_pictures()
        for picture in remaining:
            audio.add_picture(picture)
        if data:
            picture = Picture()
            picture.type, picture.mime, picture.desc, picture.data = 3, mime, 'Front cover', data
            with Image.open(BytesIO(data)) as image:
                picture.width, picture.height = image.size
                picture.depth = 32 if image.mode == 'RGBA' else 24
            audio.add_picture(picture)
    elif family == 'asf':
        if data:
            value = struct.pack('<BI', 3, len(data)) + (mime + '\0Front cover\0').encode('utf-16-le') + data
            remaining = [item for item in tags.get('WM/Picture', [])
                         if isinstance(item.value, bytes) and item.value and item.value[0] != 3]
            tags['WM/Picture'] = [asf.ASFByteArrayAttribute(value)] + remaining
        else:
            delete_tag(tags, 'WM/Picture')
    elif family == 'ape':
        if data:
            tags['Cover Art (Front)'] = APEValue(b'cover\0' + data, 1)
        else:
            for key in list(tags):
                if key.lower().startswith('cover art ('):
                    del tags[key]
    else:
        delete_tag(tags, 'coverart')
        delete_tag(tags, 'coverartmime')
        pictures = []
        for encoded in tags.get('metadata_block_picture', []):
            picture = Picture(base64.b64decode(encoded))
            if data and picture.type != 3:
                pictures.append(encoded)
        if data:
            picture = Picture()
            picture.type, picture.mime, picture.desc, picture.data = 3, mime, 'Front cover', data
            with Image.open(BytesIO(data)) as image:
                picture.width, picture.height = image.size
                picture.depth = 32 if image.mode == 'RGBA' else 24
            pictures.append(base64.b64encode(picture.write()).decode())
        if pictures:
            tags['metadata_block_picture'] = pictures
        else:
            delete_tag(tags, 'metadata_block_picture')


def read_document(track):
    path = Path(track.path)
    if track.cd_source:
        fields = {row[0]: str(getattr(track, row[0], '') or '') for row in FIELDS}
        fields['tracknumber'], fields['discnumber'], fields['date'] = str(track.number or ''), str(track.disc or ''), track.release_date
        return MetadataDocument(path, 'cd', fields, {}, b'', (0, 0, 0), False, 'Audio CD metadata is read-only.')
    stamp = file_stamp(path)
    audio = mutagen.File(filesystem_path(path))
    if audio is None:
        raise ValueError(f'Unable to read metadata: {path.name}')
    writable, reason = True, ''
    if audio.tags is None:
        try:
            audio.add_tags()
        except (NotImplementedError, AttributeError, mutagen.MutagenError):
            writable, reason = False, 'This audio format does not support writable tags.'
    if writable and not os.access(filesystem_path(path), os.W_OK):
        writable, reason = False, 'Some selected audio files are read-only.'
    tags = audio.tags if audio.tags is not None else {}
    family = tag_family(tags)
    native = {key: json.dumps(encode_value(value), ensure_ascii=False, sort_keys=True) for key, value in tags.items()}
    if hasattr(audio, 'pictures'):
        native['@pictures'] = json.dumps([base64.b64encode(picture.write()).decode() for picture in audio.pictures])
    if file_stamp(path) != stamp:
        raise ValueError(f'{path.name} changed while its metadata was loading. Reopen the editor.')
    return MetadataDocument(path, family, {row[0]: read_field(tags, family, row[0]) for row in FIELDS},
                            native, embedded_art(audio, path), stamp, writable, reason)


def read_documents(tracks, cancelled=lambda: False):
    result = []
    values, artwork = {}, {}
    for track in tracks:
        if cancelled():
            break
        document = read_document(track)
        document.tags = {key: values.setdefault(value, value) for key, value in document.tags.items()}
        document.artwork = artwork.setdefault(document.artwork, document.artwork)
        result.append(document)
    return result


def write_metadata(documents, fields, native_changes, artwork=None):
    prepared = []
    image_data, mime = None, 'image/jpeg'
    if artwork is not None:
        image_data = b'' if artwork == '' else filesystem_path(artwork).read_bytes()
        if image_data:
            if len(image_data) > MAX_ART_BYTES:
                raise ValueError('Cover images must be 20 MB or smaller.')
            with Image.open(BytesIO(image_data)) as image:
                image.verify()
                if image.format not in ('JPEG', 'PNG'):
                    raise ValueError('Choose a JPEG or PNG cover image.')
                mime = 'image/png' if image.format == 'PNG' else 'image/jpeg'
    for document in documents:
        if not document.writable:
            raise ValueError(document.reason)
        if file_stamp(document.path) != document.stamp:
            raise ValueError(f'{document.path.name} changed outside the editor. Reopen metadata before saving.')
        audio = mutagen.File(filesystem_path(document.path))
        if audio is None:
            raise ValueError(f'Unable to read {document.path.name}')
        if audio.tags is None:
            audio.add_tags()
        for key, value in native_changes.items():
            if key == '@pictures':
                pictures = [] if value is None else [Picture(base64.b64decode(item, validate=True)) for item in json.loads(value)]
                if not hasattr(audio, 'clear_pictures'):
                    raise ValueError('This format does not support FLAC picture blocks.')
                audio.clear_pictures()
                for picture in pictures:
                    audio.add_picture(picture)
            else:
                set_native_tag(audio, document.family, key, value)
        for key, value in fields.items():
            try:
                set_field(audio, document.family, key, value)
            except (ValueError, TypeError) as error:
                raise ValueError(f'{document.path.name}: {FIELD_MAP[key][1]}: {error}') from error
        if image_data is not None:
            replace_artwork(audio, document.family, image_data, mime)
        prepared.append((document, audio))
    saved, errors = [], []
    for document, audio in prepared:
        try:
            audio.save()
            path = filesystem_path(document.path)
            stamp = path.stat()
            if stamp.st_mtime_ns == document.stamp[1]:
                os.utime(path, ns=(stamp.st_atime_ns, max(time.time_ns(), stamp.st_mtime_ns + 1_000_000)))
            invalidate_track_metadata([document.path])
            saved.append(document.path)
        except Exception as error:
            errors.append(f'{document.path.name}: {error}')
    return saved, errors
