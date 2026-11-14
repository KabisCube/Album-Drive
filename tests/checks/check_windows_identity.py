import ctypes as ct
from ctypes import wintypes as wt
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'windows'

if sys.platform != 'win32':
    print('SKIP: Windows shell identity')
    sys.exit(0)

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication, QMainWindow
from app_identity import configure_app
from app_paths import ASSETS_DIR
from windows_identity import APP_ID, GUID, PROPERTY_FORMAT, STORE_IID, PropertyKey, PropVariant, WindowsIdentity, call, check, interface, query


app = QApplication([])
configure_app(app)
ole = ct.WinDLL('ole32')
initialized = ole.CoInitializeEx(None, 2)
check(initialized)
shell = WindowsIdentity()
window = QMainWindow()
window.winId()


class IconInfo(ct.Structure):
    _fields_ = [('icon', wt.BOOL), ('x', wt.DWORD), ('y', wt.DWORD),
                ('mask', wt.HBITMAP), ('color', wt.HBITMAP)]


class Bitmap(ct.Structure):
    _fields_ = [('type', wt.LONG), ('width', wt.LONG), ('height', wt.LONG),
                ('width_bytes', wt.LONG), ('planes', wt.WORD), ('bits_pixel', wt.WORD), ('bits', ct.c_void_p)]


shell.user.GetIconInfo.argtypes = [wt.HICON, ct.POINTER(IconInfo)]
shell.user.GetIconInfo.restype = wt.BOOL
gdi = ct.WinDLL('gdi32')
gdi.GetObjectW.argtypes = [wt.HANDLE, ct.c_int, ct.c_void_p]
gdi.DeleteObject.argtypes = [wt.HANDLE]


def native_icon_size(handle):
    info = IconInfo()
    if not shell.user.GetIconInfo(handle, ct.byref(info)):
        return None
    try:
        bitmap = Bitmap()
        assert gdi.GetObjectW(info.color, ct.sizeof(bitmap), ct.byref(bitmap))
        return bitmap.width, bitmap.height
    finally:
        gdi.DeleteObject(info.color)
        gdi.DeleteObject(info.mask)


def window_properties():
    pointer = ct.c_void_p()
    check(shell.shell.SHGetPropertyStoreForWindow(int(window.winId()), ct.byref(STORE_IID), ct.byref(pointer)))
    values = {}
    with interface(pointer) as store:
        for identity in (2, 3, 4, 5):
            key = PropertyKey(PROPERTY_FORMAT, identity)
            value = PropVariant()
            try:
                check(call(store, 5, ct.byref(key), ct.byref(value),
                           types=(ct.POINTER(PropertyKey), ct.POINTER(PropVariant))))
                values[identity] = value.value.text if value.type == 31 else None
            finally:
                shell.ole.PropVariantClear(ct.byref(value))
    return values


def create_shortcut(path, app_id):
    pointer = ct.c_void_p()
    clsid = GUID.parse('00021401-0000-0000-C000-000000000046')
    iid = GUID.parse('000214F9-0000-0000-C000-000000000046')
    check(shell.ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(pointer)))
    with interface(pointer) as link:
        check(call(link, 20, sys.executable, types=(wt.LPCWSTR,)))
        with interface(query(link, '886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99')) as store:
            shell.set_properties(store, ((5, app_id),))
            check(call(store, 7))
        with interface(query(link, '0000010B-0000-0000-C000-000000000046')) as persist:
            check(call(persist, 6, str(path), True, types=(wt.LPCWSTR, wt.BOOL)))


try:
    with TemporaryDirectory() as directory, patch.dict(os.environ, LOCALAPPDATA=directory, APPDATA=directory):
        root = Path(directory)
        pinned = root / 'Microsoft/Internet Explorer/Quick Launch/User Pinned/TaskBar'
        pinned.mkdir(parents=True)
        shortcut = pinned / 'Album Drive.lnk'
        unrelated = pinned / 'Other.lnk'
        create_shortcut(shortcut, APP_ID)
        create_shortcut(unrelated, 'Other.App')
        original = unrelated.read_bytes()
        icon = ASSETS_DIR / 'icons' / 'album-drive.ico'
        stale = root / 'Album Drive/icons/theme-cfe10e.ico'
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b'old')

        def shortcut_icon(path):
            pointer = ct.c_void_p()
            clsid = GUID.parse('00021401-0000-0000-C000-000000000046')
            iid = GUID.parse('000214F9-0000-0000-C000-000000000046')
            check(shell.ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(pointer)))
            with interface(pointer) as link, interface(query(link, '0000010B-0000-0000-C000-000000000046')) as persist:
                check(call(persist, 5, str(path), 0, types=(wt.LPCWSTR, wt.DWORD)))
                location = ct.create_unicode_buffer(32768)
                index = ct.c_int()
                check(call(link, 16, location, len(location), ct.byref(index),
                           types=(wt.LPWSTR, ct.c_int, ct.POINTER(ct.c_int))))
                return Path(location.value), index.value

        previous_icon = None
        for _ in range(2):
            shell.update(app)
            native_icon = window._theme_taskbar_icon.value
            assert native_icon_size(native_icon) == (256, 256)
            for size in (0, 1):
                assert shell.user.SendMessageW(int(window.winId()), 0x7f, size, 0) == native_icon
            if previous_icon:
                assert native_icon_size(previous_icon) is None
            previous_icon = native_icon
            properties = window_properties()
            assert properties[3] == f'{icon},0' and properties[5] == APP_ID
            assert shortcut_icon(shortcut) == (icon, 0)
            assert unrelated.read_bytes() == original
        assert not stale.exists(), 'old per-color icons are cleaned up'
        with Image.open(icon) as image:
            assert image.ico.sizes() == {(size, size) for size in (16, 24, 32, 48, 64, 128, 256)}
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert native_icon_size(previous_icon) is None
        from main import PlayerWindow
        music = root / 'Music'
        music.mkdir()
        settings = QSettings(str(root / 'player.ini'), QSettings.IniFormat)
        settings.setValue('folder', str(music))
        settings.setValue('browser_root', str(music))
        settings.setValue('welcome_complete', True)
        window = PlayerWindow(settings)
        assert not window.isVisible()
        properties = window_properties()
        assert properties[3] == f'{icon},0' and properties[5] == APP_ID
        assert native_icon_size(window._theme_taskbar_icon.value) == (256, 256)
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        dragged = pinned / 'AlbumDrive.lnk'
        create_shortcut(dragged, None)
        with patch.object(sys, 'frozen', True, create=True):
            shell.update(app)
        assert shortcut_icon(dragged)[0] == icon
        assert unrelated.read_bytes() == original
finally:
    ole.CoUninitialize()

print("PASS: static taskbar identity before first show, native icon cleanup, pinned updates, stale themed icons removed, unrelated shortcuts preserved")
