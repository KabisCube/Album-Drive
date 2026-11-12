"""Local, read-only music discovery. No Qt dependency."""

import base64
import logging
import os
import re
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
from io import BytesIO
from pathlib import Path
from threading import Lock
from library_cache import AlbumCache, album_stamp
from file_paths import filesystem_path, library_path

import mutagen
from mutagen.flac import Picture
from PIL import Image

EXTENSIONS = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.aac', '.wav', '.aif', '.aiff', '.wma'}
MAX_ART_BYTES = 20 * 1024 * 1024
logger = logging.getLogger(__name__)
_track_cache = OrderedDict()
_track_cache_lock = Lock()


@dataclass
class Track:
    path: Path
    title: str
    artist: str = ''
    album: str = ''
    disc: int = 0
    number: int = 0
    seconds: float = 0
    release_date: str = ''
    cd_source: str = ''
    cd_start: int = 0
    cd_sectors: int = 0
    cd_disc_id: str = ''


@dataclass
class Album:
    folder: Path
    title: str
    artist: str
    tracks: list[Track]
    artwork: bytes = b''
    has_album_title: bool = False
    release_date: str = ''
    thumbnail: bytes = b''


def natural_key(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r'(\d+)', str(value)))


def tag_text(tags, *keys):
    for key in keys:
        try:
            value = tags.get(key)
        except ValueError:
            # Vorbis comments reject MP4's non-ASCII tag names, even on lookup.
            continue
        if value:
            if hasattr(value, 'text'):
                value = value.text
            if isinstance(value, (list, tuple)):
                value = value[0] if value else ''
            return repair_windows_text(str(value))
    return ''


def repair_windows_text(text):
    if not any('\x80' <= character <= '\x9f' for character in text):
        return text
    try:
        return text.encode('latin-1').decode('cp1252')
    except UnicodeError:
        return text


def tag_number(value):
    match = re.match(r'\d+', value)
    return int(match[0]) if match else 0


def release_date(value):
    match = re.search(r'(?<!\d)([12]\d{3})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?(?!\d)', value)
    if not match:
        return ''
    year, month, day = match.groups()
    try:
        return date(int(year), int(month or 1), int(day or 1)).isoformat()
    except ValueError:
        return f'{year}-01-01'


def readable_artwork(data, source):
    """Reject damaged images before Qt/libpng tries to render them."""
    if not data or len(data) > MAX_ART_BYTES:
        return b''
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        # Verification checks PNG checksums; loading also checks pixel filters.
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        logger.warning('Skipping unreadable cover image in %s: %s', source, error)
        return b''
    return data


def embedded_art(audio, source='audio tags'):
    tags = audio.tags or {}
    pictures = list(getattr(audio, 'pictures', []))
    if hasattr(tags, 'getall'):
        pictures.extend(tags.getall('APIC'))
    candidates = [p.data for p in sorted(pictures, key=lambda p: p.type != 3)]
    candidates.extend(tags.get('covr', []))
    for value in tags.get('WM/Picture', []):
        data = getattr(value, 'value', value)
        if isinstance(data, bytes) and len(data) >= 5:
            size = int.from_bytes(data[1:5], 'little')
            if 0 < size <= len(data) - 5:
                candidates.append(data[-size:])
    cover = tags.get('Cover Art (Front)')
    if cover is not None:
        data = getattr(cover, 'value', cover)
        if isinstance(data, bytes) and b'\0' in data:
            candidates.append(data.split(b'\0', 1)[1])
    for encoded in tags.get('metadata_block_picture', []):
        try:
            candidates.append(Picture(base64.b64decode(encoded)).data)
        except (mutagen.MutagenError, ValueError):
            continue
    for encoded in tags.get('coverart', []):
        try:
            candidates.append(base64.b64decode(encoded, validate=True))
        except (ValueError, TypeError):
            continue
    for data in candidates:
        artwork = readable_artwork(bytes(data), source)
        if artwork:
            return artwork
    return b''


def invalidate_track_metadata(paths):
    with _track_cache_lock:
        for path in paths:
            _track_cache.pop(path, None)


