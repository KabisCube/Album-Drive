import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from case_shell import artwork_tray_color, shell_pixmap
from main import cd_case_pixmap
from library import cover_thumbnail
from test_case_trays import cover


app = QApplication([])
shell = shell_pixmap().toImage()
assert shell.size().width() == 601 and shell.size().height() == 525
assert shell.pixelColor(0, 0).alpha() == 0
for x, y in ((300, 5), (300, 520), (595, 260)):
    assert shell.pixelColor(x, y).alpha() == 255
assert shell_pixmap() is shell_pixmap()
sheet = QPixmap(1120, 260)
sheet.fill(QColor('#393939'))
painter = QPainter(sheet)
for index, accent in enumerate(('#808080', '#e02030', '#f0c020', '#3030ea')):
    artwork = cover('#a0a0a0', (((0, 0, 29, 99), accent),))
    selected = artwork_tray_color(artwork)
    case = cd_case_pixmap(artwork, '', case_key='colored-tray')
    image = case.toImage()
    plain = cd_case_pixmap(artwork, '', tray_color='').toImage()
    thumbnail = cd_case_pixmap(cover_thumbnail(artwork), '', tray_color=selected or '').toImage()
    for x, y in ((30, 260),):
        color = image.pixelColor(x, y)
        if index:
            assert selected
            assert abs(color.hueF() - QColor(selected).hueF()) < .025
            assert color.saturationF() > .5
            assert color.value() > 100
            assert color == thumbnail.pixelColor(x, y)
        else:
            assert selected is None
            assert color == plain.pixelColor(x, y)
    for x, y in ((300, 260), (300, 5), (300, 520), (82, 260), (595, 260)):
        assert image.pixelColor(x, y) == plain.pixelColor(x, y)
    if index:
        ribs = [image.pixelColor(x, 260).value() for x in range(10, 52)]
        assert max(ribs) - min(ribs) > 3
    painter.drawPixmap(QRectF(index * 280 + 10, 10, 260, 260 * 1050 / 1202),
                       case, QRectF(case.rect()))
painter.end()
sheet.save('build/colored-case-textures.png')
print('PASS: procedural shells preserve artwork, accent trays, ribs, neutral frames and transparent corners')
