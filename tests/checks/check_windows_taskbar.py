"""Native message dispatch and taskbar button state without opening a window."""

import ctypes as ct
from ctypes import wintypes as wt
import os
from unittest.mock import Mock

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtMultimedia import QMediaPlayer
from windows_taskbar import WindowsTaskbar

app = QApplication([])
window = Mock()
window.previous, window.play, window.next = [QPushButton() for _ in range(3)]
window.player.playbackState.return_value = QMediaPlayer.PlayingState
toolbar = WindowsTaskbar(window, Mock())
toolbar.enabled = True
toolbar.interface = ct.c_void_p(1)
toolbar.hwnd = 9876
toolbar.created_message = 0xc123
toolbar.icons = dict(previous=1, play=2, pause=3, next=4)
toolbar.call = Mock(return_value=0)
toolbar.update()
args = toolbar.call.call_args.args
assert args[:3] == (15, 9876, 3)
assert [button.tooltip for button in args[3]] == ['Previous', 'Pause', 'Next']
toolbar.update()
assert toolbar.call.call_count == 1  # Unchanged state does not call the shell.
window.next.setEnabled(False)
window.player.playbackState.return_value = QMediaPlayer.PausedState
toolbar.update()
args = toolbar.call.call_args.args
assert args[0] == 16 and args[3][1].tooltip == 'Play' and args[3][2].flags == 1
for index, button in enumerate((window.previous, window.play, window.next)):
    callback = Mock()
    button.clicked.connect(callback)
    message = wt.MSG()
    message.hWnd = toolbar.hwnd
    message.message = 0x111
    message.wParam = (0x1800 << 16) | (0x6a00 + index)
    assert toolbar.nativeEventFilter(None, ct.addressof(message)) == (True, 0)
    assert callback.call_count == (1 if button.isEnabled() else 0)
message.hWnd = 1234
assert toolbar.nativeEventFilter(None, ct.addressof(message)) == (False, 0)
message.hWnd = toolbar.hwnd
message.message = toolbar.created_message
toolbar.nativeEventFilter(None, ct.addressof(message))
assert not toolbar.added  # Explorer restart permits reinstallation.
toolbar.enabled = False
print('PASS: Previous/Play/Pause/Next native routing, enable state, shell updates and Explorer restart handling')