def read_track(path, want_art=True):
    """Reuse unchanged metadata while allowing embedded covers to be probed later."""
    try:
        info = filesystem_path(path).stat()
        stamp = (info.st_mtime_ns, info.st_ctime_ns, info.st_size)
    except OSError:
        return _read_track(path, want_art)
    with _track_cache_lock:
        cached = _track_cache.get(path)
        if cached and cached[0] == stamp and (not want_art or (cached[3] and not cached[4])):
            _track_cache.move_to_end(path)
            return replace(cached[1]), b'', cached[2]
    track, art, artist = _read_track(path, want_art)
    with _track_cache_lock:
        _track_cache[path] = (stamp, replace(track), artist, want_art, bool(art))
        _track_cache.move_to_end(path)
        while len(_track_cache) > 32768:
            _track_cache.popitem(last=False)
    return track, art, artist


def _read_track(path, want_art=True):
    track = Track(path, path.stem)
    art = b''
    album_artist = ''
    try:
        audio = mutagen.File(filesystem_path(path))
        if audio is not None:
            tags = audio.tags or {}
            track.title = tag_text(tags, 'TIT2', '\xa9nam', 'title', 'Title') or path.stem
            track.artist = tag_text(tags, 'TPE1', '\xa9ART', 'artist', 'Author')
            track.album = tag_text(tags, 'TALB', '\xa9alb', 'album', 'WM/AlbumTitle')
            track.release_date = release_date(tag_text(tags, 'TDRC', 'TYER', '\xa9day', 'date', 'year', 'WM/Year', 'originaldate'))
            album_artist = tag_text(tags, 'TPE2', 'aART', 'albumartist', 'WM/AlbumArtist')
            track.number = tag_number(tag_text(tags, 'TRCK', 'tracknumber', 'WM/TrackNumber'))
            track.disc = tag_number(tag_text(tags, 'TPOS', 'discnumber', 'WM/PartOfSet'))
            for key, attribute in [('trkn', 'number'), ('disk', 'disc')]:
                if tags.get(key):
                    setattr(track, attribute, int(tags[key][0][0]))
            track.seconds = max(0, float(getattr(audio.info, 'length', 0)))
            if want_art:
                art = embedded_art(audio, path)
    except (mutagen.MutagenError, OSError, ValueError, TypeError, IndexError, AttributeError):
        # A damaged tag must not hide an otherwise playable file.
        pass
    return track, art if len(art) <= MAX_ART_BYTES else b'', album_artist


DISC_FOLDER = re.compile(r'^(?:disc|disk|cd)[ _.-]*(\d+)(?:[ _.-]+.*)?$', re.IGNORECASE)
ART_NAMES = tuple(f'{name}.{extension}' for name in ('cover', 'folder', 'front', 'album art')
                  for extension in ('jpg', 'png', 'jpeg'))


def folder_art(folder, cancelled=lambda: False, tree=None):
    """Find front covers within an album without borrowing a child album's art."""
    candidates = []
    def indexed_walk():
        pending = [folder]
        while pending:
            directory = pending.pop()
            children, files = tree.get(directory, ((), ()))
            children = list(children)
            yield directory, children, files
            pending.extend(directory / name for name in reversed(children))

    indexed = tree is not None and folder in tree
    entries = indexed_walk() if indexed else os.walk(filesystem_path(folder), followlinks=False)
    for directory, folders, files in entries:
        if cancelled():
            return b''
        directory = library_path(directory)
        if not indexed:
            folders[:] = sorted((name for name in folders if not filesystem_path(directory / name).is_symlink()), key=natural_key)
        if (directory != folder and not DISC_FOLDER.fullmatch(directory.name)
                and any(Path(name).suffix.lower() in EXTENSIONS for name in files)):
            folders[:] = []
            continue
        for name in files:
            if name.startswith('.') or Path(name).suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                continue
            stem = Path(name).stem.casefold()
            front = re.search(r'(?:^|[^a-z])front(?:cover)?(?:$|[^a-z])', stem)
            other_art = re.search(r'(?:^|[^a-z])(?:back|disc|disk|cd|label|sleeve|inlay)(?:$|[^a-z])', stem)
            if front and not other_art:
                priority = 0
            elif name.casefold() in ART_NAMES:
                priority = 1
            else:
                continue
            path = directory / name
            relative = path.relative_to(folder)
            candidates.append((priority, len(relative.parts), natural_key(relative), path))
    for _, _, _, path in sorted(candidates):
        if cancelled():
            return b''
        try:
            with filesystem_path(path).open('rb') as source:
                artwork = source.read(MAX_ART_BYTES + 1)
            if artwork and len(artwork) <= MAX_ART_BYTES:
                artwork = readable_artwork(artwork, path)
                if artwork:
                    return artwork
        except OSError:
            continue
    return b''


