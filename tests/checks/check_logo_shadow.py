import os
from math import ceil

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication
from themes import LOGO_BACKGROUND_TRIM, LOGO_VERTICAL_OFFSET, ChunkyBrand, corner_radius, lettering_shadow, lettering_shadow_pixmap


app = QApplication([])
font = QFont()
font.setPixelSize(27)
for ratio in (1, 1.25, 2):
    for depth in (0, 4, 12):
        for x, y in ((20, 40), (20.375, 40.625)):
            cached = lettering_shadow_pixmap(font.toString(), 'Album Drive', depth, 320, 100, ratio, x, y)
            reference = QPixmap(ceil(320 * ratio), ceil(100 * ratio))
            reference.setDevicePixelRatio(ratio)
            reference.fill(Qt.transparent)
            painter = QPainter(reference)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillPath(lettering_shadow(font.toString(), 'Album Drive', depth).translated(x, y),
                             QColor(0, 0, 0, 65))
            painter.end()
            assert cached.toImage() == reference.toImage(), (ratio, depth, x, y)

brand = ChunkyBrand('Album Drive')
brand.setFont(font)
app.setProperty('uiThickness', 300)
brand.resize(320, brand.sizeHint().height())
brand.show()
app.processEvents()
brand.grab()
before = lettering_shadow_pixmap.cache_info()
for color in ('#203040', '#709080', '#d0b090'):
    app.setProperty('brandLineColor', color)
    app.setProperty('brandTextColor', color)
    brand.grab()
after = lettering_shadow_pixmap.cache_info()
assert after.misses == before.misses
assert after.hits >= before.hits + 3
brand.resize(360, brand.height())
brand.grab()
assert lettering_shadow_pixmap.cache_info().misses == after.misses + 1
app.setProperty('uiThickness', 0)
app.setProperty('brandLineColor', '#dddddd')
app.setProperty('brandTextColor', '#77dc12')
actual = brand.grab()
reference = QPixmap(actual.size())
reference.setDevicePixelRatio(actual.devicePixelRatioF())
reference.fill(brand.palette().window().color())
painter = QPainter(reference)
painter.setRenderHint(QPainter.Antialiasing)
painter.setPen(Qt.NoPen)
painter.setBrush(QColor('#dddddd'))
stripe = brand.background_rect()
radius = corner_radius(6, stripe.width(), stripe.height())
painter.drawRoundedRect(stripe, radius, radius)
path = QPainterPath()
path.addText(0, 0, brand.font(), brand.text())
position = QPointF(brand.width() / 2 - path.boundingRect().center().x(),
                  stripe.center().y() + LOGO_BACKGROUND_TRIM / 2 - path.boundingRect().center().y() + LOGO_VERTICAL_OFFSET)
painter.setBrush(QColor('#77dc12'))
painter.drawPath(path.translated(position))
painter.end()
assert actual.toImage() == reference.toImage(), 'Flat logo has an extra outline or text layer'
brand.close()
print('PASS: cached logo shadows match vector rendering, reuse color frames, refresh on resize and leave flat lettering free of outlines')
