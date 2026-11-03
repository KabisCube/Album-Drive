import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider, QWidget

from themes import ColorSwatch, ThemedButton, ThemedComboBox, ThemeSlider, CONTROL_HEADROOM, accent_knob, chunky_style, control_body, control_face, control_offset, control_shadow, control_shadow_body, paint_control, button_paint_rect


app = QApplication([])
app.setStyle('Fusion')
app.setProperty('playerTheme', 'chunky')
app.setProperty('themeAccent', '#80b060')
app.setProperty('uiThickness', 200)
app.setProperty('cornerRoundness', 0)
app.setStyleSheet(chunky_style('', accent='#80b060', roundness=0))
window = QWidget()
window.resize(600, 240)
accent = QColor('#80b060')
shadow = accent.darker(125)
left = ThemedButton(window)
left.setGeometry(20, 10, 120, 50)
right = ThemedButton(window)
right.setGeometry(460, 10, 120, 50)
swatch = ColorSwatch('#dda077', 'Test', window)
swatch.setGeometry(20, 80, 120, 50)
swatch.setEnabled(False)
choice = ThemedComboBox(window)
choice.addItems(['First', 'Second'])
choice.setGeometry(460, 80, 120, 50)
choice.setEnabled(False)
slider = ThemeSlider(window)
slider.setGeometry(20, 160, 560, 40)
slider.setRange(0, 100)
window.show()
app.processEvents()

for button, side in ((left, 'right'), (right, 'left')):
    image = button.grab().toImage()
    base = control_face(button_paint_rect(button), pressed=True)
    y = round(base.center().y())
    x = round(base.right() - 1) if side == 'right' else round(base.left() + 1)
    assert image.pixelColor(x, y).name() == shadow.name(), side
    raised = control_face(button_paint_rect(button), widget=button)
    assert image.pixelColor(round(raised.center().x()), y) == accent, side
    button.setDown(True)
    pressed = button.grab().toImage()
    assert pressed.pixelColor(x, y) == accent, side
    button.setDown(False)

left.move(460, 10)
image = left.grab().toImage()
assert image.pixelColor(CONTROL_HEADROOM + 1, y).name() == shadow.name()
left.move(20, 10)

disabled = swatch.grab().toImage()
raised = control_face(button_paint_rect(swatch), widget=swatch)
x = round(raised.left() + 1)
assert disabled.pixelColor(x, round(raised.top() + 1)) == disabled.pixelColor(x, round(raised.center().y()))
disabled = choice.grab().toImage()
raised = control_face(button_paint_rect(choice), widget=choice)
x = round(raised.left() + 3)
assert disabled.pixelColor(x, round(raised.top() + 1)) == disabled.pixelColor(x, round(raised.top() + 5))

for value, side in ((0, 'right'), (100, 'left')):
    slider.setValue(value)
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
    image = slider.grab().toImage()
    base = control_face(QRectF(handle), pressed=True)
    x = round(base.right() - 1) if side == 'right' else round(base.left() + 1)
    assert image.pixelColor(x, handle.center().y()).name() == shadow.name(), (value, side)

