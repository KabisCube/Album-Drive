"""Stationary glare, case-bound scuffs, finish layering and centered logos."""
import os
from io import BytesIO
from dataclasses import replace
from unittest.mock import patch
from PIL import Image
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QApplication
from case_finish import finish_for_album, paint_case_finish, reflection_gradient, sleeve_rect
from main import cd_case_pixmap, load_app_font
from themes import ChunkyBrand
from case_shell import case_variant
from case_geometry import CASE_WIDTH, CASE_HEIGHT
from pathlib import Path
from main import NowPlayingCover
from open_case import CaseFront

app = QApplication([])
load_app_font()
keys = [f'Album {index}' for index in range(80)]
styles = [finish_for_album(key) for key in keys]
assert len({style.variant for style in styles}) == 5
assert all(style.scratches for style in styles)
assert any(len(style.scratches) <= 6 for style in styles) and any(len(style.scratches) > 6 for style in styles)
first = finish_for_album(keys[0])
finish_for_album.cache_clear()
assert finish_for_album(keys[0]) == first
rect = QRectF(50, 50, 216, 196.8)
for style in styles:
    assert 30 <= max(color.alpha() for _, color in reflection_gradient(rect, style).stops()) <= 94

def reflection(angle, key, case_rect=rect):
    pixmap = QPixmap(320, 300)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    # Isolate lighting when comparing pixels across different physical cases.
    with patch('case_finish.finish_for_album', return_value=replace(finish_for_album(key), scratches=())):
        paint_case_finish(painter, case_rect, angle, key)
    painter.end()
    return pixmap.toImage()

key = keys[0]
straight, rotated = reflection(0, key), reflection(25, key)
shared, edges_changed = 0, 0
inner = sleeve_rect(rect).adjusted(2, 2, -2, -2)
rotation = QTransform().translate(rect.center().x(), rect.center().y()).rotate(25).translate(-rect.center().x(), -rect.center().y())
inverse, _ = rotation.inverted()
for x in range(320):
    for y in range(300):
        a, b = straight.pixelColor(x, y), rotated.pixelColor(x, y)
        point = QPointF(x + .5, y + .5)
        if inner.contains(point) and inner.contains(inverse.map(point)):
            assert abs(a.alpha() - b.alpha()) <= 1, 'Reflection rotated with the case'
            shared += 1
        if bool(a.alpha()) != bool(b.alpha()):
            edges_changed += 1
assert shared > 1000 and edges_changed > 1000

# Different cases scrolling through the same screen position share exactly the
# same reflection. Wear still travels with its physical case.
other_key = keys[1]
shifted_rect = rect.translated(0, -35)
shifted = reflection(0, other_key, shifted_rect)
overlap = sleeve_rect(rect).intersected(sleeve_rect(shifted_rect)).adjusted(2, 2, -2, -2).toAlignedRect()
for x in range(overlap.left(), overlap.right()):
    for y in range(overlap.top(), overlap.bottom()):
        assert straight.pixelColor(x, y) == shifted.pixelColor(x, y), 'Glare followed a case while scrolling'

# Verify the actual widgets composite the finish above opaque artwork, including
# white sleeves where a white-only glare would disappear.
for sleeve_color in ('#28445b', '#f4f4f4'):
    data = BytesIO()
    Image.new('RGB', (200, 200), sleeve_color).save(data, format='PNG')
    base = cd_case_pixmap(data.getvalue(), '', case_key=key)
    for widget in (NowPlayingCover(), CaseFront(None)):
        widget.resize(244, 224)
        if isinstance(widget, NowPlayingCover):
            widget.setPixmap(base)
        else:
            widget.pixmap = base
        widget.sheen_key = ''
        plain = widget.grab().toImage()
        widget.sheen_key = key
        coated = widget.grab().toImage()
        changes = [abs(plain.pixelColor(x, y).red() - coated.pixelColor(x, y).red())
                   for x in range(60, 195, 3) for y in range(45, 170, 3)]
        assert sum(changes) / len(changes) > (2 if sleeve_color == '#f4f4f4' else 9), (type(widget).__name__, sleeve_color, sum(changes) / len(changes), max(changes))
        widget.close()

app.setProperty('brandTextColor', '#00ff00')
app.setProperty('brandLineColor', '#332211')
brand = ChunkyBrand('Album Drive')
font = QFont(app.font())
font.setPixelSize(30)
brand.setFont(font)
brand.resize(480, 140)
brand.setStyleSheet('background: #101010;')
for thickness in (0, 100, 200, 300):
    app.setProperty('uiThickness', thickness)
    image = brand.grab().toImage()
    ink, backdrop = [], []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y).name()
            if color in ('#00ff00', QColor('#00ff00').darker(150).name()):
                ink.append(y)
            elif color == '#332211':
                backdrop.append(y)
    assert ink and backdrop
    assert abs((min(ink) + max(ink)) / 2 - (min(backdrop) + max(backdrop)) / 2) <= 1
    assert min(ink) >= min(backdrop) and max(ink) <= max(backdrop)
brand.close()

# A contact sheet using identical sleeves makes the gentle variations visible.
Path('build').mkdir(exist_ok=True)
sheet = QPixmap(1040, 500)
sheet.fill(QColor('#393939'))
painter = QPainter(sheet)
painter.setRenderHint(QPainter.SmoothPixmapTransform)
cover = BytesIO()
Image.new('RGB', (200, 200), '#28445b').save(cover, format='PNG')
assert {case_variant(key) for key in keys} == set(range(4))
shell_pixels = set()
for index in range(8):
    base = cd_case_pixmap(cover.getvalue(), '', case_key=keys[index])
    shell_pixels.add(base.toImage().pixelColor(45, 180).name())
    assert base.toImage().pixelColor(260, 260).name() == '#28445b', 'Sleeve was modified'
    target = QRectF(18 + index % 4 * 260, 18 + index // 4 * 245, 224, 224 * CASE_HEIGHT / CASE_WIDTH)
    angle = (-10, 0, 12, -4)[index % 4]
    painter.save()
    painter.translate(target.center())
    painter.rotate(angle)
    painter.translate(-target.center())
    painter.drawPixmap(target, base, QRectF(base.rect()))
    painter.restore()
    paint_case_finish(painter, target, angle, keys[index])
assert len(shell_pixels) == 1
painter.end()
sheet.save('build/case-finish-variations.png')
print('PASS: shared stationary glare, case-bound scuffs, finish above artwork and centered logos')
