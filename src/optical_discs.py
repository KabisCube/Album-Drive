"""Read-only Windows optical-disc discovery and digital CD audio preparation."""

import ctypes as ct
from ctypes import wintypes as wt
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sys
from uuid import uuid4
import wave

from PySide6.QtCore import QThread, Signal

from library import Album, Track, cover_thumbnail, folder_art


@dataclass(frozen=True)
class Disc:
    root: str
    title: str
    identity: str
    audio: tuple = ()  # (track number, starting sector, sector count)


class RawReadInfo(ct.Structure):
    _fields_ = [('offset', ct.c_int64), ('sectors', ct.c_uint32), ('mode', ct.c_int32)]


def parse_toc(data):
    """Decode Windows CDROM_TOC, including its lead-out entry."""
    if len(data) < 4:
        raise ValueError('Incomplete CD table of contents')
    first, last = data[2:4]
    count = last - first + 1
    if not 1 <= first <= last <= 99 or len(data) < 4 + (count + 1) * 8:
        raise ValueError('Invalid CD table of contents')
    entries = [data[4 + index * 8:12 + index * 8] for index in range(count + 1)]
    def sector(entry):
        return (entry[5] * 60 + entry[6]) * 75 + entry[7] - 150
    audio = []
    for entry, following in zip(entries, entries[1:]):
        start, end = sector(entry), sector(following)
        if not entry[1] & 4 and start >= 0 and end > start:
            audio.append((entry[2], start, end - start))
    canonical = data[:4 + (count + 1) * 8]
    return hashlib.sha256(canonical).hexdigest(), tuple(audio)


class WindowsDiscDevice:
    def __init__(self, root):
        self.root = root
        self.kernel = ct.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ct.c_void_p,
                                            wt.DWORD, wt.DWORD, wt.HANDLE]
        self.kernel.CreateFileW.restype = wt.HANDLE
        self.kernel.CloseHandle.argtypes = [wt.HANDLE]
        self.kernel.DeviceIoControl.argtypes = [wt.HANDLE, wt.DWORD, ct.c_void_p, wt.DWORD,
                                                ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD), ct.c_void_p]
        self.kernel.DeviceIoControl.restype = wt.BOOL
        self.handle = self.kernel.CreateFileW('\\\\.\\' + root[:2], 0x80000000, 3, None, 3, 0, None)
        if self.handle == ct.c_void_p(-1).value:
            raise ct.WinError(ct.get_last_error())

    def ioctl(self, code, size, request=None):
        output = ct.create_string_buffer(size) if size else None
        received = wt.DWORD()
        if not self.kernel.DeviceIoControl(self.handle, code, ct.byref(request) if request is not None else None,
                                           ct.sizeof(request) if request is not None else 0,
                                           output, size, ct.byref(received), None):
            raise ct.WinError(ct.get_last_error())
        return output.raw[:received.value] if output is not None else b''

    def toc(self):
        return parse_toc(self.ioctl(0x24000, 804))

    def read_audio(self, start, count):
        data = self.ioctl(0x2403e, count * 2352, RawReadInfo(start * 2048, count, 2))
        if len(data) != count * 2352:
            raise OSError('The CD drive returned incomplete audio. Check the disc and try again.')
        return data

    def eject(self):
        # Win32 IOCTL_STORAGE_MEDIA_REMOVAL / IOCTL_STORAGE_EJECT_MEDIA.
        # https://learn.microsoft.com/windows/win32/api/winioctl/ni-winioctl-ioctl_storage_eject_media
        self.ioctl(0x2d4804, 0, ct.c_ubyte(0))
        self.ioctl(0x2d4808, 0)

    def close(self):
        self.kernel.CloseHandle(self.handle)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def discover_discs(cancelled=lambda: False):
    if sys.platform != 'win32':
        return []
    kernel = ct.WinDLL('kernel32', use_last_error=True)
    kernel.GetDriveTypeW.argtypes = [wt.LPCWSTR]
    kernel.GetVolumeInformationW.argtypes = [wt.LPCWSTR, wt.LPWSTR, wt.DWORD, ct.POINTER(wt.DWORD),
                                             ct.POINTER(wt.DWORD), ct.POINTER(wt.DWORD), wt.LPWSTR, wt.DWORD]
    kernel.SetThreadErrorMode.argtypes = [wt.DWORD, ct.POINTER(wt.DWORD)]
    old_mode = wt.DWORD()
    kernel.SetThreadErrorMode(1, ct.byref(old_mode))  # Never show Windows' empty-drive dialog.
    result = []
    try:
        drives = kernel.GetLogicalDrives()
        for index in range(26):
            if cancelled():
                break
            root = f'{chr(65 + index)}:\\'
            if not drives & (1 << index) or kernel.GetDriveTypeW(root) != 5:
                continue
            label, serial = ct.create_unicode_buffer(256), wt.DWORD()
            mounted = kernel.GetVolumeInformationW(root, label, 256, ct.byref(serial), None, None, None, 0)
            try:
                with WindowsDiscDevice(root) as device:
                    identity, audio = device.toc()
            except (OSError, ValueError):
                if not mounted:
                    continue
                identity, audio = f'volume-{serial.value:x}', ()
            title = label.value.strip() or ('Audio CD' if audio else 'Disc')
            result.append(Disc(root, title, identity, audio))
    finally:
        kernel.SetThreadErrorMode(old_mode.value, None)
    return result