def folder_artist(folder):
    candidate = folder.parent.name
    # Library containers and temporary folders are not artist names.
    if (not candidate or candidate.casefold() in
            {'music', 'artists', 'albums', 'soundtrack', 'soundtracks', 'various artists', 'temp', 'tmp'}
            or re.match(r'^tmp[a-z0-9_]{6,}$', candidate, re.IGNORECASE)):
        return 'Unknown artist'
    return candidate


def cover_thumbnail(artwork):
    if not artwork:
        return b''
    try:
        with Image.open(BytesIO(artwork)) as image:
            side = min(image.size)
            left, top = (image.width - side) // 2, (image.height - side) // 2
            image = image.crop((left, top, left + side, top + side))
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            output = BytesIO()
            if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                image.convert('RGBA').save(output, format='PNG')
            else:
                image.convert('RGB').save(output, format='JPEG', quality=88)
            return output.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError):
        return b''


def scan_library(root, cancelled=lambda: False, progress=lambda count: None, cache_path=None):
    """Discover album folders, grouping named disc subfolders; never follow symlinks."""
    albums, skipped, groups, tree = [], [], {}, {}

    def on_error(error):
        skipped.append(str(error))

    for directory, folders, files in os.walk(filesystem_path(root), followlinks=False, onerror=on_error):
        if cancelled():
            break
        directory = library_path(directory)
        folders[:] = sorted((f for f in folders if not filesystem_path(directory / f).is_symlink()), key=natural_key)
        tree[Path(directory)] = (tuple(folders), tuple(files))
        paths = sorted((Path(directory, f) for f in files if Path(f).suffix.lower() in EXTENSIONS), key=natural_key)
        if not paths:
            continue
        directory = Path(directory)
        disc = DISC_FOLDER.fullmatch(directory.name)
        album_folder = directory.parent if disc else directory
        if album_folder not in groups:
            groups[album_folder] = []
            progress(len(groups))
        groups[album_folder].extend((path, int(disc[1]) if disc else 0) for path in paths)

    cache = AlbumCache(cache_path) if cache_path is not None else None

    def load_album(entry):
        folder, paths = entry
        stamp = album_stamp(folder, paths, tree, EXTENSIONS, DISC_FOLDER, cancelled) if cache else None
        cached = cache.load(folder, stamp) if cache else None
        if cached is not None:
            return cached
        tracks, artists, embedded = [], [], b''
        for path, disc in paths:
            if cancelled():
                return None
            track, art, artist = read_track(path, not embedded)
            if disc and not track.disc:
                track.disc = disc
            tracks.append(track)
            embedded = embedded or art
            if artist:
                artists.append(artist)
        if cancelled():
            return None
        tracks.sort(key=lambda t: (t.disc, t.number, natural_key(t.path.name)))
        unique_artists = {t.artist for t in tracks if t.artist}
        artist = (artists[0] if artists else
                  next(iter(unique_artists)) if len(unique_artists) == 1 else
                  'Various artists' if unique_artists else folder_artist(folder))
        if artist not in ('Unknown artist', 'Various artists'):
            for track in tracks:
                if not track.artist:
                    track.artist = artist
        artwork = embedded or folder_art(folder, cancelled, tree)
        tagged_title = next((t.album for t in tracks if t.album.strip()), '')
        title = tagged_title or folder.name
        released = next((track.release_date for track in tracks if track.release_date), '') or release_date(folder.name)
        album = Album(folder, title, artist, tracks, artwork, bool(tagged_title), released, cover_thumbnail(artwork))
        if cache and not cancelled():
            cache.store(album, stamp)
        return album

    if cancelled():
        if cache:
            cache.close()
        return [], skipped
    # Albums are independent: overlap filesystem reads without blocking the UI.
    try:
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(groups)))) as workers:
            for album in workers.map(load_album, groups.items()):
                if cancelled():
                    return [], skipped
                if album is not None:
                    albums.append(album)
    finally:
        if cache:
            cache.close()
    albums.sort(key=lambda a: (natural_key(a.title), natural_key(a.folder)))
    return albums, skipped
