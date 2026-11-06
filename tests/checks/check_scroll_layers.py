import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QListWidget, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QWidget
from scroll_shadows import install_scroll_shadows
from theme_settings import SettingsPage
from main import load_app_font
from open_case import TrackNumberDelegate, TrackTitleDelegate


app = QApplication([])
load_app_font()
app.setProperty('themeBackground', '#f4f4f4')
app.setProperty('textColor', '#ff00ff')
app.setStyleSheet('QWidget { background: #f4f4f4; color: #ff00ff; font-size: 20px; } QLabel { background: transparent; } QPushButton { background: #ff8000; border: none; }')
install_scroll_shadows(app)
areas = []
for page_type in (QWidget, SettingsPage):
    page = page_type()
    form = QFormLayout(page)
    form.setContentsMargins(30, 0, 30, 0)
    for index in range(40):
        form.addRow(QLabel('MMMMMMMM'), QPushButton('Button'))
    area = QScrollArea()
    area.setWidget(page)
    area.setWidgetResizable(True)
    areas.append(area)
items = QListWidget()
items.addItems(['MMMMMMMM'] * 40)
areas.append(items)
table = QTableWidget(40, 2)
table.setColumnWidth(0, 64)
table.setColumnWidth(1, 200)
table.setProperty('paperForegroundColor', '#ff00ff')
table.setItemDelegateForColumn(0, TrackNumberDelegate(table))
table.setItemDelegateForColumn(1, TrackTitleDelegate(table))
table.horizontalHeader().hide()
table.verticalHeader().hide()
table.setShowGrid(False)
for row in range(40):
    table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
    table.setItem(row, 1, QTableWidgetItem('MMMMMMMM'))
areas.append(table)
for area in areas:
    area.setFocusPolicy(Qt.NoFocus)
    area.resize(360, 240)
    area.show()
    app.processEvents()
    if hasattr(area, 'clearSelection'):
        area.clearSelection()
    area.verticalScrollBar().setValue(0)
    fades = area.scroll_edge_shadows.fades
    fades[0].reveal(True)
    for fade in fades:
        fade.animation.stop()
        fade.set_opacity(0)
    plain = area.viewport().grab().toImage()
    for fade in fades:
        fade.set_opacity(1)
    faded = area.viewport().grab().toImage()
    colors = {'#ff00ff'}
    if isinstance(area, QScrollArea):
        colors.add('#ff8000')
    for color in colors:
        pixels = [(x, y) for y in range(24) for x in range(plain.width())
                  if plain.pixelColor(x, y).name() == color]
        assert pixels, (type(area), color)
        assert all(faded.pixelColor(x, y) == plain.pixelColor(x, y) for x, y in pixels), (type(area), color)
    assert any(plain.pixelColor(x, y) != faded.pixelColor(x, y)
               for y in range(24) for x in range(plain.width())), type(area)
    if area is table:
        for column in range(2):
            start = table.columnViewportPosition(column)
            end = start + table.columnWidth(column)
            assert any(plain.pixelColor(x, y) != faded.pixelColor(x, y)
                       for y in range(24) for x in range(start, min(end, plain.width()))), column
    area.close()
print('PASS: halftone stays behind text and buttons in scroll pages, settings pages, lists and track tables')