def audio_album(disc, cache_folder, cancelled=lambda: False):
    if not disc.audio:
        return None
    title = disc.title
    root = Path(disc.root)
    artwork = folder_art(root, cancelled)
    tracks = [Track(Path(cache_folder) / 'cd-audio' / disc.identity / f'{number:02}.wav',
                    f'Track {number:02}', album=title, number=number, seconds=count / 75,
                    cd_source=disc.root, cd_start=start, cd_sectors=count, cd_disc_id=disc.identity)
              for number, start, count in disc.audio]
    return Album(root / '.audio-cd', title, '', tracks, artwork, True,
                 thumbnail=cover_thumbnail(artwork))


def cached_audio_valid(track):
    try:
        if track.path.stat().st_size < 44 + track.cd_sectors * 2352:
            return False
        with wave.open(str(track.path), 'rb') as audio:
            return (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (
                2, 2, 44100, track.cd_sectors * 588)
    except (OSError, EOFError, wave.Error):
        return False


def prepare_audio(track, cancelled=lambda: False, progress=lambda value: None, device_factory=WindowsDiscDevice):
    """Prepare one requested track; leave both the CD and music library untouched."""
    if cancelled():
        return None
    if cached_audio_valid(track):
        return track.path
    target = track.path
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f'{target.name}.{uuid4().hex}.part')
    try:
        with device_factory(track.cd_source) as device:
            identity, _ = device.toc()
            if identity != track.cd_disc_id:
                raise OSError('The disc has changed. Select the inserted CD again.')
            with wave.open(str(temporary), 'wb') as audio:
                audio.setnchannels(2)
                audio.setsampwidth(2)
                audio.setframerate(44100)
                completed = 0
                while completed < track.cd_sectors:
                    if cancelled():
                        return None
                    count = min(16, track.cd_sectors - completed)
                    audio.writeframesraw(device.read_audio(track.cd_start + completed, count))
                    completed += count
                    progress(round(completed * 100 / track.cd_sectors))
        if cancelled():
            return None
        os.replace(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


class DiscMonitor(QThread):
    result = Signal(object)

    def run(self):
        discs = discover_discs(self.isInterruptionRequested)
        if not self.isInterruptionRequested():
            self.result.emit(discs)


def eject_disc(root, device_factory=WindowsDiscDevice):
    if sys.platform != 'win32':
        raise OSError('Disc ejection is only available on Windows.')
    with device_factory(root) as device:
        device.eject()


class DiscEjector(QThread):
    result = Signal(bool, str)

    def __init__(self, root, parent):
        super().__init__(parent)
        self.root = root

    def run(self):
        try:
            eject_disc(self.root)
            self.result.emit(True, '')
        except OSError as error:
            self.result.emit(False, str(error))


class DiscReader(QThread):
    ready = Signal(object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, track, parent):
        super().__init__(parent)
        self.track = track

    def run(self):
        try:
            previous = -1
            def progress(value):
                nonlocal previous
                if value != previous:
                    previous = value
                    self.progress.emit(value)
            path = prepare_audio(self.track, self.isInterruptionRequested, progress)
            if path is not None and not self.isInterruptionRequested():
                self.ready.emit(path)
        except (OSError, ValueError, wave.Error) as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
