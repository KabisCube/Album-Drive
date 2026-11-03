"""Offscreen regression checks for hover clipping and stable album spacing."""

import os
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListView, QListWidgetItem

from album_grid import AlbumGrid


app = QApplication([])
grid = AlbumGrid()
grid.setViewMode(QListView.IconMode)
grid.setResizeMode(QListView.Adjust)
grid.setMovement(QListView.Static)
grid.setIconSize(QSize(200, 160))
grid.resize(700, 580)
pixmap = QPixmap(240, 192)
pixmap.fill(QColor('#fe0102'))
other = QPixmap(240, 192)
other.fill(QColor('#0102fe'))
for row in range(12):
    grid.addItem(QListWidgetItem(QIcon(pixmap if row == 3 else other), ''))
    grid.item(row).setData(Qt.UserRole, row)
grid.set_hover_options(0, 0, hover_lift=0)
grid.show()
QTest.qWait(40)
pitch = grid.row_pitch()
cells = [grid.visualItemRect(grid.item(row)) for row in range(12)]
grid.set_hover_options(360, 0, hover_lift=40)
QTest.qWait(40)
assert grid.hover_rotation == 45
for cleaning, limit in ((False, 45), (True, 90)):
    grid.set_cleaning(cleaning)
    grid.set_hover(-1)
    with patch('album_grid.random.uniform', return_value=0) as rotation:
        grid.set_hover(0)
        rotation.assert_called_once_with(-limit, limit)
    assert grid.hover_rotation == 45
grid.set_cleaning(False)
grid.set_hover(-1)
assert grid.row_pitch() == pitch
assert cells == [grid.visualItemRect(grid.item(row)) for row in range(12)]
grid.set_hover_options(0, 0, hover_lift=40)

# A middle-row case can draw above its own cell without getting cut off.
grid.set_hover(3)
QTest.qWait(220)
image = grid.viewport().grab().toImage()
cell = grid.visualItemRect(grid.item(3))
x = cell.center().x()
y = cell.top() - 20
assert image.pixelColor(x, y).name() == '#fe0102'
assert image.pixelColor(x, y - 30).name() != '#fe0102'
middle_artwork_rows = [row for row in range(image.height()) if image.pixelColor(x, row).name() == '#fe0102']
assert len(middle_artwork_rows) >= grid.iconSize().height() * .9

# The top case stops at the viewport edge, preserving its entire image.
grid.item(0).setIcon(QIcon(pixmap))
grid.item(3).setIcon(QIcon(other))
grid.set_hover(0)
QTest.qWait(220)
image = grid.viewport().grab().toImage()
x = grid.visualItemRect(grid.item(0)).center().x()
top_artwork_rows = [row for row in range(image.height()) if image.pixelColor(x, row).name() == '#fe0102']
assert abs(len(top_artwork_rows) - len(middle_artwork_rows)) <= 1
assert top_artwork_rows == list(range(top_artwork_rows[0], top_artwork_rows[-1] + 1))
assert 1 < top_artwork_rows[0] < grid.iconSize().height() * .1
assert image.pixelColor(x, 1).name() != '#fe0102'

# Enlargement and arbitrary rotations also stay within visible boundaries.
grid.set_hover_options(360, 20, hover_lift=40)
grid.set_cleaning(True)
grid.animate_tilt(0, 45)
QTest.qWait(220)
assert abs(grid.tilts[0] - 45) < .01
image = grid.viewport().grab().toImage()
assert any(image.pixelColor(x, y).name() == '#fe0102'
           for y in range(1, grid.iconSize().height() // 10) for x in range(image.width()))
assert all(image.pixelColor(x, 0).name() != '#fe0102' for x in range(image.width()))
assert grid.row_pitch() == pitch
grid.set_cleaning(False)
grid.set_hover_options(15, 20, hover_lift=40)
grid.set_hover(1)
QTest.qWait(220)
assert 1 in grid.tilts
grid.set_hover(-1)
QTest.qWait(220)
assert not grid.tilts and not grid.tilt_animations

# Opening an album suppresses only its artwork, keeping its grid slot intact.
cell = grid.visualItemRect(grid.item(0))
assert grid.viewport().grab().toImage().pixelColor(cell.center()).name() == '#fe0102'
grid.suppressed_album = 0
assert grid.viewport().grab().toImage().pixelColor(cell.center()).name() != '#fe0102'
assert grid.count() == 12 and grid.visualItemRect(grid.item(0)) == cell
grid.suppressed_album = None
assert grid.viewport().grab().toImage().pixelColor(cell.center()).name() == '#fe0102'
grid.close()
print('PASS: stable grid spacing, visible-edge protection, 45-degree tilt cap, doubled cleaning tilt and disabled cleaning')
