"""Windows thumbnail transport controls, using the shell's ITaskbarList3 API."""

import ctypes as ct
from ctypes import wintypes as wt
import logging
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer


class GUID(ct.Structure):
    _fields_ = [('data', ct.c_ubyte * 16)]

    @classmethod
    def parse(cls, value):
        return cls((ct.c_ubyte * 16).from_buffer_copy(UUID(value).bytes_le))


class ThumbButton(ct.Structure):
    _fields_ = [('mask', wt.DWORD), ('id', wt.UINT), ('bitmap', wt.UINT),
                ('icon', wt.HICON), ('tooltip', wt.WCHAR * 260), ('flags', wt.DWORD)]


class WindowsTaskbar(QAbstractNativeEventFilter):
    def __init__(self, window, icon_factory):
        super().__init__()
        self.window = window
        self.interface = ct.c_void_p()
        self.added = False
        self.last_state = None
        self.icons = {}
        self.com_initialized = False
        self.enabled = sys.platform == 'win32' and QApplication.platformName() == 'windows'
        if not self.enabled:
            return
        self.user = ct.WinDLL('user32', use_last_error=True)
        self.user.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
        self.user.RegisterWindowMessageW.restype = wt.UINT
        self.created_message = self.user.RegisterWindowMessageW('TaskbarButtonCreated')
        self.user.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ct.c_int, ct.c_int, wt.UINT]
        self.user.LoadImageW.restype = wt.HANDLE
        self.user.DestroyIcon.argtypes = [wt.HICON]
        self.ole = ct.WinDLL('ole32')
        self.ole.CoInitializeEx.argtypes = [ct.c_void_p, wt.DWORD]
        self.ole.CoInitializeEx.restype = ct.c_long
        self.ole.CoCreateInstance.argtypes = [ct.POINTER(GUID), ct.c_void_p, wt.DWORD,
                                             ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
        self.ole.CoCreateInstance.restype = ct.c_long
        clsid = GUID.parse('56FDF344-FD6D-11d0-958A-006097C9A090')
        iid = GUID.parse('EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF')
        try:
            initialized = self.ole.CoInitializeEx(None, 2)
            self.com_initialized = initialized in (0, 1)
            if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
                raise OSError(f'CoInitializeEx: {initialized:#x}')
            result = self.ole.CoCreateInstance(ct.byref(clsid), None, 1, ct.byref(iid), ct.byref(self.interface))
            if result < 0:
                raise OSError(f'CoCreateInstance: {result:#x}')
            if self.call(3) < 0:  # HrInit
                raise OSError('Taskbar initialization failed')
            with TemporaryDirectory(prefix='album-drive-taskbar-') as directory:
                for name in ('previous', 'play', 'pause', 'next'):
                    path = Path(directory) / (name + '.ico')
                    icon_factory(name, '#ffffff').pixmap(32, 32).save(str(path), 'ICO')
                    handle = self.user.LoadImageW(None, str(path), 1, 32, 32, 0x10)
                    if not handle:
                        raise ct.WinError(ct.get_last_error())
                    self.icons[name] = handle
            self.hwnd = int(window.winId())
            QApplication.instance().installNativeEventFilter(self)
        except (OSError, ValueError):
            logging.exception('Windows taskbar controls unavailable')
            self.close()

    def call(self, index, *args, types=()):
        table = ct.cast(self.interface, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        return ct.WINFUNCTYPE(ct.c_long, ct.c_void_p, *types)(table[index])(self.interface, *args)

    def nativeEventFilter(self, event_type, message):
        if not self.enabled or not self.interface:
            return False, 0
        msg = wt.MSG.from_address(int(message))
        if msg.hWnd != self.hwnd:
            return False, 0
        if msg.message == self.created_message:
            self.added = False  # Explorer can restart while the player stays open.
            self.last_state = None
            QTimer.singleShot(0, self.update)
        elif msg.message == 0x111 and (msg.wParam >> 16) & 0xffff == 0x1800:
            index = (msg.wParam & 0xffff) - 0x6a00
            if 0 <= index < 3:
                button = (self.window.previous, self.window.play, self.window.next)[index]
                if button.isEnabled():
                    button.click()
                return True, 0
        return False, 0

    def update(self):
        if not self.enabled or not self.interface:
            return
        window = self.window
        playing = window.player.playbackState() == QMediaPlayer.PlayingState
        names = ('previous', 'pause' if playing else 'play', 'next')
        enabled = tuple(button.isEnabled() for button in (window.previous, window.play, window.next))
        state = (names, enabled)
        if self.added and state == self.last_state:
            return
        buttons = (ThumbButton * 3)()
        for index, (name, active) in enumerate(zip(names, enabled)):
            buttons[index] = ThumbButton(0xe, 0x6a00 + index, 0, self.icons[name], name.title(), 0 if active else 1)
        result = self.call(16 if self.added else 15, self.hwnd, 3, buttons,
                           types=(wt.HWND, wt.UINT, ct.POINTER(ThumbButton)))
        if result >= 0:
            self.added = True
            self.last_state = state

    def close(self):
        if not self.enabled:
            return
        QApplication.instance().removeNativeEventFilter(self)
        if self.interface:
            self.call(2)  # Release on the GUI/COM apartment thread.
            self.interface = ct.c_void_p()
        for handle in self.icons.values():
            self.user.DestroyIcon(handle)
        self.icons.clear()
        if self.com_initialized:
            self.ole.CoUninitialize()
            self.com_initialized = False
