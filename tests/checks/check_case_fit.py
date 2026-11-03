import os
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QListView, QListWidgetItem, QWidget

from album_grid import AlbumGrid
from case_shell import paint_cd_case
from main import NowPlayingCover, cd_case_pixmap
from open_case import CaseFront


app = QApplication([])
scene = QWidget()
scene.resize(1600, 1100)
scene.show()
source = cd_case_pixmap(b'', '', tray_color='#a7671f')


def assert_bounds(layer, width, height, ratio=1, vertical=(True, True)):
    image = layer.toImage().convertToFormat(QImage.Format_RGBA8888)
    pixels = Image.frombytes('RGBA', (image.width(), image.height()), image.constBits().tobytes())
    left, top, right, bottom = pixels.getchannel('A').getbbox()
    padding = 32 * ratio
    assert left >= padding and (not vertical[0] or top >= padding), (left, top, width, height, ratio)
    assert right <= padding + width * ratio and (not vertical[1] or bottom <= padding + height * ratio), (
        right, bottom, width, height, ratio)


def assert_fits(widget, target, angle=0, ratio=1, vertical=(True, True)):
    layer = QPixmap((widget.width() + 64) * ratio, (widget.height() + 64) * ratio)
    layer.setDevicePixelRatio(ratio)
    layer.fill(Qt.transparent)
    painter = QPainter(layer)
    painter.translate(32, 32)
    paint_cd_case(painter, widget, target, source, angle=angle)
    painter.end()
    assert_bounds(layer, widget.width(), widget.height(), ratio, vertical)


for cls in (NowPlayingCover, CaseFront):
    widget = cls() if cls is NowPlayingCover else cls(scene)
    widget.setParent(scene)
    if cls is NowPlayingCover:
        widget.setPixmap(source)
    else:
        widget.pixmap = source
    widget.show()
    for width in (64, 96, 180, 328, 640):
        for left in (20, 900):
            widget.setGeometry(left, 20, width, round(width * 525 / 601))
            app.processEvents()
            for ratio in (1, 2):
                assert_fits(widget, widget.image_rect(), ratio=ratio)
    widget.hide()

grid = AlbumGrid()
grid.setParent(scene)
grid.setViewMode(QListView.IconMode)
grid.setMovement(QListView.Free)
grid.setResizeMode(QListView.Fixed)
grid.icon_provider = lambda row: source
for row in range(18):
    grid.addItem(QListWidgetItem(QIcon(source), ''))
grid.show()
for width in (260, 520, 1000):
    grid.resize(width, 600)
    for scale in (50, 100, 150):
        grid.set_album_scale(scale)
        app.processEvents()
        grid.doItemsLayout()
        grid.finish_reflow()
        for row, scroll in ((0, 0), (17, grid.verticalScrollBar().maximum())):
            grid.verticalScrollBar().setValue(scroll)
            for angle in (-45, 0, 45):
                grid.lifts[row] = 1
                grid.tilts[row] = angle
                target, rotation = grid.case_geometry(grid.visualItemRect(grid.item(row)), row)
                assert_fits(grid.viewport(), target, rotation, vertical=(row == 0, row == 17))
            grid.lifts.clear()
            grid.tilts.clear()


def capture_drag(painter, widget, rect, pixmap, *args, **kwargs):
    device = painter.device()
    ratio = device.devicePixelRatioF()
    layer = QPixmap(round(device.width() + 64 * ratio), round(device.height() + 64 * ratio))
    layer.setDevicePixelRatio(ratio)
    layer.fill(Qt.transparent)
    reference = QPainter(layer)
    reference.translate(32, 32)
    reference.setWorldTransform(painter.worldTransform(), True)
    paint_cd_case(reference, widget, rect, pixmap, *args, **kwargs)
    reference.end()
    assert_bounds(layer, device.width() / ratio, device.height() / ratio, ratio)
    return paint_cd_case(painter, widget, rect, pixmap, *args, **kwargs)


grid.set_custom_order(True)
for row in (0, 17):
    grid.setCurrentRow(row)
    grid.scrollToItem(grid.item(row))
    app.processEvents()
    with patch('album_grid.QDrag') as drag, patch('album_grid.paint_cd_case', side_effect=capture_drag):
        grid.startDrag(Qt.MoveAction)
        assert drag.return_value.setPixmap.called
scene.close()
print('PASS: complete cases fit Now Playing, album views, grid edges, hover rotations and drag previews at multiple sizes and DPI scales')
