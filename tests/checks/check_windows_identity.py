import ctypes as ct
from ctypes import wintypes as wt
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

if sys.platform != 'win32':
    print('SKIP: Windows shell identity')
    sys.exit(0)

from PIL import Image
from PySide6.QtWidgets import QApplication
from app_identity import update_theme_icon
from windows_identity import APP_ID, GUID, WindowsIdentity, call, check, interface, query


app = QApplication([])
ole = ct.WinDLL('ole32')
initialized = ole.CoInitializeEx(None, 2)
check(initialized)
shell = WindowsIdentity()


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
        paths = []
        for accent in ('#cfe10e', '#a03070'):
            update_theme_icon(app, accent)
            shell.update(app)
            icon = root / 'Album Drive/icons' / f'theme-{accent[1:]}.ico'
            assert icon.is_file()
            with Image.open(icon) as image:
                assert image.ico.sizes() == {(size, size) for size in (16, 24, 32, 48, 64, 128, 256)}
                pixels = image.convert('RGBA')
                colors = [pixels.getpixel((x, y)) for y in range(pixels.height) for x in range(pixels.width)]
                assert any(color[3] == 0 for color in colors)
                assert all(color[:3] == tuple(bytes.fromhex(accent[1:]))
                           for color in colors if color[3] == 255)
            pointer = ct.c_void_p()
            clsid = GUID.parse('00021401-0000-0000-C000-000000000046')
            iid = GUID.parse('000214F9-0000-0000-C000-000000000046')
            check(shell.ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(pointer)))
            with interface(pointer) as link, interface(query(link, '0000010B-0000-0000-C000-000000000046')) as persist:
                check(call(persist, 5, str(shortcut), 0, types=(wt.LPCWSTR, wt.DWORD)))
                location = ct.create_unicode_buffer(32768)
                index = ct.c_int()
                check(call(link, 16, location, len(location), ct.byref(index),
                           types=(wt.LPWSTR, ct.c_int, ct.POINTER(ct.c_int))))
                assert Path(location.value) == icon and index.value == 0
            assert unrelated.read_bytes() == original
            paths.append(icon)
        assert all(path.is_file() for path in paths)
finally:
    ole.CoUninitialize()

print('PASS: persistent multiresolution theme icons, matching pinned shortcuts, preserved unrelated shortcuts')
