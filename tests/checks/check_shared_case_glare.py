import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from case_shell import paint_cd_case
from case_finish import sleeve_rect
from main import NowPlayingCover, PlayerWindow, cd_case_pixmap
from library import Album
from open_case import CaseFront


def pixels(image):
    return image.convertToFormat(QImage.Format_RGBA8888).constBits().tobytes()


app = QApplication([])
scene = QWidget()
scene.resize(1000, 720)
scene.setStyleSheet('background: #393939;')
viewport = QWidget(scene)
viewport.setGeometry(100, 80, 700, 560)
front = CaseFront(scene)
front.lighting_source = viewport
front.sheen_key = 'shared-glare'
artwork = BytesIO()
Image.new('RGB', (64, 64), '#28445b').save(artwork, format='PNG')
front.pixmap = cd_case_pixmap(artwork.getvalue(), '', case_key=front.sheen_key)
scene.show()
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    for geometry in (QRect(210, 150, 244, 224), QRect(380, 240, 360, 330)):
        front.setGeometry(geometry)
        front.raise_()
        app.processEvents()
        target = front.image_rect()
        origin = viewport.mapFromGlobal(front.mapToGlobal(QPoint()))
        reference = QPixmap(viewport.size())
        reference.fill(QColor('#393939'))
        painter = QPainter(reference)
        painted = paint_cd_case(painter, viewport, target.translated(origin), front.pixmap,
                                front.sheen_key, visible=QRectF(viewport.rect()), shadow=True)
        painter.end()
        expected = reference.toImage().copy(QRect(origin, front.size()))
        actual = front.grab().toImage()
        sleeve = sleeve_rect(painted.translated(-origin)).adjusted(2, 2, -2, -2).toAlignedRect().intersected(front.rect())
        assert pixels(actual.copy(sleeve)) == pixels(expected.copy(sleeve)), (thickness, geometry)
        front.lighting_source = None
        assert pixels(front.grab().toImage().copy(sleeve)) != pixels(expected.copy(sleeve))
        front.lighting_source = viewport
front.hide()
cover = NowPlayingCover()
cover.setParent(scene)
cover.lighting_source = viewport
cover.sheen_key = front.sheen_key
controller = SimpleNamespace(cover=cover, artist_handwriting=lambda folder: None,
                             now_playing=SimpleNamespace(reveal=lambda expanded: None))
album = Album(Path(front.sheen_key), '', '', [], artwork.getvalue())
PlayerWindow.update_now_playing_cover(controller, album)
assert cover.pixmap().toImage() == front.pixmap.toImage()
cover.setGeometry(160, 120, 244, 224)
cover.show()
app.processEvents()
origin = viewport.mapFromGlobal(cover.mapToGlobal(QPoint()))
reference = QPixmap(viewport.size())
reference.fill(QColor('#393939'))
painter = QPainter(reference)
painted = paint_cd_case(painter, viewport, cover.image_rect().translated(origin), cover.pixmap(),
                        cover.sheen_key, visible=QRectF(viewport.rect()), shadow=True)
painter.end()
sleeve = sleeve_rect(painted.translated(-origin)).adjusted(2, 2, -2, -2).toAlignedRect().intersected(cover.rect())
expected = reference.toImage().copy(QRect(origin, cover.size()))
assert pixels(cover.grab().toImage().copy(sleeve)) == pixels(expected.copy(sleeve))
cover.lighting_source = None
assert pixels(cover.grab().toImage().copy(sleeve)) != pixels(expected.copy(sleeve))
scene.close()
print('PASS: Now Playing glare matches the album viewport pixel for pixel')
print('PASS: track-list glare matches the album viewport pixel for pixel across positions, sizes and thicknesses')
