"""Popup direction, scrolling, selection and live button styling."""
import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from themes import CONTROL_HEADROOM, ThemedComboBox, button_paint_rect, control_face, control_shadow, text_style, ui_depth
from main import load_app_font
from theme_settings import ThemeSettingsDialog

app = QApplication([])
app.setStyle('Fusion')
load_app_font()
app.setStyleSheet(text_style())
window = QWidget()
layout = QVBoxLayout(window)
choice = ThemedComboBox()
choice.addItems(['Alphabetical', 'Oldest', 'Newest', 'Custom'])
layout.addWidget(choice)
window.resize(350, 100)
window.show()
app.processEvents()


def settle_popup():
    while choice.drop.moving:
        QTest.qWait(16)
    app.processEvents()


def press_outside_popup(point):
    global_point = QPointF(choice.mapToGlobal(point))
    local = QPointF(choice.popup.mapFromGlobal(global_point.toPoint()))
    QApplication.sendEvent(choice.popup, QMouseEvent(QEvent.MouseButtonPress, local, global_point, Qt.LeftButton,
                                                     Qt.LeftButton, Qt.NoModifier))
    if choice.popup.isVisible():
        choice.popup.hide()


for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    choice.setCurrentIndex(2)
    QTest.mouseClick(choice, Qt.LeftButton)
    settle_popup()
    app.processEvents()
    assert choice.popup.isVisible()
    own_face = control_face(button_paint_rect(choice), widget=choice)
    popup_face = control_face(button_paint_rect(choice.popup), widget=choice.popup)
    gap = choice.popup.y() + popup_face.top() - choice.mapToGlobal(QPoint(0, round(own_face.bottom()))).y()
    assert abs(gap) <= 1, gap
    view = choice.view()
    assert view.visualRect(choice.model().index(0, 0)).top() >= 0
    target = view.visualRect(choice.model().index(1, 0)).center()
    QTest.mouseMove(view.viewport(), target)
    app.processEvents()
    row = view.visualRect(choice.model().index(1, 0))
    origin = view.viewport().mapTo(choice.popup, row.topLeft())
    preview = choice.popup.grab().toImage()
    assert preview.pixelColor(preview.width() // 2, round(control_face(button_paint_rect(choice.popup), widget=choice.popup).top() + 2)).name() == QColor('#393939').darker(110).name()
    # Hover leaves the menu surface plain, with a three-pixel text underline.
    assert preview.pixelColor(origin.x() + 2, origin.y() + row.height() // 2).name() == QColor('#393939').darker(110).name()
    line_y = min(row.bottom() - 3, row.center().y() + view.fontMetrics().height() / 2 + 1)
    point = view.viewport().mapTo(choice.popup, QPoint(row.left() + 11, round(line_y)))
    assert preview.pixelColor(point).name() == '#888888'
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=target)
    assert choice.currentIndex() == 1
    assert not choice.popup.isVisible()
app.setProperty('themeBackground', '#b3c4d5')
choice.showPopup()
settle_popup()
app.processEvents()
preview = choice.popup.grab().toImage()
assert preview.pixelColor(preview.width() // 2, round(control_face(button_paint_rect(choice.popup), widget=choice.popup).top() + 2)).name() == QColor('#b3c4d5').darker(110).name()
choice.hidePopup()
app.setProperty('buttonFill', '#cccccc')
choice.clear()
choice.addItems([f'Font {i}' for i in range(80)])
choice.setCurrentIndex(70)
choice.showPopup()
settle_popup()
app.processEvents()
assert choice.view().verticalScrollBar().maximum() > 0
assert choice.view().verticalScrollBar().isVisible()
assert choice.view().viewport().height() >= 10 * choice.view().sizeHintForRow(0)
assert choice.popup.grab().toImage().pixelColor(0, 0).alpha() == 0
assert not choice.view().hasAutoScroll()
offset = choice.view().verticalScrollBar().value()
QTest.mouseMove(choice.view().viewport(), QPoint(15, choice.view().viewport().height() - 1))
QTest.qWait(400)
assert choice.view().verticalScrollBar().value() == offset
assert choice.view().viewport().rect().intersects(choice.view().visualRect(choice.model().index(70, 0)))
QTest.keyClick(choice.view(), Qt.Key_Down)
QTest.keyClick(choice.view(), Qt.Key_Return)
assert choice.currentIndex() == 71
assert not choice.popup.isVisible()
# Near the bottom of a screen, use the space above rather than a three-row slit.
screen = choice.screen().availableGeometry()
window.move(screen.left() + 20, screen.bottom() - window.height() - 20)
app.processEvents()
choice.showPopup()
settle_popup()
app.processEvents()
assert choice.popup.y() < choice.mapToGlobal(QPoint()).y()
assert choice.view().viewport().height() >= 10 * choice.view().sizeHintForRow(0)
QTest.keyClick(choice.view(), Qt.Key_Escape)
assert not choice.popup.isVisible()
with tempfile.TemporaryDirectory() as folder:
    settings = QSettings(str(Path(folder) / 'settings.ini'), QSettings.IniFormat)
    dialog = ThemeSettingsDialog(settings)
    dialog.artwork_theme.setChecked(True)
    assert not dialog.saved_theme_choice.isEnabled()
    dialog.artwork_theme.setChecked(False)
    assert dialog.saved_theme_choice.isEnabled()
    dialog.reject()
window.move(screen.left() + 20, screen.top() + 40)
app.processEvents()
choice.showPopup()
QTest.qWait(40)
below = choice.popup_edge
assert choice.popup.y() < choice.popup_final.y()
assert choice.popup.mask().boundingRect().top() + choice.popup.y() >= below
travel = []
while choice.drop.moving:
    travel.append(choice.popup.y() - choice.popup_final.y())
    QTest.qWait(8)
assert travel and travel[0] < 0 and max(travel) > 0, travel
assert choice.popup.pos() == choice.popup_final.topLeft()
assert choice.popup.mask().boundingRect().top() + choice.popup.y() == choice.popup_edge
from themes import control_silhouette
outline = control_silhouette(choice, button_paint_rect(choice))
corner = choice.mapToGlobal(QPoint()) - choice.popup.pos()
covered = [point for point in (QPoint(round(outline.boundingRect().center().x()), round(outline.boundingRect().bottom()) - 1),)
           if outline.contains(point)]
assert covered
for point in covered:
    assert not choice.popup.mask().contains(point + corner), point
for _ in range(3):
    press_outside_popup(choice.rect().center())
    app.processEvents()
    assert not choice.popup.isVisible()
    QTest.mouseClick(choice, Qt.LeftButton)
    app.processEvents()
    assert not choice.popup.isVisible()
    QTest.qWait(450)
    QTest.mouseClick(choice, Qt.LeftButton)
    settle_popup()
    assert choice.popup.isVisible()
press_outside_popup(QPoint(choice.width() + 200, -200))
app.processEvents()
assert not choice.popup.isVisible()
QTest.mouseClick(choice, Qt.LeftButton)
settle_popup()
assert choice.popup.isVisible()
choice.hidePopup()
window.close()
print('PASS: downward popups, flat/thick styling, mouse/keyboard selection, long lists and saved-theme dependencies')
