"""Build the CD case icon as SVG, then render it to PNG and a Windows multi-resolution ICO.
The case is drawn upright and the whole group is tilted, so every measurement below is in the upright case's units."""

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

TILT = -5.6
VIEW = (167, 163.5, 690, 690)
FACE = (168, 260.5, 775, 822)
DEPTH = (-22, 30)
RADIUS = 6
BORDER = 25
SPINE_RIGHT = 262
INSET = (282, 303, 731, 787)
DISC = (501, 550, 227, 52.5)
GLARE_SLOPE = 1.215
GLARE_BANDS = ((277, 337.5), (391, 702))
GLARE_AT = 290

FRAME = '#d3d3d3'
SIDE = '#bbbbb1'
SPINE = '#4b4b4b'
SPINE_SIDE = '#414141'
ART = '#f0883a'


def polygon(points):
    return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in points) + ' Z'


def clip(points, left, top, right, bottom):
    for inside, cross in (
            (lambda p: p[0] >= left, lambda a, b: (left, a[1] + (b[1] - a[1]) * (left - a[0]) / (b[0] - a[0]))),
            (lambda p: p[0] <= right, lambda a, b: (right, a[1] + (b[1] - a[1]) * (right - a[0]) / (b[0] - a[0]))),
            (lambda p: p[1] >= top, lambda a, b: (a[0] + (b[0] - a[0]) * (top - a[1]) / (b[1] - a[1]), top)),
            (lambda p: p[1] <= bottom, lambda a, b: (a[0] + (b[0] - a[0]) * (bottom - a[1]) / (b[1] - a[1]), bottom))):
        result = []
        for index, current in enumerate(points):
            previous = points[index - 1]
            if inside(current):
                if not inside(previous):
                    result.append(cross(previous, current))
                result.append(current)
            elif inside(previous):
                result.append(cross(previous, current))
        points = result
    return points


def icon_svg():
    left, top, right, bottom = FACE
    dx, dy = DEPTH
    art = (SPINE_RIGHT, top + BORDER, right - BORDER, bottom - BORDER)
    ax0, ay0, ax1, ay1 = art
    i = RADIUS
    body = polygon([(left + i, top + i), (right - i, top + i), (right - i, bottom - i), (right - i + dx, bottom - i + dy),
                    (left + i + dx, bottom - i + dy), (left + i + dx, top + i + dy)])
    spine_side = polygon([(left, ay0), (left, ay1), (left + dx, ay1 + dy), (left + dx, ay0 + dy)])
    ix0, iy0, ix1, iy1 = INSET
    band = (f'M{ax0} {ay0} H{ax1} V{ay1} H{ax0} Z M{ix0} {iy0} V{iy1} H{ix1} V{iy0} Z')
    cx, cy, outer, hole = DISC
    disc = (f'M{cx - outer} {cy} a{outer} {outer} 0 1 0 {2 * outer} 0 a{outer} {outer} 0 1 0 {-2 * outer} 0 Z '
            f'M{cx - hole} {cy} a{hole} {hole} 0 1 1 {2 * hole} 0 a{hole} {hole} 0 1 1 {-2 * hole} 0 Z')
    glare = []
    for start, end in GLARE_BANDS:
        def at(x, y):
            return (x + GLARE_SLOPE * (y - GLARE_AT), y)
        band_points = [at(start, ay0 - 1), at(end, ay0 - 1), at(end, ay1 + 1), at(start, ay1 + 1)]
        glare.append(polygon(clip(band_points, *art)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{VIEW[2]}" height="{VIEW[3]}" viewBox="{' '.join(map(str, VIEW))}">
  <g transform="rotate({TILT})">
    <path d="{body}" fill="{SIDE}" stroke="{SIDE}" stroke-width="{2 * RADIUS}" stroke-linejoin="round"/>
    <path d="{spine_side}" fill="{SPINE_SIDE}"/>
    <rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" rx="{RADIUS}" fill="{FRAME}"/>
    <rect x="{left - 1}" y="{ay0}" width="{ax0 - left + 1}" height="{ay1 - ay0}" fill="{SPINE}"/>
    <rect x="{ax0}" y="{ay0}" width="{ax1 - ax0}" height="{ay1 - ay0}" fill="{ART}"/>
    <path d="{band}" fill="#000000" fill-opacity=".06" fill-rule="evenodd"/>
    <path d="{disc}" fill="#ffffff" fill-opacity=".11" fill-rule="evenodd"/>
    <path d="{glare[0]}" fill="#ffffff" fill-opacity=".15"/>
    <path d="{glare[1]}" fill="#ffffff" fill-opacity=".15"/>
  </g>
</svg>
'''


def main():
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1] / 'assets' / 'icons'
    (root / 'album-drive.svg').write_text(icon_svg(), encoding='utf-8')
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
    print(f'Created {root / "album-drive.svg"}, album-drive.png and album-drive.ico')


if __name__ == '__main__':
    main()
