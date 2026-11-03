import ctypes as ct
from ctypes import wintypes as wt
from contextlib import contextmanager
from io import BytesIO
import logging
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt

from windows_taskbar import GUID


APP_ID = 'AlbumDrive.MusicPlayer'
PROPERTY_FORMAT = GUID.parse('9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3')
STORE_IID = GUID.parse('886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99')


class PropertyKey(ct.Structure):
    _fields_ = [('format', GUID), ('id', wt.DWORD)]


class VariantValue(ct.Union):
    _fields_ = [('text', wt.LPWSTR), ('storage', ct.c_byte * (16 if ct.sizeof(ct.c_void_p) == 8 else 8))]


class PropVariant(ct.Structure):
    _fields_ = [('type', ct.c_ushort), ('reserved', ct.c_ushort * 3), ('value', VariantValue)]


def check(result):
    if result < 0:
        raise OSError(f'Windows shell: {result:#x}')


def call(pointer, index, *args, types=()):
    table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    return ct.WINFUNCTYPE(ct.c_long, ct.c_void_p, *types)(table[index])(pointer, *args)


@contextmanager
def interface(pointer):
    try:
        yield pointer
    finally:
        if pointer:
            call(pointer, 2)


def query(pointer, identity):
    result = ct.c_void_p()
    iid = GUID.parse(identity)
    check(call(pointer, 0, ct.byref(iid), ct.byref(result),
               types=(ct.POINTER(GUID), ct.POINTER(ct.c_void_p))))
    return result


class WindowsIdentity:
    def __init__(self):
        self.shell = ct.WinDLL('shell32')
        self.ole = ct.WinDLL('ole32')
        self.shell.SHGetPropertyStoreForWindow.argtypes = [wt.HWND, ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
        self.shell.SHGetPropertyStoreForWindow.restype = ct.c_long
        self.shell.SHChangeNotify.argtypes = [ct.c_long, wt.UINT, wt.LPCWSTR, wt.LPCWSTR]
        self.shell.SHChangeNotify.restype = None
        self.ole.CoCreateInstance.argtypes = [ct.POINTER(GUID), ct.c_void_p, wt.DWORD,
                                             ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
        self.ole.CoCreateInstance.restype = ct.c_long
        self.ole.PropVariantClear.argtypes = [ct.POINTER(PropVariant)]

    def set_properties(self, store, values):
        for identity, text in values:
            key = PropertyKey(PROPERTY_FORMAT, identity)
            buffer = ct.create_unicode_buffer(text)
            value = PropVariant()
            value.type = 31
            value.value.text = ct.cast(buffer, wt.LPWSTR)
            check(call(store, 6, ct.byref(key), ct.byref(value),
                       types=(ct.POINTER(PropertyKey), ct.POINTER(PropVariant))))

    def get_app_id(self, store):
        key = PropertyKey(PROPERTY_FORMAT, 5)
        value = PropVariant()
        try:
            check(call(store, 5, ct.byref(key), ct.byref(value),
                       types=(ct.POINTER(PropertyKey), ct.POINTER(PropVariant))))
            return value.value.text if value.type == 31 else None
        finally:
            self.ole.PropVariantClear(ct.byref(value))

    def update_window(self, window, icon_path):
        pointer = ct.c_void_p()
        check(self.shell.SHGetPropertyStoreForWindow(int(window.winId()), ct.byref(STORE_IID), ct.byref(pointer)))
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.append(str(Path(__file__).with_name('main.py')))
        with interface(pointer) as store:
            self.set_properties(store, ((2, subprocess.list2cmdline(command)), (4, 'Album Drive'),
                                        (3, f'{icon_path},0'), (5, APP_ID)))

    def update_shortcut(self, path, icon_path):
        pointer = ct.c_void_p()
        clsid = GUID.parse('00021401-0000-0000-C000-000000000046')
        iid = GUID.parse('000214F9-0000-0000-C000-000000000046')
        check(self.ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(pointer)))
        with interface(pointer) as link, interface(query(link, '0000010B-0000-0000-C000-000000000046')) as persist:
            check(call(persist, 5, str(path), 0, types=(wt.LPCWSTR, wt.DWORD)))
            with interface(query(link, '886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99')) as store:
                if self.get_app_id(store) != APP_ID:
                    return
            check(call(link, 17, str(icon_path), 0, types=(wt.LPCWSTR, ct.c_int)))
            check(call(persist, 6, str(path), True, types=(wt.LPCWSTR, wt.BOOL)))
            self.shell.SHChangeNotify(0x2000, 0x2005, str(path), None)

    def update(self, app):
        accent = app.property('themeIconAccent')
        if not accent:
            return
        directory = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Album Drive' / 'icons'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'theme-{accent.lstrip("#")}.ico'
        if not path.is_file():
            data = QByteArray()
            buffer = QBuffer(data)
            buffer.open(QIODevice.WriteOnly)
            if not app.windowIcon().pixmap(256, 256).save(buffer, 'PNG'):
                raise OSError('Cannot encode the application icon')
            with Image.open(BytesIO(bytes(data))) as image:
                image.save(path, format='ICO', sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
        for window in app.topLevelWidgets():
            if window.windowType() == Qt.Window:
                self.update_window(window, path)
        roaming = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
        pinned = roaming / 'Microsoft' / 'Internet Explorer' / 'Quick Launch' / 'User Pinned' / 'TaskBar'
        for shortcut in pinned.glob('*.lnk'):
            try:
                self.update_shortcut(shortcut, path)
            except OSError:
                logging.exception('Cannot refresh pinned icon: %s', shortcut)


def update_windows_identity(app):
    ole = ct.WinDLL('ole32')
    initialized = ole.CoInitializeEx(None, 2)
    try:
        if initialized < 0 and initialized != -2147417850:
            check(initialized)
        WindowsIdentity().update(app)
    except OSError:
        logging.exception('Cannot refresh Windows application identity')
    finally:
        if initialized in (0, 1):
            ole.CoUninitialize()
