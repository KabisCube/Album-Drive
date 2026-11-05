from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QImage, QPainter, QRawFont
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QTableWidget, QTableWidgetItem

from app_paths import ASSETS_DIR
from main import load_app_font
from font_support import configure_font_rendering
from open_case import PLAYING_ROLE, TrackNumberDelegate


app = QApplication([])
load_app_font()
assert app.font().styleStrategy() & QFont.PreferAntialias
assert app.font().hintingPreference() == QFont.PreferNoHinting
raw = QRawFont(str(ASSETS_DIR / 'fonts' / 'AlbumRound-Bold.ttf'), 16)
assert raw.isValid() and raw.familyName() == 'Album Round'
assert all(raw.fontTable(tag) for tag in ('fpgm', 'prep', 'cvt ', 'gasp'))
assert all(raw.supportsCharacter(ord(char)) for char in '0123456789SherpaÅÄÖåäö')
for char in 'haT':
    outline = raw.pathForGlyph(raw.glyphIndexesForString(char)[0])
    assert any(outline.elementAt(index).isCurveTo() for index in range(outline.elementCount()))

table = QTableWidget(1, 1)
table.setProperty('paperBackgroundColor', '#ffffff')
table.setProperty('paperForegroundColor', '#000000')
delegate = TrackNumberDelegate(table)
option = QStyleOptionViewItem()
option.rect = QRect(0, 0, 54, 38)
font = QFont('Album Round')
font.setBold(True)
configure_font_rendering(font)
for ratio in (1, 1.5, 2):
    for size in (12, 16, 32, 64):
        font.setPixelSize(size)
        option.font = font
        for number in ('1', '9', '10', '99', '123'):
            table.setItem(0, 0, QTableWidgetItem(number))
            image = QImage(round(72 * ratio), round(54 * ratio), QImage.Format.Format_RGB32)
            image.setDevicePixelRatio(ratio)
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            delegate.paint(painter, option, table.model().index(0, 0))
            painter.end()
            pixels = [(x / ratio, y / ratio) for y in range(image.height()) for x in range(image.width())
                      if image.pixelColor(x, y).red() < 180]
            assert pixels, (size, number, ratio)
            assert min(x for x, y in pixels) >= 10, (size, number, ratio)
            assert max(x for x, y in pixels) <= option.rect.width() - 9, (size, number, ratio)
            assert min(y for x, y in pixels) >= 1, (size, number, ratio)
            assert max(y for x, y in pixels) <= option.rect.height() - 2, (size, number, ratio)

table.item(0, 0).setData(PLAYING_ROLE, True)
option.state |= QStyle.StateFlag.State_Selected
image = QImage(72, 54, QImage.Format.Format_RGB32)
image.fill(Qt.GlobalColor.white)
painter = QPainter(image)
delegate.paint(painter, option, table.model().index(0, 0))
painter.end()
output = Path('build/previews/track-number-rendering.png')
output.parent.mkdir(parents=True, exist_ok=True)
image.save(str(output))

sample = QTableWidget(1, 1)
sample.setFont(app.font())
sample.horizontalHeader().hide()
sample.verticalHeader().hide()
sample.setShowGrid(False)
sample.setStyleSheet('QTableWidget { background: white; color: black; border: none; font-size: 16px; }')
sample.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
sample.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
sample.setColumnWidth(0, 650)
sample.setRowHeight(0, 46)
sample.resize(660, 48)
sample.setItem(0, 0, QTableWidgetItem('Sherpa   Tohogd   Tamebsz   Ababa Hotel  0123456789'))
sample.ensurePolished()
app.processEvents()
shot = sample.grab().toImage()
shades = {shot.pixelColor(x, y).red() for y in range(shot.height()) for x in range(shot.width())}
assert len([shade for shade in shades if 0 < shade < 255]) >= 32, shades
assert sample.font().hintingPreference() == QFont.PreferNoHinting
shot.save('build/previews/track-text-antialiasing.png')

print('PASS: smooth table text, font curves and hint data, number fitting at 100/150/200% scaling, selection and playback rendering')