swatch.setEnabled(True)
swatch.setGeometry(228, 80, 144, 50)
baseline_pixels = None
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    depth = thickness * 4 / 100
    base = control_face(button_paint_rect(left), pressed=True)
    face = control_face(button_paint_rect(left), widget=left)
    assert face.size() == base.size()
    assert face.top() == base.top() - depth
    assert control_face(button_paint_rect(right), widget=right).size() == base.size()
    image = swatch.grab().toImage()
    pixels = {(x, y) for y in range(image.height()) for x in range(image.width())
              if image.pixelColor(x, y).name() == '#dda077'}
    if baseline_pixels is None:
        baseline_pixels = pixels
    assert pixels == {(x, y - int(depth)) for x, y in baseline_pixels}
    icon = accent_knob(accent)
    for size in (24, 36, 48):
        canvas = QSize(size + 2 * CONTROL_HEADROOM, size + CONTROL_HEADROOM)
        image = icon.pixmap(canvas).toImage()
        pixels = [image.pixelColor(canvas.width() // 2, y).name() for y in range(canvas.height())]
        assert pixels.count(accent.name()) == size, (thickness, size)
        assert pixels.count(shadow.name()) == thickness * 4 // 100, (thickness, size)

app.setProperty('uiThickness', 0)
app.setProperty('cornerRoundness', 100)
icon = accent_knob(accent)
for canvas in (QSize(48, 36), QSize(60, 48), QSize(72, 36), QSize(48, 60)):
    rendered = icon.pixmap(canvas).toImage()
    diameter = min(canvas.width() - 24, canvas.height() - 12)
    expected = QPixmap(canvas)
    expected.fill(Qt.transparent)
    painter = QPainter(expected)
    painter.setRenderHint(QPainter.Antialiasing)
    ellipse = QRectF(0, 0, diameter, diameter)
    ellipse.moveCenter(QRectF(0, 0, canvas.width(), canvas.height()).center())
    ellipse.translate(0, 6)
    painter.setBrush(Qt.white)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(ellipse)
    painter.end()
    mask = expected.toImage()
    for y in range(canvas.height()):
        for x in range(canvas.width()):
            if mask.pixelColor(x, y).alpha() == 255:
                assert rendered.pixelColor(x, y).alpha() == 255, (canvas, x, y)
            if mask.pixelColor(x, y).alpha() == 0:
                assert rendered.pixelColor(x, y).alpha() == 0, (canvas, x, y)

app.setProperty('cornerRoundness', 0)
app.setProperty('uiThickness', 300)
rect = QRectF(0, 0, 48, 36)
face = control_face(rect, widget=left)
offset = control_offset(left, rect, 12)
radius = min(face.width(), face.height()) / 2
front = QPainterPath()
front.addRoundedRect(face, radius, radius)
for opacity in (1, .45):
    rendered = QPixmap(48, 36)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setOpacity(opacity)
    paint_control(painter, left, rect, accent, rounding=100)
    painter.end()
    image = rendered.toImage()
    for fraction in (0, .25, .5, .75, 1):
        mask = QPixmap(48, 36)
        mask.fill(Qt.transparent)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillPath(front.translated(offset * fraction), Qt.white)
        painter.end()
        expected = mask.toImage()
        for y in range(36):
            for x in range(48):
                if expected.pixelColor(x, y).alpha() == 255:
                    assert abs(image.pixelColor(x, y).alpha() - round(255 * opacity)) <= 2, (opacity, fraction, x, y)

gaps = 0
for depth in (4, 12):
    for rounding in (0, 100):
        for pressed in (False, True):
            for opacity in (1, .45):
                canvas = QPixmap(96, 96)
                canvas.fill(Qt.transparent)
                rect = QRectF(16, 16, 48, 36)
                face = control_face(rect, pressed, left, depth)
                offset = control_offset(left, rect, depth) if not pressed else control_offset(left, rect, 0)
                radius = min(face.width(), face.height()) / 2 * rounding / 100
                body = control_body(face.width(), face.height(), radius, offset.x(), offset.y()).translated(face.topLeft())
                base = QPainterPath()
                base.addRoundedRect(face.translated(offset), radius, radius)
                shadow_offset = control_shadow(depth)
                footprint = control_shadow_body(face.width(), face.height(), radius, offset.x(), offset.y(),
                                                shadow_offset.x(), shadow_offset.y())
                assert footprint.boundingRect().top() == offset.y()
                assert footprint.boundingRect().bottom() == offset.y() + face.height() + shadow_offset.y()
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setOpacity(opacity)
                paint_control(painter, left, rect, accent, pressed, depth, rounding, shadow=True)
                painter.end()
                image = canvas.toImage()
                endpoints = QPixmap(96, 96)
                endpoints.fill(Qt.transparent)
                painter = QPainter(endpoints)
                painter.fillPath(body, Qt.white)
                painter.fillPath(base.translated(shadow_offset), Qt.white)
                painter.end()
                old = endpoints.toImage()
                for fraction in (.25, .5, .75):
                    mask = QPixmap(96, 96)
                    mask.fill(Qt.transparent)
                    painter = QPainter(mask)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.fillPath(base.translated(shadow_offset * fraction), Qt.white)
                    painter.end()
                    expected = mask.toImage()
                    for y in range(96):
                        for x in range(96):
                            if expected.pixelColor(x, y).alpha() == 255 and old.pixelColor(x, y).alpha() == 0:
                                gaps += 1
                                assert image.pixelColor(x, y).alpha() >= round(65 * opacity) - 2, (depth, rounding, pressed, opacity, fraction, x, y)
assert gaps > 0
app.setProperty('uiThickness', 0)
for button in (left, right):
    image = button.grab().toImage()
    y = round(control_face(button_paint_rect(button), widget=button).center().y())
    assert image.pixelColor(CONTROL_HEADROOM + 1, y) == accent
    assert image.pixelColor(image.width() - CONTROL_HEADROOM - 2, y) == accent
window.close()
print('PASS: fixed face sizes, upward extrusion, perspective, connected edges, disabled opacity and press travel')
