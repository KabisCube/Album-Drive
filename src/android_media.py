"""Tells Android's PlaybackService what is playing and receives its button presses.

Qt for Python has no JNI bindings on Android, so both directions travel over a local socket.
"""

import json
from pathlib import Path
import socket
import zlib

from PySide6.QtCore import QObject, QSocketNotifier, QStandardPaths, Signal

from responsive import running_on_android

MEDIA_SOCKET = '\0albumdrive-media'


class AndroidMedia(QObject):
    command = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connection = None
        self.notifier = None
        self.received = b''
        self.last_state = None
        self.last_bars = None
        self.cover_path = None

    def update(self, **state):
        if not running_on_android() or state == self.last_state:
            return
        try:
            if self.connection is None:
                self.connect()
            self.connection.send((json.dumps(state) + '\n').encode('utf-8'))
            self.last_state = state
        except BlockingIOError:
            pass
        except OSError:
            self.disconnect()

    def set_system_bars(self, color):
        """Paint the status and navigation bars in the app's background color."""
        if not running_on_android() or color == self.last_bars:
            return
        try:
            if self.connection is None:
                self.connect()
            self.connection.send((json.dumps({'systemBars': color}) + '\n').encode('utf-8'))
            self.last_bars = color
        except BlockingIOError:
            pass
        except OSError:
            self.disconnect()

    def connect(self):
        if not hasattr(socket, 'AF_UNIX'):
            raise OSError('Local sockets are unavailable')
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection.setblocking(False)
        self.connection.connect(MEDIA_SOCKET)
        self.notifier = QSocketNotifier(self.connection.fileno(), QSocketNotifier.Read, self)
        self.notifier.activated.connect(self.read)

    def disconnect(self):
        if self.notifier is not None:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.connection is not None:
            self.connection.close()
        self.connection = None
        self.last_state = None
        self.last_bars = None
        self.received = b''

    def read(self, *_):
        try:
            data = self.connection.recv(4096)
        except BlockingIOError:
            return
        except OSError:
            data = b''
        if not data:
            self.disconnect()
            return
        self.received += data
        *lines, self.received = self.received.split(b'\n')
        for line in lines:
            name, _, value = line.decode('utf-8', 'replace').partition(' ')
            self.command.emit(name, int(value) if value.isdigit() else 0)

    def cover_file(self, artwork):
        if not artwork:
            return ''
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
        path = folder / f'now-playing-{zlib.crc32(artwork):08x}'
        if path != self.cover_path:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(artwork)
            if self.cover_path is not None:
                self.cover_path.unlink(missing_ok=True)
            self.cover_path = path
        return str(path)
