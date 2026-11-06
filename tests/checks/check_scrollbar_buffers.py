import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollBar, QStyle, QStyleOptionSlider
from live_scrollbars import install_live_scrollbars
from themes import CONTROL_HEADROOM, chunky_style, control_face, text_style


app = QApplication([])
app.setStyle('Fusion')
app.setProperty('themeBackground', '#3b2422')
app.setProperty('themeAccent', '#a99b3e')
app.setProperty('cornerRoundness', 0)
app.setStyleSheet(chunky_style('', background='#3b2422', accent='#a99b3e') + text_style())
install_live_scrollbars(app)
for orientation in (Qt.Vertical, Qt.Horizontal):
    bar = QScrollBar(orientation)
    bar.setRange(0, 100)
    bar.setPageStep(20)
    bar.resize(60, 500) if orientation == Qt.Vertical else bar.resize(500, 60)
    bar.show()
    size = bar.size()
    bounds = []
    for thickness in (0, 100, 300):
        app.setProperty('uiThickness', thickness)
        for value in (0, 50, 100):
            bar.setValue(value)
            QTest.qWait(10)
            option = QStyleOptionSlider()
            bar.initStyleOption(option)
            handle = bar.style().subControlRect(QStyle.CC_ScrollBar, option, QStyle.SC_ScrollBarSlider, bar)
            knob = QRectF(handle).adjusted(0, 0, 0, -CONTROL_HEADROOM)
            face = control_face(knob, widget=bar)
            image = bar.grab().toImage()
            surface = QColor('#3b2422')
            assert all(image.pixelColor(x, image.height() - 1) == surface for x in range(image.width()))
            assert all(image.pixelColor(x, 0) == surface for x in range(image.width()))
            assert bar.size() == size
            if value == 50:
                x = round(face.right() - 3) if orientation == Qt.Vertical else round(face.center().x())
                colors = ('#a99b3e', QColor('#a99b3e').darker(125).name())
                pixels = [y for y in range(image.height()) if image.pixelColor(x, y).name() in colors]
                bounds.append((min(pixels), max(pixels)))
            if orientation == Qt.Vertical and value == 0:
                assert image.pixelColor(round(face.center().x()), round(face.top()) - 2) == surface
                assert image.pixelColor(face.center().toPoint()).name() == '#a99b3e'
    assert bounds[0][0] > bounds[1][0] > bounds[2][0], bounds
    assert len({bottom for top, bottom in bounds}) == 1, bounds
    bar.close()
print('PASS: scrollbar knobs and shadows fit both orientations with clear end buffers and reachable rail ends')
