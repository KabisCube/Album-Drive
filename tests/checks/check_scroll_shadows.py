import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidget, QScrollArea, QTableWidget, QTreeView, QWidget
from album_grid import AlbumGrid
from scroll_shadows import install_scroll_shadows
from themes import ThemedComboBox


app = QApplication([])
app.setProperty('themeBackground', '#f4f4f4')
install_scroll_shadows(app)
areas = []
scroll = QScrollArea()
body = QWidget()
body.resize(480, 1200)
body.setStyleSheet('background: #f4f4f4;')
scroll.setWidget(body)
areas.append(scroll)
items = QListWidget()
items.addItems([f'Item {number}' for number in range(80)])
areas.append(items)
table = QTableWidget(80, 2)
table.setProperty('paperBackgroundColor', '#e7c977')
areas.append(table)
browser = QTreeView()
browser.setObjectName('fileBrowser')
model = QStandardItemModel(browser)
for number in range(80):
    model.appendRow(QStandardItem(f'Folder {number}'))
browser.setModel(model)
browser.setHeaderHidden(True)
areas.append(browser)
for area in areas:
    area.resize(360, 240)
    area.show()
    QTest.qWait(20)
    shadows = area.scroll_edge_shadows
    top, bottom = shadows.fades
    bar = area.verticalScrollBar()
    assert bar.maximum() > 0
    assert top.isHidden() and not bottom.isHidden()
    bar.setValue(bar.maximum() // 2)
    assert top.opacity == 0
    top.animation.pause()
    if area is scroll:
        shades = []
        for fraction in (0, .25, .5, 1):
            top.animation.setCurrentTime(round(top.animation.duration() * fraction))
            frame = area.grab().toImage()
            shades.append(frame.pixelColor(top.geometry().center().x(), top.geometry().top()).lightness())
        assert all(first > second for first, second in zip(shades, shades[1:])), shades
    top.animation.setCurrentTime(top.animation.duration() // 2)
    assert 0 < top.opacity < 1
    assert abs(top.opacity - .5) < .01
    intermediate = top.opacity
    bar.setValue(bar.value() + 1)
    assert top.opacity == intermediate
    top.animation.setCurrentTime(top.animation.duration())
    assert top.opacity == 1
    app.processEvents()
    assert not top.isHidden() and not bottom.isHidden()
    geometry = [fade.geometry() for fade in shadows.fades]
    for fade in shadows.fades:
        assert fade.testAttribute(Qt.WA_TransparentForMouseEvents)
        assert fade.width() == area.viewport().width()
        fade.grab()
        image = fade._image
        edge = image.height() - 1 if fade.bottom else 0
        assert image.pixelColor(0, edge).alpha() == 0
        assert image.pixelColor(image.width() - 1, edge).alpha() == 0
        assert image.pixelColor(image.width() // 2, edge).alpha() > 0
    if area is table:
        actual = top._image.pixelColor(top.width() // 2, 0)
        expected = QColor('#e7c977').darker(125)
        assert all(abs(a - b) <= 2 for a, b in zip(actual.getRgb()[:3], expected.getRgb()[:3]))
    bar.setValue(bar.value() + 1)
    assert [fade.geometry() for fade in shadows.fades] == geometry
    area.hide()
    assert top.opacity == 0
    area.show()
    assert top.opacity == 0
    assert top.animation.state() == top.animation.State.Running
    area.resize(420, 280)
    app.processEvents()
    assert top.width() == area.viewport().width()
    bar.setValue(bar.maximum())
    assert not top.isHidden() and bottom.isHidden()
    bar.setRange(0, 0)
    assert top.isHidden() and bottom.isHidden()
    assert top.opacity == 0 and bottom.opacity == 0
    area.close()
grid = AlbumGrid()
grid.setObjectName('albumGrid')
grid.show()
app.processEvents()
assert hasattr(browser, 'scroll_edge_shadows')
assert not hasattr(grid, 'scroll_edge_shadows')
choice = ThemedComboBox()
choice.addItems([f'Choice {number}' for number in range(80)])
choice.show()
choice.showPopup()
app.processEvents()
assert hasattr(choice.view(), 'scroll_edge_shadows')
assert choice.view().verticalScrollBar().maximum() > 0
assert not choice.view().scroll_edge_shadows.fades[1].isHidden()
choice.hidePopup()
choice.close()
browser.close()
grid.close()
print('PASS: matching shadows on scroll areas, lists, track tables, file browser and dropdowns; themed paper, side taper, fixed edges and scroll limits')
