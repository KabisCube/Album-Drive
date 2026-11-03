import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget
from shiboken6 import delete, isValid

from themes import ChunkyTabBar, ThemedComboBox


app = QApplication([])
errors = []
sys.excepthook = lambda kind, value, trace: errors.append(str(value))
for iteration in range(40):
    tabs = QTabWidget()
    bar = ChunkyTabBar(tabs)
    tabs.setTabBar(bar)
    for name in ('General', 'Style', 'Audio', 'File browser', 'Album list', 'Track list'):
        tabs.addTab(QWidget(), name)
    tabs.resize(400, 200)
    tabs.show()
    app.processEvents()
    bar.tabLayoutChange()
    assert bar.scroll_update_timer.isActive()
    timer = bar.scroll_update_timer
    delete(tabs)
    assert not isValid(timer)
    combo = ThemedComboBox()
    combo.addItems(('Default', 'Album theme'))
    combo.show()
    combo.showPopup()
    assert combo.popup_position_timer.isActive()
    timer = combo.popup_position_timer
    delete(combo)
    assert not isValid(timer)
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QTest.qWait(1)
assert not errors, errors
print('PASS: 40 tab and dropdown destruction cycles cancel pending callbacks without Python errors or native crashes')
