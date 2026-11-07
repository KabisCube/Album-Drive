"""Asks AlbumDriveActivity for the Android keyboard tap, which follows the phone's touch feedback setting.

Qt for Python has no JNI bindings on Android, so the request travels over a local socket.
"""

import socket

from responsive import running_on_android

HAPTIC_SOCKET = '\0albumdrive-haptics'
_connection = None


def press_haptic():
    global _connection
    if not running_on_android():
        return
    try:
        if _connection is None:
            _connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            _connection.setblocking(False)
            _connection.connect(HAPTIC_SOCKET)
        _connection.send(b'\1')
    except BlockingIOError:
        pass
    except OSError:
        if _connection is not None:
            _connection.close()
        _connection = None
