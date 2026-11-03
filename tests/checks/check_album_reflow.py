"""Centered rows and continuous native item geometry while resizing/scaling."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListView, QListWidgetItem
from album_grid import AlbumGrid

app = QApplication([])
grid = AlbumGrid()
grid.setViewMode(QListView.IconMode)
grid.setMovement(QListView.Free)
grid.setResizeMode(QListView.Fixed)
grid.setIconSize(QSize(200, 180))
grid.setGridSize(QSize(220, 200))
pixmap = QPixmap(200, 180)
pixmap.fill(QColor('#456b85'))
for row in range(11):
    item = QListWidgetItem(QIcon(pixmap), '')
    item.setData(Qt.UserRole, row)
    grid.addItem(item)
grid.resize(830, 610)
grid.show()
QTest.qWait(40)
grid.doItemsLayout()
grid.reflow_animation.setCurrentTime(260)

def centered():
    rows = {}
    for index in range(grid.count()):
        rect = grid.visualItemRect(grid.item(index))
        rows.setdefault(rect.y(), []).append(rect)
    for cells in rows.values():
        center = (min(cell.left() for cell in cells) + max(cell.right() for cell in cells) + 1) / 2
        assert abs(center - grid.viewport().width() / 2) <= 1.5, (center, grid.viewport().width())

centered()
before = grid.visualItemRect(grid.item(3)).center()
grid.resize(1050, 610)
app.processEvents()
grid.reflow_animation.pause()
assert grid._reflow_targets
start = grid.visualItemRect(grid.item(3)).center()
assert abs(start.x() - before.x()) <= 2 and abs(start.y() - before.y()) <= 2, (start, before)
grid.reflow_animation.setCurrentTime(130)
middle = grid.visualItemRect(grid.item(3)).center()
grid.reflow_animation.setCurrentTime(260)
end = grid.visualItemRect(grid.item(3)).center()
assert middle != start and middle != end
assert min(start.y(), end.y()) <= middle.y() <= max(start.y(), end.y())
centered()
old_size = grid.display_icon_size()
grid.set_album_scale(125)
grid.reflow_animation.pause()
assert grid.display_icon_size() == old_size
grid.reflow_animation.setCurrentTime(130)
assert old_size.width() < grid.display_icon_size().width() < grid.iconSize().width()
grid.reflow_animation.setCurrentTime(260)
centered()
assert [grid.item(row).data(Qt.UserRole) for row in range(11)] == list(range(11))
rect = grid.visualItemRect(grid.item(0))
QTest.mouseClick(grid.viewport(), Qt.LeftButton, pos=rect.center())
assert grid.currentRow() == 0
grid.close()

# Large folders keep their scroll range and layout steady at the bottom.
grid.clear()
for row in range(500):
    grid.addItem(QListWidgetItem(QIcon(pixmap), ''))
grid.show()
QTest.qWait(40)
grid.finish_reflow()
bar = grid.verticalScrollBar()
maximum = bar.maximum()
last = grid.model().index(499, 0)
grid.lifts[499] = 1.0
grid.tilts[499] = 12.0
centers = []
for value in range(max(0, maximum - 50), maximum + 1):
    bar.setValue(value)
    app.processEvents()
    cell = grid.visualRect(last)
    centers.append(grid.case_geometry(cell, 499)[0].center().y())
    assert bar.maximum() == maximum
    assert not grid._reflow_targets
assert all(abs((b - a) + 1) < .001 for a, b in zip(centers, centers[1:])), 'Bottom row moved differently from its grid cells'

# Narrow windows and interrupted reflows fit without horizontal panning.
for width in (930, 520, 260, 780, 340):
    grid.resize(width, 610)
    app.processEvents()
    assert not grid.horizontalScrollBar().isVisible()
    assert grid.horizontalScrollBar().value() == 0
    grid.reflow_animation.setCurrentTime(260)
    app.processEvents()
    centered()
    for row in (0, grid.count() - 1):
        cell = grid.visualItemRect(grid.item(row))
        assert cell.left() >= 0 and cell.right() < grid.viewport().width(), (width, cell)
        rect, _ = grid.case_geometry(cell, row)
        assert rect.width() <= grid.viewport().width()
grid.close()
print('PASS: every row centered, continuous resize/scale animation, unchanged order and correct click targets')
