"""Disposable SQLite album metadata, artwork and thumbnail cache."""

from dataclasses import asdict
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from threading import Lock
from file_paths import filesystem_path

CACHE_VERSION = 2


class AlbumCache:
    def __init__(self, path):
        self.lock = Lock()
        self.connection = None
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(path), timeout=.5, check_same_thread=False)
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.connection.execute('CREATE TABLE IF NOT EXISTS albums '
                                    '(folder TEXT PRIMARY KEY, stamp TEXT, metadata TEXT, artwork BLOB, thumbnail BLOB)')
        except (OSError, sqlite3.Error) as error:
            logging.warning('Album cache unavailable: %s', error)
            self.close()

    def load(self, folder, stamp):
        if self.connection is None or stamp is None:
            return None
        try:
            with self.lock:
                row = self.connection.execute('SELECT metadata, artwork, thumbnail FROM albums WHERE folder=? AND stamp=?',
                                              (str(folder.resolve()), stamp)).fetchone()
            if row:
                from library import Album, Track
                metadata = json.loads(row[0])
                tracks = [Track(**dict(track, path=Path(track['path']))) for track in metadata.pop('tracks')]
                return Album(folder=folder, tracks=tracks, artwork=bytes(row[1]), thumbnail=bytes(row[2]), **metadata)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
            pass
        return None

    def store(self, album, stamp):
        if self.connection is None or stamp is None:
            return
        metadata = dict(title=album.title, artist=album.artist, has_album_title=album.has_album_title,
                        release_date=album.release_date,
                        tracks=[dict(asdict(track), path=str(track.path)) for track in album.tracks])
        try:
            with self.lock:
                self.connection.execute('INSERT OR REPLACE INTO albums VALUES (?, ?, ?, ?, ?)',
                                        (str(album.folder.resolve()), stamp, json.dumps(metadata), album.artwork, album.thumbnail))
        except sqlite3.Error:
            pass

    def close(self):
        if self.connection is not None:
            try:
                self.connection.commit()
            except sqlite3.Error:
                pass
            self.connection.close()
            self.connection = None


def album_stamp(folder, paths, tree, extensions, disc_pattern, cancelled):
    """Stat tracks and relevant cover files, without reopening their contents."""
    entries = [(path, disc) for path, disc in paths]
    pending = [folder]
    while pending:
        directory = pending.pop()
        children, files = tree.get(directory, ((), ()))
        if directory != folder and not disc_pattern.fullmatch(directory.name) and any(Path(name).suffix.lower() in extensions for name in files):
            continue
        entries.extend((directory / name, 0) for name in files if Path(name).suffix.lower() in {'.png', '.jpg', '.jpeg'})
        pending.extend(directory / name for name in children)
    signature = []
    try:
        for path, disc in sorted(entries):
            if cancelled():
                return None
            stat = filesystem_path(path).stat()
            signature.append((str(path), disc, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
    except OSError:
        return None
    return hashlib.sha256(repr((CACHE_VERSION, signature)).encode('utf-8')).hexdigest()
