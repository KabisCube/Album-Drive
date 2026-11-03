import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTabWidget, QToolButton, QWidget

from themes import BUTTON_SHADOW, CONTROL_HEADROOM, ChunkyTabBar, button_paint_rect, chunky_style, control_face, text_style, ui_depth
from main import load_app_font


app = QApplication([])
app.setStyle('Fusion')
load_app_font()
app.setProperty('playerTheme', 'chunky')
app.setProperty('cornerRoundness', 100)
app.setProperty('buttonSoundVolume', 0)
app.setStyleSheet(chunky_style('QWidget { background: #393939; }') + text_style())
tabs = QTabWidget()
bar = ChunkyTabBar(tabs)
tabs.setTabBar(bar)
for title in ('General', 'Style', 'Audio', 'File browser', 'Album list', 'Track list'):
    tabs.addTab(QWidget(), title)
tabs.resize(460, 220)
tabs.show()
app.processEvents()
def check_gutters():
    image = bar.grab().toImage()
    for button in (bar.scroll_left, bar.scroll_right):
        if not button.isVisible():
            continue
        outer = button_paint_rect(button).translated(0, (ui_depth() - CONTROL_HEADROOM) / 2)
        body = control_face(outer, widget=button).united(control_face(outer, pressed=True, widget=button))
        body = body.adjusted(-3, -1, 1, BUTTON_SHADOW + 1)
        for y in range(button.height()):
            for x in range(button.width()):
                if not body.contains(x, y):
                    assert image.pixelColor(button.x() + x, y).name() == '#393939', (button.accessibleName(), x, y)

assert bar.maximum_scroll() > 0
assert not bar.scroll_left.isVisible()
assert bar.scroll_right.isVisible()
assert not any(button.isVisible() for button in bar.findChildren(QToolButton))
native = bar.findChildren(QToolButton)
assert native
tabs.setUsesScrollButtons(True)
for button in native:
    button.show()
app.processEvents()
assert not bar.usesScrollButtons()
assert not any(button.isVisible() for button in native)
check_gutters()
selected = tabs.currentIndex()
previous = bar.scroll_offset
QTest.mouseClick(bar.scroll_right, Qt.LeftButton)
assert bar.scroll_offset > previous
assert tabs.currentIndex() == selected
assert bar.scroll_left.isVisible()
assert bar.scroll_right.isVisible()
image = bar.grab().toImage()
assert image.pixelColor(bar.scroll_button_width() - 1, bar.height() // 2).name() == '#393939'
assert image.pixelColor(bar.width() - bar.scroll_button_width(), bar.height() // 2).name() == '#393939'
for _ in range(30):
    if not bar.scroll_right.isVisible():
        break
    QTest.mouseClick(bar.scroll_right, Qt.LeftButton)
    check_gutters()
assert not bar.scroll_right.isVisible()
assert bar.scroll_left.isVisible()
assert bar.tab_viewport().contains(bar.tabRect(bar.count() - 1))
target = bar.count() - 1
QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(target).center())
assert tabs.currentIndex() == target
bar.setFocus()
for _ in range(bar.count() - 1):
    QTest.keyClick(bar, Qt.Key_Left)
    assert bar.tab_viewport().contains(bar.tabRect(bar.currentIndex()))
assert tabs.currentIndex() == 0
assert not bar.scroll_left.isVisible()
assert bar.scroll_right.isVisible()
for _ in range(30):
    if not bar.scroll_right.isVisible():
        break
    QTest.mouseClick(bar.scroll_right, Qt.LeftButton)
for _ in range(30):
    if not bar.scroll_left.isVisible():
        break
    QTest.mouseClick(bar.scroll_left, Qt.LeftButton)
    check_gutters()
assert bar.scroll_offset == 0
assert not bar.scroll_left.isVisible()
tabs.resize(2000, 220)
app.processEvents()
assert bar.maximum_scroll() == 0
assert not bar.scroll_left.isVisible() and not bar.scroll_right.isVisible()
tabs.resize(460, 220)
app.processEvents()
tabs.setCurrentIndex(bar.count() - 1)
assert bar.tab_viewport().contains(bar.tabRect(bar.currentIndex()))
assert not bar.scroll_right.isVisible()
tabs.grab().save('build/tab-scroll-preview.png')
tabs.close()
print('PASS: directional arrows, scroll without selection, mouse/keyboard access, edge visibility and resize')
