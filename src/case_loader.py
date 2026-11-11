"""Prepares album-grid case artwork on worker threads so decoding never stalls scrolling.

Workers do the heavy lifting with Pillow, which releases the GIL while it decodes, pastes and
resizes; PySide keeps the GIL through most Qt image calls, so Qt work on a worker would freeze the
GUI thread anyway. The only Qt step here renders each tray colour's empty shell once. The GUI
thread just wraps the finished pixels. Each request carries the library generation, so results
for a folder that is no longer shown are dropped."""

import sys
from collections import namedtuple
from functools import lru_cache
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

from PIL import Image
from PySide6.QtCore import QObject, QRectF, Signal
from PySide6.QtGui import QColor, QImage

from case_geometry import CASE_HEIGHT, CASE_PIXMAP_SIZE, CASE_WIDTH, sleeve_rect
from case_shell import artwork_tray_color, shell_image

_scale = CASE_PIXMAP_SIZE.width() / CASE_WIDTH
_sleeve = sleeve_rect(QRectF(0, 0, CASE_WIDTH, CASE_HEIGHT))
SLEEVE_BOX = (round(_sleeve.x() * _scale), round(_sleeve.y() * _scale), round(_sleeve.width() * _scale))
PreparedCase = namedtuple('PreparedCase', 'source source_size icon icon_size tray')
_shell_lock = Lock()


@lru_cache(maxsize=32)
def shell_layer(tray_name):
    image = shell_image(tray_name).convertToFormat(QImage.Format_RGBA8888)
    return Image.frombytes('RGBA', (image.width(), image.height()), bytes(image.constBits()))


def fitted(size, target):
    scale = min(target[0] / size[0], target[1] / size[1])
    return max(1, round(size[0] * scale)), max(1, round(size[1] * scale))


def prepare_case(artwork, tray_source, target):
    """Return the finished case and its grid-sized copy as RGBA bytes, or no pixels to let Qt try."""
    tray = artwork_tray_color(tray_source) if tray_source else None
    if not artwork:
        return PreparedCase(None, None, None, None, tray)
    x, y, side = SLEEVE_BOX
    try:
        with Image.open(BytesIO(artwork)) as cover:
            cover.draft('RGB', (side, side))
            cover = cover.convert('RGB')
        crop = min(cover.size)
        left, top = (cover.width - crop) // 2, (cover.height - crop) // 2
        cover = cover.crop((left, top, left + crop, top + crop)).resize((side, side), Image.BICUBIC)
    except (OSError, ValueError, Image.DecompressionBombError):
        return PreparedCase(None, None, None, None, tray)  # Qt gets one more try on the GUI thread.
    with _shell_lock:
        shell = shell_layer(QColor(tray).name() if tray else '')
    case = shell.copy()
    case.paste(cover, (x, y))
    icon = case.resize(fitted(case.size, target), Image.BICUBIC)
    return PreparedCase(case.tobytes(), case.size, icon.tobytes(), icon.size, tray)


class CaseLoader(QObject):
    loaded = Signal(object)

    def __init__(self, prepare, parent=None, workers=2):
        super().__init__(parent)
        self.prepare = prepare
        # Workers still run some Python; hand the GIL back to the GUI thread within a millisecond.
        sys.setswitchinterval(min(sys.getswitchinterval(), .001))
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='case-loader')
        self.pending = {}
        self.closed = False

    def request(self, generation, index, arguments):
        if self.closed or (generation, index) in self.pending:
            return
        self.pending[(generation, index)] = self.pool.submit(self.work, generation, index, arguments)

    def work(self, generation, index, arguments):
        try:
            prepared = self.prepare(*arguments)
        except Exception as error:  # A bad file must not kill the worker; the GUI falls back to Qt.
            print(f'Case artwork preparation failed for album {index}: {error}')
            prepared = PreparedCase(None, None, None, None, None)
        if not self.closed:
            self.loaded.emit((generation, index, prepared))

    def finished(self, generation, index):
        self.pending.pop((generation, index), None)

    def keep_only(self, generation, indexes):
        for key, future in list(self.pending.items()):
            if (key[0] != generation or key[1] not in indexes) and future.cancel():
                del self.pending[key]

    def shutdown(self):
        self.closed = True
        for future in self.pending.values():
            future.cancel()
        self.pending.clear()
        self.pool.shutdown(wait=False, cancel_futures=True)
