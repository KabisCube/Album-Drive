import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from main import load_app_font
from theme_settings import SettingResetButton
from themes import ChunkyTabBar, ThemedButton, ThemedComboBox, button_text_bounds, button_text_font, button_text_sizing, chunky_style, control_face, text_style, ui_depth


app = QApplication([])
app.setStyle('Fusion')
load_app_font()
app.setProperty('playerTheme', 'chunky')
app.setProperty('buttonFontSize', 30)
app.setProperty('dropdownFontSize', 30)
app.setProperty('buttonTextColor', '#000000')
app.setProperty('cornerRoundness', 100)
app.setProperty('uiThickness', 100)
app.setStyleSheet(chunky_style('QWidget { background: #393939; }') + text_style())
window = QWidget()
window.resize(640, 430)
large = ThemedButton('Wide button', window)
large.setGeometry(20, 20, 430, 80)
small = ThemedButton('Narrow', window)
small.setGeometry(20, 110, 130, 50)
choice = ThemedComboBox(window)
choice.addItems(['One', 'A longer choice'])
choice.setGeometry(20, 180, 220, 56)
reset = SettingResetButton('Test')
reset.setParent(window)
reset.setGeometry(260, 180, reset.sizeHint().width(), reset.sizeHint().height())
reset.hide()
tabs = ChunkyTabBar(window)
tabs.addTab('General')
tabs.addTab('File browser')
tabs.setGeometry(20, 270, 500, tabs.tabSizeHint(0).height())
window.show()
QTest.qWait(30)
controls = (large, small, choice, reset, tabs)

def check_fit():
    size = button_text_sizing().pixel_size
    assert 1 < size <= 30
    for widget in controls:
        assert button_text_font(widget).pixelSize() == size
        for rect, texts in widget.button_text_regions():
            for text in texts:
                bounds = button_text_bounds(widget.font().toString(), text, size)
                assert bounds.width() <= rect.width() and bounds.height() <= rect.height(), (text, size, bounds, rect)
    for button in (large, small):
        rect = button.button_text_regions()[0][0]
        image = button.grab().toImage()
        points = [(x, y) for y in range(image.height()) for x in range(image.width())
                  if image.pixelColor(x, y).alpha() == 255 and image.pixelColor(x, y).name() == '#000000']
        assert points
        assert all(rect.adjusted(-1, -1, 1, 1).contains(x, y) for x, y in points)
    return size

initial = check_fit()
assert initial < 30
choice.addItem('Speakers (Steam Streaming Speakers)')
QTest.qWait(20)
assert check_fit() == initial
choice.setCurrentIndex(choice.count() - 1)
QTest.qWait(20)
assert check_fit() < initial
choice.setCurrentIndex(0)
QTest.qWait(20)
assert check_fit() == initial
reset.show()
QTest.qWait(20)
assert check_fit() == initial
small.setText('A much longer label')
QTest.qWait(20)
assert check_fit() < initial
small.setText('Narrow')
QTest.qWait(20)
assert check_fit() == initial
small.resize(100, 40)
QTest.qWait(20)
assert check_fit() <= initial
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    outer = tabs.tab_face_rect(0)
    face = control_face(outer, widget=tabs)
    assert abs(face.center().y() + ui_depth() / 2 - tabs.height() / 2) < .1
window.close()
QTest.qWait(10)
print('PASS: shared smallest text size, padded ink bounds, label/size changes, stable Reset and centered tabs')
