"""Offscreen settings workflow and sidebar regression checks."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QItemSelectionModel, QPoint, QRect, QSettings, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QPushButton, QStyle, QStyleOptionSlider, QStyleOptionViewItem, QTableWidgetItem

from main import PlayerWindow
from theme_settings import ThemeSettingsDialog
from test_library import make_wave
from themes import UI_FONT_DEFAULT, font_sizes


def check_slider(slider):
    low, high = slider.minimum(), slider.maximum()
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
    span = slider.width() - handle.width()
    slider.setValue(low)
    QTest.mousePress(slider, Qt.LeftButton, pos=QPoint(round(handle.width() / 2 + span * .75), 2))
    assert slider.isSliderDown()
    assert low + .7 * (high - low) <= slider.value() <= low + .9 * (high - low)
    QTest.mouseMove(slider, QPoint(round(handle.width() / 2 + span * .25), slider.height() - 2))
    assert low + .1 * (high - low) <= slider.value() <= low + .3 * (high - low)
    QTest.mouseRelease(slider, Qt.LeftButton, pos=QPoint(0, 2))
    assert slider.value() == low and not slider.isSliderDown()
    QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() - 1, 2))
    assert slider.value() == high


def branch_image(tree, index):
    pixmap = QPixmap(28, 30)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    tree.drawBranches(painter, QRect(0, 0, 28, 30), index)
    painter.end()
    return pixmap.toImage()


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    old, new = root / 'Old library', root / 'New library'
    make_wave(old / 'Old album' / '1.wav')
    make_wave(new / 'New album' / '1.wav')
    for number in range(40):
        (new / f'Empty folder {number}').mkdir()
    (new / 'Empty folder 0' / 'Child').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(old))
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 1 and not window.scanners)
    original_size = window.size()
    for width in (1000, 1400, 1700):
        window.resize(width, original_size.height())
        QTest.qWait(20)
        background = window.brand.background_rect()
        origin = window.brand.mapTo(window, background.topLeft().toPoint())
        assert origin.x() == origin.y() == 16
        assert background.width() == window.tree.width()
        assert window.brand.mapTo(window, QPoint()).x() == window.tree.mapTo(window, QPoint()).x()
        image = window.grab().toImage()
        color = app.property('brandLineColor')
        assert image.pixelColor(origin.x() + int(background.width()) // 2, origin.y() + 1).name() == color
        assert image.pixelColor(origin.x() + 1, origin.y() + int(background.height()) // 2).name() == color
        assert image.pixelColor(origin.x() + int(background.width()) - 2, origin.y() + int(background.height()) // 2).name() == color
    window.resize(original_size)
    QTest.qWait(20)
    assert not window.settings_button.text() and not window.settings_button.icon().isNull()
    assert window.settings_button.accessibleName() == 'Settings'
    assert window.settings_button.x() > window.refresh_button.x()
    assert window.settings_button.menu() is None
    assert window.volume.x() - window.play.geometry().right() >= 12
    assert window.previous.x() - window.volume.geometry().right() >= 12
    window.settings_button.click()
    assert window.settings_dialog.isVisible()
    assert not window.settings_dialog.isModal()
    window.settings_dialog.reject()
    assert not hasattr(window, 'sort_label')
    assert not any(label.text() == 'Albums' for label in window.findChildren(QLabel))
    assert window.count_label.isVisible()
    assert window.track_title.font().pixelSize() == 18
    assert window.album_table.columnWidth(0) > 30
    assert not any(button.text() == 'Set Library' and button.isVisible() for button in window.findChildren(QPushButton))

    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    assert 'theme_placeholder_text_color' not in dialog.colors
    assert dialog.numbers['hover_rotation'].maximum() == 45
    assert dialog.tabs.tabText(1) == 'Style'
    assert dialog.tabs.tabText(2) == 'Audio'
    assert 'button_outline_width' not in dialog.numbers
    assert dialog.tabs.widget(1).isAncestorOf(dialog.numbers['ui_thickness'])
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    QTest.qWait(30)
    check_slider(dialog.rounding_slider)
    check_slider(dialog.numbers['ui_thickness'].slider)
    dialog.tabs.setCurrentIndex(4)
    QTest.qWait(30)
    check_slider(dialog.numbers['hover_rotation'].slider)
    assert dialog.tabs.tabText(0) == 'General'
    assert not hasattr(dialog, 'font_choice')
    with patch('theme_settings.QFileDialog.getExistingDirectory', return_value=str(new)):
        dialog.library_button.click()
    assert window.current_folder == old
    assert settings.value('folder') == str(old)
    dialog.theme_name = 'classic'
    font = next(font for font in app.property('availableFonts') if font['id'] != UI_FONT_DEFAULT)
    dialog.ui_font_choice.setCurrentIndex(dialog.ui_font_choice.findData(font['id']))
    dialog.numbers['main_font_size'].setValue(22)
    dialog.numbers['track_list_font_size'].setValue(110)
    dialog.numbers['track_list_vertical_spacing'].setValue(18)
    assert 'logo_line_width' not in dialog.numbers
    assert 'logo_line_height' not in dialog.numbers
    dialog.apply()
    wait_until(lambda: window.current_folder == new and not window.scanners)
    assert app.property('playerTheme') == 'classic'
    assert window.album_table.font().family() == font['family']
    assert app.property('timelineFontSize') == font_sizes(settings)['timeline_font_size']
    assert app.property('mainFontSize') == 22
    assert window.album_table.font().pixelSize() == font_sizes(settings)['track_list_font_size']
    metrics = QFontMetricsF(window.album_table.font())
    assert window.album_table.columnWidth(0) >= max(metrics.tightBoundingRect(str(n)).width() for n in range(100)) + 12
    assert window.album_table.verticalHeader().defaultSectionSize() == max(44, window.album_table.fontMetrics().height() + 12) + 18
    # Single- and double-digit numbers share the same visible left edge.
    table = window.album_table
    table.setRowCount(1)
    left_edges = []
    for number in ('1', '11', '99'):
        table.setItem(0, 0, QTableWidgetItem(number))
        option = QStyleOptionViewItem()
        option.font = table.font()
        option.rect = QRect(0, 0, table.columnWidth(0), table.verticalHeader().defaultSectionSize())
        pixmap = QPixmap(option.rect.size())
        pixmap.fill(QColor('#f2efdf'))
        painter = QPainter(pixmap)
        table.itemDelegateForColumn(0).paint(painter, option, table.model().index(0, 0))
        painter.end()
        image = pixmap.toImage()
        left_edges.append(min(x for x in range(image.width()) for y in range(image.height())
                              if image.pixelColor(x, y).name() != '#f2efdf'))
    assert left_edges == [12, 12, 12]
    table.setRowCount(0)
    assert window.brand.background_rect().width() == window.tree.width()
    dialog.accept()

    # Cancelled edits never reach preferences or the active app.
    cancelled = ThemeSettingsDialog(settings, window)
    cancelled.numbers['main_font_size'].setValue(9)
    cancelled.reject()
    assert int(settings.value('main_font_size')) == 22
    window.volume.setValue(43)
    assert window.volume.toolTip() == '43%'
    check_slider(window.volume)
    window.volume.setLayoutDirection(Qt.RightToLeft)
    QTest.mouseClick(window.volume, Qt.LeftButton, pos=QPoint(0, 2))
    assert window.volume.value() == 100
    window.volume.setLayoutDirection(Qt.LeftToRight)

    settings.setValue('corner_roundness', 100)
    # Distinguish the underline from gray antialiasing pixels in white labels.
    settings.setValue('theme_accent_color', '#5689ab')
    settings.remove('custom_theme_colors')
    window.set_theme('chunky')
    wait_until(lambda: window.tree.verticalScrollBar().isVisible())
    QTest.qWait(40)
    panel = QColor(app.property('themeBackground')).darker(110).name()
    bar = window.tree.verticalScrollBar()
    assert bar.parentWidget().grab().toImage().pixelColor(0, 0).name() == panel
    assert bar.grab().toImage().pixelColor(0, 0).name() == panel
    leaf = window.files.index(str(new / 'Empty folder 1'))
    parent = window.files.index(str(new / 'Empty folder 0'))
    branch_image(window.tree, parent)  # Request the asynchronous child listing.
    branch_image(window.tree, leaf)
    wait_until(lambda: window.files.rowCount(parent) == 1)
    window.tree.clearSelection()
    image = branch_image(window.tree, leaf)
    assert not any(image.pixelColor(x, y).alpha() for x in range(28) for y in range(30))
    image = branch_image(window.tree, parent)
    points = [(x + .5, y + .5, image.pixelColor(x, y).alpha())
              for x in range(28) for y in range(30) if image.pixelColor(x, y).alpha()]
    weight = sum(alpha for _, _, alpha in points)
    assert weight > 0
    assert abs(sum(x * alpha for x, _, alpha in points) / weight - 14) < .75
    assert abs(sum(y * alpha for _, y, alpha in points) / weight - 14) < .75
    selected = window.files.index(str(new / 'New album'))
    window.tree.setCurrentIndex(selected)
    window.tree.selectionModel().select(selected, QItemSelectionModel.ClearAndSelect)
    wait_until(lambda: not window.scanners)
    QTest.qWait(40)
    row = window.tree.visualRect(selected)
    image = window.tree.viewport().grab().toImage()
    assert image.pixelColor(row.right() - 3, row.center().y()).name() == panel
    branch_left = max(0, row.left() - window.tree.indentation())
    assert image.pixelColor(branch_left, row.center().y()).name() == panel
    assert image.pixelColor(branch_left + 1, row.top() + 1).name() == panel
    assert not any(image.pixelColor(x, y).name() == app.property('themeAccent')
                   for x in range(branch_left, row.left()) for y in range(row.top(), row.bottom()))
    underline = [(x, y) for x in range(row.left(), row.right()) for y in range(row.top(), row.bottom() + 1)
                 if image.pixelColor(x, y).name() == app.property('themeAccent')]
    assert underline
    underline_rows = {y for _, y in underline if sum(py == y for _, py in underline) > 20}
    assert len(underline_rows) == 3
    assert max(x for x, _ in underline) - min(x for x, _ in underline) > 20
    window.open_album(window.grid.item(0))
    QTest.qWait(30)
    button = window.settings_button
    assert window.childAt(button.mapTo(window, button.rect().center())) is button
    QTest.mouseClick(button, Qt.LeftButton)
    assert window.settings_dialog.isVisible()
    window.settings_dialog.reject()
    assert window.viewed_album is not None
    tighter = ThemeSettingsDialog(settings, window)
    tighter.applied.connect(window.apply_settings)
    spacing = tighter.numbers['track_list_vertical_spacing']
    assert spacing.slider.minimum() == -32
    original_height = window.album_table.verticalHeader().defaultSectionSize()
    original_width = window.album_table.columnWidth(0)
    spacing.setValue(-16)
    tighter.apply()
    assert window.album_table.verticalHeader().defaultSectionSize() < original_height
    assert window.album_table.columnWidth(0) == original_width
    assert window.album_table.font().pixelSize() == font_sizes(settings)['track_list_font_size']
    assert window.viewed_album is not None
    tighter.close()
    window.close()
    wait_until(lambda: not window.scanners)
    # Windows registry DWORDs can expose a saved -16 as this unsigned value.
    settings.setValue('track_list_vertical_spacing', 4294967280)
    settings.sync()
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    restored.show()
    wait_until(lambda: not restored.scanners and len(restored.albums) == 1)
    assert restored.album_table.font().family() == font['family']
    assert app.property('timelineFontSize') == font_sizes(settings)['timeline_font_size']
    assert app.property('mainFontSize') == 22
    assert restored.album_table.font().pixelSize() == font_sizes(settings)['track_list_font_size']
    assert app.property('trackListVerticalSpacing') == -16
    restored_dialog = ThemeSettingsDialog(settings, restored)
    assert restored_dialog.numbers['track_list_vertical_spacing'].value() == -16
    restored_dialog.close()
    assert Path(restored.files.filePath(restored.tree.rootIndex())) == new
    restored.close()

print('PASS: Settings library/theme/font controls, Apply/Cancel, saved preferences, volume percentage, matching scrollbar corners and 3px folder underline')
