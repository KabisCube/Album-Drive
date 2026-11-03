import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from case_geometry import CASE_WIDTH, CASE_HEIGHT, sleeve_rect
from case_shell import case_frame_color, paint_cd_case
from main import cd_case_pixmap


app = QApplication([])
widget = QWidget()
widget.resize(380, 340)
source = cd_case_pixmap(b'', '', case_key='theme-reflection')
original = source.toImage()
rect = QRectF(30, 30, 320, 320 * CASE_HEIGHT / CASE_WIDTH)


def render(background):
    app.setProperty('themeBackground', background)
    layer = QPixmap(widget.size())
    layer.fill(QColor(background))
    painter = QPainter(layer)
    painted = paint_cd_case(painter, widget, rect, source, 'theme-reflection')
    painter.end()
    return layer, sleeve_rect(painted).adjusted(5, 5, -5, -5).toAlignedRect()


samples = []
sheet = QPixmap(1140, 340)
sheet.fill(QColor('#393939'))
painter = QPainter(sheet)
for index, background in enumerate(('#703030', '#307030', '#303070')):
    layer, area = render(background)
    image = layer.toImage()
    pixels = [image.pixelColor(x, y) for x in range(area.left(), area.right(), 5)
              for y in range(area.top(), area.bottom(), 5)]
    samples.append(tuple(sum(getattr(pixel, channel)() for pixel in pixels) / len(pixels)
                         for channel in ('red', 'green', 'blue')))
    painter.drawPixmap(index * 380, 0, layer)
painter.end()
assert samples[0][0] > samples[2][0] + 1
assert samples[1][1] > samples[0][1] + 1
assert samples[2][2] > samples[1][2] + 1
first, _ = render('#703030')
render('#303070')
returned, _ = render('#703030')
assert first.toImage() == returned.toImage()
assert source.toImage() == original
frames = []
for background in ('#808080', '#606060', '#404040', '#202020'):
    app.setProperty('themeBackground', background)
    layer = QPixmap(widget.size())
    layer.fill(Qt.transparent)
    painter = QPainter(layer)
    painted = paint_cd_case(painter, widget, rect, source, shadow=False)
    painter.end()
    frame = layer.toImage().pixelColor(round(painted.center().x()), round(painted.top() + 2))
    assert frame == case_frame_color(), (background, frame.name(), case_frame_color().name())
    frames.append(frame.lightness())
assert frames[0] == 221
assert all(first > second for first, second in zip(frames, frames[1:])), frames
render('#808080')
assert case_frame_color().name() == '#dddddd'
assert source.toImage() == original
sheet.save('build/theme-case-reflections.png')
print('PASS: live reflections and fading case frames preserve source artwork and restore light themes')
