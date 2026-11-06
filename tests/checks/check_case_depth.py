import os
from PIL import Image

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from case_shell import CASE_COLOR, CASE_DEPTH, CASE_SHADOW_ENABLED, paint_cd_case
from case_geometry import CASE_PIXMAP_SIZE, CASE_WIDTH, sleeve_rect
from main import cd_case_pixmap
from themes import control_offset


app = QApplication([])
window = QWidget()
window.resize(900, 260)
source = cd_case_pixmap(b'', '', case_key='depth-test')
assert source.size() == CASE_PIXMAP_SIZE
assert source.toImage().pixelColor(0, 0).alpha() == 0
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    depth = CASE_DEPTH
    for rect in (QRectF(20, 30, 240, 219), QRectF(640, 30, 240, 219)):
        layer = QPixmap(window.size())
        layer.fill(Qt.transparent)
        painter = QPainter(layer)
        painted = paint_cd_case(painter, window, rect, source, 'depth-test')
        painter.end()
        offset = control_offset(window, rect, depth)
        assert painted.size() == rect.size()
        assert painted.top() == rect.top() - depth
        assert painted.left() == rect.left() - offset.x()
        if depth:
            image = layer.toImage()
            x = rect.right() - 2 if offset.x() > 0 else rect.left() + .8
            y = rect.center().y()
            assert image.pixelColor(round(x), round(y)).alpha() == 255, (thickness, rect)
            x = rect.left() + 90 * rect.width() / 180
            bottom = rect.bottom() - 1
            for y in range(round(bottom - depth + 3), round(bottom)):
                assert image.pixelColor(round(x), y).alpha() == 255
baseline = {}
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    for angle in (-25, 0, 25):
        images = []
        for shadow in (False, True, None):
            layer = QPixmap(512, 512)
            layer.fill(Qt.transparent)
            painter = QPainter(layer)
            options = {} if shadow is None else {'shadow': shadow}
            paint_cd_case(painter, window, QRectF(100, 100, 240, 219), source, 'depth-test', angle, **options)
            painter.end()
            image = layer.toImage().convertToFormat(QImage.Format_RGBA8888)
            images.append(Image.frombytes('RGBA', (512, 512), image.constBits().tobytes()))
        assert images[1].tobytes() == images[2].tobytes()
        before, after = (image.getchannel('A').getbbox() for image in images[:2])
        if CASE_SHADOW_ENABLED:
            assert after[0] <= before[0], (thickness, angle, before, after)
            assert after[3] > before[3], (thickness, angle, before, after)
        else:
            assert images[0].tobytes() == images[1].tobytes()
        pixels = tuple(image.tobytes() for image in images)
        if thickness == 0:
            baseline[angle] = pixels
        assert pixels == baseline[angle]
for width in (180, 328, 640):
    for left in (20, 700):
        layer = QPixmap(1500, 800)
        layer.fill(Qt.transparent)
        painter = QPainter(layer)
        rect = QRectF(left, 30, width, width * 525 / 601)
        painted = paint_cd_case(painter, window, rect, source, shadow=False)
        painter.end()
        image = layer.toImage()
        x = round(painted.left() + painted.width() * .6)
        y = round(painted.center().y())
        vertical = [image.pixelColor(x, row) for row in range(image.height())]
        horizontal = [image.pixelColor(column, y) for column in range(image.width())]
        borders = []
        for line in (vertical, horizontal):
            threshold = min(QColor(CASE_COLOR).darker(112).getRgb()[:3])
            frame = [index for index, color in enumerate(line)
                     if color.alpha() > 128 and min(color.red(), color.green(), color.blue()) > threshold]
            paper = [index for index, color in enumerate(line)
                     if color.alpha() > 128 and min(color.red(), color.green(), color.blue()) > 200]
            if line is vertical:
                borders.extend((paper[0] - frame[0], frame[-1] - paper[-1]))
            else:
                borders.append(frame[-1] - paper[-1])
        assert max(borders) - min(borders) <= 1, (width, left, borders)
rect = QRectF(640, 30, 240, 240 * 525 / 601)
layer = QPixmap(3600, 1200)
layer.fill(Qt.transparent)
painter = QPainter(layer)
painter.scale(4, 4)
painted = paint_cd_case(painter, window, rect, source, shadow=False)
painter.end()
image = layer.toImage()
offset = control_offset(window, rect, CASE_DEPTH)
sleeve = sleeve_rect(painted)
x = painted.left() + .4 * rect.width() / CASE_WIDTH + offset.x() / 2
for edge, direction in ((sleeve.top(), 1), (sleeve.bottom(), -1)):
    y = edge + offset.y() / 2
    light = image.pixelColor(round(x * 4), round((y - direction * .75) * 4))
    dark = image.pixelColor(round(x * 4), round((y + direction * .75) * 4))
    assert light.alpha() == 255 and min(light.red(), light.green(), light.blue()) > 110
    assert dark.alpha() == 255 and max(dark.red(), dark.green(), dark.blue()) < 100
print('PASS: raised edges align at both spine joins, with equal front borders across sizes')
