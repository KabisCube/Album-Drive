"""Render the editable CD icon into PNG and Windows multi-resolution ICO."""

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1] / 'assets' / 'icons'
    renderer = QSvgRenderer(str(root / 'album-drive.svg'))
    if not renderer.isValid():
        raise RuntimeError('Invalid Album Drive SVG icon')
    image = QImage(1024, 1024, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, 1024, 1024))
    painter.end()
    if not image.save(str(root / 'album-drive.png')):
        raise RuntimeError('Unable to save icon PNG')
    with Image.open(root / 'album-drive.png') as source:
        source.save(root / 'album-drive.ico', sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    print(f'Created {root / "album-drive.png"} and album-drive.ico')


if __name__ == '__main__':
    main()
