import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel
from overflow_controls import OverflowControls
from themes import ThemedButton


app = QApplication([])
app.setProperty('buttonSoundVolume', 0)
header = OverflowControls(QLabel('24 albums'))
buttons = []
for label in ('Album size', 'Sort albums', 'Save theme', 'Refresh', 'Settings'):
    button = ThemedButton(label)
    button.setFixedSize(140, 70)
    header.controls.addWidget(button)
    buttons.append(button)
header.show()
app.processEvents()


def settle():
    while header.pager.spring.moving or header.scroll_left.animating or header.scroll_right.animating:
        QTest.qWait(16)
    viewport = header.viewport.rect()
    shown = 0
    for button in buttons:
        if button.isHidden():
            continue
        rect = button.geometry().translated(header.content.pos())
        assert viewport.contains(rect) or not viewport.intersects(rect), (button.text(), rect, viewport)
        shown += viewport.contains(rect)
    assert shown >= 1


natural = header.controls.sizeHint().width()
for width in (natural + 200, natural + 1, natural - 1, 300):
    header.resize(width, 80)
    app.processEvents()
    header.refresh()
    assert header.count.isVisible() == (width >= natural + header.count.sizeHint().width() + header.controls.spacing())
    assert header.scroll_right.isVisible() == (width < natural)
    assert not header.scroll_left.isVisible()
    for first, second in zip(buttons, buttons[1:]):
        assert first.geometry().right() < second.geometry().left()
    if width < natural:
        settle()
        QTest.mouseClick(header.scroll_right, Qt.LeftButton)
        assert header.scroll_offset > 0
        settle()
        for _ in range(20):
            header.scroll(1)
            settle()
        assert header.scroll_offset == header.maximum_scroll
        assert not header.scroll_right.isVisible()
        assert header.scroll_left.isVisible()
        header.setFocus(Qt.OtherFocusReason)
        buttons[0].setFocus(Qt.TabFocusReason)
        app.processEvents()
        assert header.scroll_offset == 0
        buttons[-1].setFocus(Qt.TabFocusReason)
        app.processEvents()
        assert header.scroll_offset == header.maximum_scroll
        header.scroll_offset = 0
        header.refresh()
header.resize(natural + 200, 80)
app.processEvents()
header.refresh()
settle()
header.resize(natural - 160, 80)
app.processEvents()
header.refresh()
from scale_ghost import ScaleGhost
ghosts = header.findChildren(ScaleGhost)
assert ghosts and all(0 < ghost.spring.value <= 1 for ghost in ghosts)
shown_rects = [button.geometry().translated(header.content.pos() + header.viewport.pos()) for button in header.shown_items()]
assert not any(ghost.geometry().intersects(rect) for ghost in ghosts for rect in shown_rects), ([ghost.geometry() for ghost in ghosts], shown_rects)
assert header.scroll_right.isVisible() and header.scroll_right.grow.value < 1
peak = 0
while header.scroll_right.animating:
    peak = max(peak, header.scroll_right.grow.value)
    QTest.qWait(10)
assert 1 < peak < 1.2, peak
QTest.qWait(100)
assert not header.findChildren(ScaleGhost)
settle()
QTest.qWait(600)
previous = {button: button.geometry().translated(header.content.pos() + header.viewport.pos()) for button in header.shown_items()}
window = header.viewport.geometry()
header.scroll(1)
ghosts = header.findChildren(ScaleGhost)
assert ghosts
left = [button for button in previous if button not in header.shown_items()]
assert left
sizes = sorted((ghost.width(), ghost.height()) for ghost in ghosts)
assert all((rect.width(), rect.height()) in sizes for rect in (previous[button].intersected(window) for button in left)), sizes
spots = {ghost.geometry().getRect() for ghost in ghosts}
assert all(previous[button].intersected(window).getRect() in spots for button in left), (spots, left)
visible_buttons = [button.geometry().translated(header.content.pos() + header.viewport.pos()) for button in header.shown_items()]
settle()
QTest.qWait(600)
header.resize(300, 80)
app.processEvents()
header.refresh()
settle()
header.scroll(1)
settle()
before = header.pager.start
header.set_pinned(True)
settle()
assert not header.scroll_left.isVisible() and not header.scroll_right.isVisible()
last = buttons[-1].geometry().translated(header.content.pos()).translated(header.viewport.pos())
assert last.right() == header.width() - 1, (last, header.width())
assert header.viewport.rect().contains(buttons[-1].geometry().translated(header.content.pos()))
header.scroll(-1)
assert header.pager.end == len(buttons)
for width in (260, 200, 420, 240):
    header.resize(width, 80)
    app.processEvents()
    header.refresh()
    settle()
    last = buttons[-1].geometry().translated(header.content.pos() + header.viewport.pos())
    assert header.rect().contains(last), (width, last)
    assert header.pager.end == len(buttons) and not header.scroll_left.isVisible() and not header.scroll_right.isVisible()
header.resize(300, 80)
app.processEvents()
header.refresh()
settle()
header.set_pinned(False)
settle()
assert header.pager.start == before
assert header.scroll_left.isVisible()
header.resize(natural + 200, 80)
app.processEvents()
header.refresh()
assert header.count.isVisible()
assert header.maximum_scroll == 0
assert not header.scroll_left.isVisible() and not header.scroll_right.isVisible()
buttons[-1].hide()
app.processEvents()
header.refresh()
assert header.content.width() < natural
header.close()
print('PASS: count hides before overflow, controls never overlap, arrows and keyboard reach every control, and resizing restores the count')
