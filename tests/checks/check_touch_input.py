import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidget, QScrollArea, QSlider, QVBoxLayout, QWidget
from touch_input import LONG_PRESS_MS, add_touch

app = QApplication([])
device = QTest.createTouchDevice()


def touch(widget, *steps):
    for step in steps:
        sequence = QTest.touchEvent(widget.window(), device)
        for action, finger, point in step:
            getattr(sequence, action)(finger, widget.mapTo(widget.window(), point), widget.window())
        sequence.commit()
        app.processEvents()


def swipe(widget, start, end):
    points = [start + (end - start) * (step / 8) for step in range(1, 9)]
    touch(widget, [('press', 0, start)])
    for point in points:
        QTest.qWait(16)
        touch(widget, [('move', 0, point)])
    touch(widget, [('release', 0, end)])


rows = QListWidget()
rows.addItems(f'Row {number}' for number in range(200))
rows.resize(320, 480)
clicked, menus = [], []
rows.itemClicked.connect(lambda item: clicked.append(item.text()))
rows.setContextMenuPolicy(Qt.CustomContextMenu)
rows.customContextMenuRequested.connect(menus.append)
scales, pinch_ended = [], []
add_touch(rows.viewport(), scrolls=True, on_pinch=lambda scale, started: scales.append((round(scale, 2), started)),
          on_pinch_end=lambda: pinch_ended.append(True))
rows.show()
QTest.qWait(50)
viewport = rows.viewport()

swipe(viewport, QPoint(160, 400), QPoint(160, 100))
QTest.qWait(400)
assert rows.verticalScrollBar().value() > 0, 'a swipe must scroll'
assert not clicked and not rows.selectedItems(), ('a swipe must not click or select', clicked, rows.currentRow(), rows.selectedItems())

viewport.touch_gestures.scroller.stop()
rows.verticalScrollBar().setValue(0)
touch(viewport, [('press', 0, QPoint(100, 40))], [('release', 0, QPoint(100, 40))])
assert len(clicked) == 1 and rows.selectedItems(), clicked

clicked.clear()
touch(viewport, [('press', 0, QPoint(100, 40))])
QTest.qWait(LONG_PRESS_MS + 80)
assert len(menus) == 1 and viewport.rect().contains(menus[0])
touch(viewport, [('release', 0, QPoint(100, 40))])
assert not clicked, 'lifting after a long press must not click'

touch(viewport, [('press', 0, QPoint(100, 100)), ('press', 1, QPoint(200, 100))],
      [('move', 0, QPoint(50, 100)), ('move', 1, QPoint(250, 100))],
      [('move', 0, QPoint(0, 100)), ('move', 1, QPoint(300, 100))],
      [('release', 0, QPoint(0, 100)), ('release', 1, QPoint(300, 100))])
assert scales[0] == (1.0, True) and scales[-1][0] >= 1.5 and pinch_ended == [True], scales
assert not clicked

page = QWidget()
layout = QVBoxLayout(page)
slider = QSlider(Qt.Horizontal)
slider.setRange(0, 100)
slider.setMinimumHeight(48)
layout.addSpacing(300)
layout.addWidget(slider)
layout.addSpacing(1200)
area = QScrollArea()
area.setWidgetResizable(True)
area.setWidget(page)
area.resize(320, 480)
add_touch(area.viewport(), scrolls=True)
area.show()
QTest.qWait(50)
center = slider.mapTo(area.viewport(), slider.rect().center())
swipe(area.viewport(), center, center + QPoint(0, -200))
QTest.qWait(300)
assert slider.value() == 0 and area.verticalScrollBar().value() > 0, ('vertical drags on a slider scroll the page', slider.value(), area.verticalScrollBar().value())
area.viewport().touch_gestures.scroller.stop()
area.verticalScrollBar().setValue(0)
QTest.qWait(50)
center = slider.mapTo(area.viewport(), slider.rect().center())
swipe(area.viewport(), QPoint(20, center.y()), QPoint(280, center.y()))
assert slider.value() > 50, 'horizontal drags on a slider move it'
assert area.verticalScrollBar().value() == 0

panel = QWidget()
panel.resize(320, 300)
child = QWidget(panel)
child.setGeometry(0, 0, 320, 300)
moved, ended = [], []
add_touch(panel, on_drag=moved.append, on_drag_end=ended.append)
panel.show()
QTest.qWait(50)
swipe(panel, QPoint(160, 250), QPoint(160, 50))
assert sum(moved) < -150 and len(ended) == 1, (moved, ended)

print('PASS: swipes only scroll, taps click once, long press opens menus, pinch reports scale, sliders and drag surfaces follow direction')
