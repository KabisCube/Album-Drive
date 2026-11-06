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
        QTest.mouseClick(header.scroll_right, Qt.LeftButton)
        assert header.scroll_offset > 0
        for _ in range(20):
            header.scroll(1)
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
assert header.count.isVisible()
assert header.maximum_scroll == 0
assert not header.scroll_left.isVisible() and not header.scroll_right.isVisible()
buttons[-1].hide()
app.processEvents()
header.refresh()
assert header.content.width() < natural
header.close()
print('PASS: count hides before overflow, controls never overlap, arrows and keyboard reach every control, and resizing restores the count')
