import os
from io import BytesIO

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from case_geometry import CASE_WIDTH, CASE_HEIGHT, sleeve_rect
from case_finish import paint_case_finish
from main import cd_case_pixmap


app = QApplication([])
assert sleeve_rect(QRectF(0, 0, 1202, 1050)) == QRectF(175, 23, 1004, 1004)
source = Image.new('RGB', (300, 100), '#e02020')
source.paste('#20b060', (100, 0, 200, 100))
source.paste('#2040e0', (200, 0, 300, 100))
data = BytesIO()
source.save(data, format='PNG')
plain = cd_case_pixmap(b'', '').toImage()
covered = cd_case_pixmap(data.getvalue(), '', tray_color='').toImage()
assert covered.width() / covered.height() == 1202 / 1050
for x in (89, 300, 588):
    for y in (13, 260, 512):
        assert covered.pixelColor(x, y).name() == '#20b060'
for x, y in ((30, 260), (65, 260), (595, 260), (300, 5), (300, 520)):
    assert covered.pixelColor(x, y) == plain.pixelColor(x, y)
assert cd_case_pixmap(b'invalid image', '').toImage() == plain
for width in (180, 328, 640):
    rect = QRectF(10, 10, width, width * CASE_HEIGHT / CASE_WIDTH)
    sleeve = sleeve_rect(rect)
    assert abs(sleeve.width() - sleeve.height()) < .0001
    assert abs(rect.right() - sleeve.right() - (sleeve.top() - rect.top())) < .0001
    assert abs(rect.bottom() - sleeve.bottom() - (sleeve.top() - rect.top())) < .0001
    layer = QPixmap(round(width + 20), round(rect.height() + 20))
    layer.fill(Qt.transparent)
    painter = QPainter(layer)
    paint_case_finish(painter, rect, 0, 'new-template')
    painter.end()
    finish = layer.toImage()
    assert finish.pixelColor(round(sleeve.center().x()), round(sleeve.center().y())).alpha() > 0
    assert finish.pixelColor(round(rect.left() + 5), round(rect.center().y())).alpha() == 0
covered.save('build/new-case-cover.png')
print('PASS: exact guide bounds, template proportions, centered artwork crop, preserved rim and fitted finish')
