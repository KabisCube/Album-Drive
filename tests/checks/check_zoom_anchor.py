"""Zooming the album list keeps the top visible row of albums in view."""
import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidgetItem

from album_grid import AlbumGrid

app = QApplication([])
grid = AlbumGrid()
placeholder = QPixmap(10, 10)
for index in range(120):
    item = QListWidgetItem(placeholder, '')
    item.setData(256, index)
    grid.addItem(item)
grid.resize(900, 600)
grid.show()
grid.set_album_scale(100)
QTest.qWait(50)
grid.setCurrentRow(0)
for start, scale in ((40, 60), (40, 140), (90, 50)):
    grid.set_album_scale(100)
    grid.doItemsLayout()
    grid.scrollToItem(grid.item(start))
    grid.verticalScrollBar().setValue(grid.verticalScrollBar().value() + 30)
    QTest.qWait(20)
    row, passed = grid.top_visible_anchor()
    grid.set_album_scale(scale)
    QTest.qWait(20)
    rect = grid.visualItemRect(grid.item(row))
    assert grid.top_visible_anchor()[0] == row or grid.verticalScrollBar().value() == grid.verticalScrollBar().maximum(), \
        (start, scale, row, grid.top_visible_anchor())
    assert rect.bottom() >= 0 and rect.top() < grid.viewport().height(), (start, scale, rect)
grid.close()
print('PASS: zooming in and out keeps the top visible row of albums in view')
