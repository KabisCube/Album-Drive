import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidgetItem

from album_grid import AlbumGrid


app = QApplication([])
app.setStyle('Fusion')
grid = AlbumGrid()
grid.setViewMode(AlbumGrid.IconMode)
grid.setMovement(AlbumGrid.Free)
grid.setResizeMode(AlbumGrid.Fixed)
grid.resize(720, 500)
source = QPixmap(540, 492)
source.fill(QColor('#cc7038'))
grid.icon_provider = lambda row: source
grid.set_album_scale(75)
for index in range(18):
    item = QListWidgetItem()
    item.setIcon(QIcon(source))
    item.setData(Qt.UserRole, index)
    grid.addItem(item)
grid.show()
QTest.qWait(30)
grid.finish_reflow()
bar = grid.verticalScrollBar()
top, bottom = grid.edge_fades
assert top.isHidden() and not bottom.isHidden()
for background in ('#393939', '#f4f4f4'):
    app.setProperty('themeBackground', background)
    grid.setStyleSheet(f'QListWidget {{ background: {background}; border: none; }}')
    grid.doItemsLayout()
    grid.finish_reflow()
    bar.setValue(110)
    grid.update_edge_fades()
    top.animation.pause()
    frames = []
    for fraction in (0, .25, .5, 1):
        top.animation.setCurrentTime(round(top.animation.duration() * fraction))
        frames.append(grid.grab().toImage())
    edge = top.geometry()
    samples = [x for x in range(edge.left(), edge.right() + 1)
               if frames[0].pixelColor(x, edge.top()).name() == background
               and frames[-1].pixelColor(x, edge.top()).name() != background]
    sample = min(samples, key=lambda x: frames[-1].pixelColor(x, edge.top()).lightness())
    shades = [frame.pixelColor(sample, edge.top()).lightness() for frame in frames]
    assert all(first >= second for first, second in zip(shades, shades[1:])), shades
    assert shades[0] > shades[2] > shades[3], shades
    for fade in grid.edge_fades:
        fade.animation.setCurrentTime(fade.animation.duration())
    app.processEvents()
    assert not top.isHidden() and not bottom.isHidden()
    positions = [fade.geometry() for fade in grid.edge_fades]
    for fade in grid.edge_fades:
        assert fade.testAttribute(Qt.WA_TransparentForMouseEvents)
        assert fade.width() == grid.viewport().width()
        fade.hide()
    plain = grid.grab().toImage()
    grid.update_edge_fades()
    for fade in grid.edge_fades:
        fade.animation.setCurrentTime(fade.animation.duration())
    faded = grid.grab().toImage()
    base = QColor(background)
    for fade in grid.edge_fades:
        edge = fade.geometry()
        y = edge.bottom() if fade.bottom else edge.top()
        changes = [x for x in range(edge.left(), edge.right() + 1)
                   if plain.pixelColor(x, y) != faded.pixelColor(x, y)]
        assert changes
        assert plain.pixelColor(edge.left(), y) == faded.pixelColor(edge.left(), y)
        assert any(plain.pixelColor(x, y) == base for x in changes)
        for x in changes:
            before = plain.pixelColor(x, y)
            after = faded.pixelColor(x, y)
            if before == base:
                assert after.lightnessF() < before.lightnessF()
    middle = grid.viewport().geometry().center().y()
    assert all(plain.pixelColor(x, middle) == faded.pixelColor(x, middle) for x in range(grid.width()))
    bar.setValue(140)
    assert [fade.geometry() for fade in grid.edge_fades] == positions
    if background == '#393939':
        grid.grab().save('build/debug/album-edge-fades.png')
    bar.setValue(bar.maximum())
    assert not top.isHidden() and bottom.isHidden()
    bar.setValue(0)
    assert top.isHidden() and not bottom.isHidden()
grid.clear()
app.processEvents()
assert all(fade.isHidden() for fade in grid.edge_fades)
grid.close()
print('PASS: subtle top/bottom album fades follow theme colors, stay fixed while scrolling, preserve the middle and do not intercept input')
