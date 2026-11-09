"""Controls the layout hides shrink away; whole pages that switch do not."""
import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

app = QApplication([])

from scale_ghost import ScaleGhost
from themes import ChunkyCheckBox, ThemedButton, ThemedComboBox, ThemeSlider

window = QWidget()
layout = QVBoxLayout(window)
button = ThemedButton('Refresh')
combo = ThemedComboBox()
combo.addItems(['one', 'two'])
check = ChunkyCheckBox('Option')
slider = ThemeSlider()
slider.setOrientation(Qt.Horizontal)
row = QWidget()
row_layout = QHBoxLayout(row)
row_layout.addWidget(ThemedButton('In a row'))
pages = QStackedWidget()
first, second = QWidget(), QWidget()
QVBoxLayout(first).addWidget(ThemedButton('Page one'))
QVBoxLayout(second).addWidget(ThemedButton('Page two'))
pages.addWidget(first)
pages.addWidget(second)
for widget in (button, combo, check, slider, row, pages):
    layout.addWidget(widget)
window.resize(500, 700)
window.show()
QTest.qWait(50)


def ghosts():
    return window.findChildren(ScaleGhost)


def settle():
    QTest.qWait(900)
    app.processEvents()
    assert not ghosts()


for widget in (button, combo, check, slider, row):
    spot = widget.geometry()
    widget.hide()
    found = ghosts()
    assert len(found) == 1, (type(widget).__name__, len(found))
    assert found[0].size() == spot.size(), (type(widget).__name__, found[0].geometry(), spot)
    image = found[0].pixmap.toImage()
    corners = [image.pixelColor(x, y).alpha() for x, y in ((0, 0), (image.width() - 1, 0), (0, image.height() - 1), (image.width() - 1, image.height() - 1))]
    assert all(alpha == 0 for alpha in corners), (type(widget).__name__, corners)
    QTest.qWait(80)
    alive = ghosts()
    assert len(alive) == 1 and 0 < alive[0].spring.value < 1, (type(widget).__name__, len(alive))
    settle()
    widget.show()
    QTest.qWait(30)
    growing = ghosts()
    assert len(growing) == 1 and growing[0].spring.value < 1, (type(widget).__name__, len(growing))
    assert widget.graphicsEffect() is not None
    moved_to = widget.pos() + QPoint(37, 11)
    widget.move(moved_to)
    QTest.qWait(40)
    assert growing[0].geometry().topLeft() == widget.mapTo(window, QPoint()), (type(widget).__name__, growing[0].geometry(), widget.mapTo(window, QPoint()))
    settle()
    assert widget.graphicsEffect() is None, type(widget).__name__

pages.setCurrentIndex(1)
QTest.qWait(30)
assert not ghosts()
pages.setCurrentIndex(0)
QTest.qWait(30)
assert not ghosts()
window.hide()
assert not ghosts()
window.close()
print('PASS: hidden buttons, dropdowns, checkboxes, sliders and rows shrink away and spring back; page switches and closing windows do not')
