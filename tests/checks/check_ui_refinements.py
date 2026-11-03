import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QListWidgetItem
from main import PlayerWindow
from color_rules import timeline_colors
from themes import NUMERIC_DEFAULTS

app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(100)
    window.edit_theme_settings()
    dialog = window.settings_dialog
    QTest.qWait(30)
    assert not hasattr(dialog, 'font_choice')
    assert 'heading_font_size' not in dialog.numbers
    assert not any(label.text() in ('Albums', 'Heading', 'Hover animation', 'Dynamic Theme')
                   for label in window.findChildren(QLabel))
    assert dialog.colors['theme_button_fill'].isHidden()
    assert dialog.library_label.text() == 'Currently: ' + str(root / 'Music')
    for key, value in (('settings_vertical_spacing', -12), ('folder_vertical_spacing', -4),
                       ('track_list_vertical_spacing', -16)):
        control = dialog.numbers[key]
        assert control.value() == value
        assert control.label.text() == '0 px'
        control.setValue(value + 3)
        assert control.label.text() == '3 px'
        control.setValue(value)
    assert dialog.numbers['button_icon_size'].value() == 28
    assert dialog.rounding_slider.value() == 32
    for key in ('album_horizontal_spacing', 'album_vertical_spacing'):
        assert dialog.numbers[key].maximum() == 50
    form = dialog.forms['Style']
    brightness = form.getWidgetPosition(dialog.artwork_theme_mode.parentWidget())[0]
    saved = form.getWidgetPosition(dialog.saved_theme_choice)[0]
    assert saved == brightness + 1
    assert dialog.option_labels[dialog.saved_theme_choice].text() == 'Saved themes'
    dialog.artwork_theme.setChecked(True)
    assert not dialog.saved_theme_choice.isEnabled()
    dialog.artwork_theme.setChecked(False)
    assert dialog.saved_theme_choice.isEnabled()
    dialog.preview_timer.stop()
    dialog.previewing = True
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        QTest.qWait(5)
        widths = []
        controls = {control for control in dialog.numbers.values()
                    if dialog.tabs.currentWidget().isAncestorOf(control)}
        for control in controls:
            previous = control.value()
            control.slider.setValue(control.slider.minimum())
            app.processEvents()
            left = control.slider.geometry()
            control.slider.setValue(control.slider.maximum())
            app.processEvents()
            assert control.slider.geometry() == left, (control.objectName(), left, control.slider.geometry())
            widths.append(control.slider.width())
            control.setValue(previous)
        assert len(set(widths)) <= 1, widths
    dialog.previewing = False
    dialog.apply()
    with patch.object(window, 'set_theme', wraps=window.set_theme) as theme, \
         patch.object(window, 'clear_case_cache', wraps=window.clear_case_cache) as clear:
        timings = []
        for value in range(-12, -2):
            dialog.numbers['settings_vertical_spacing'].setValue(value)
            start = time.perf_counter()
            dialog.apply()
            timings.append((time.perf_counter() - start) * 1000)
        assert not theme.called
        assert not clear.called
        dialog.numbers['button_icon_size'].setValue(29)
        dialog.apply()
        assert theme.call_count == 1
        assert not clear.called
    with patch.object(window, 'apply_settings') as apply, patch('theme_settings.write_theme_files') as write:
        emitted = []
        dialog.applied.connect(lambda: emitted.append(True))
        dialog.accept()
        assert not dialog.isVisible()
        assert not emitted
        assert not write.called
    print(f'Settings spacing preview average: {sum(timings) / len(timings):.1f} ms')
    seek = window.seek
    seek.setRange(0, 100000)
    rail, fill, filled_text, unfilled_text = timeline_colors(
        app.property('themeBackground'), app.property('themeAccent'))
    for value in (0, 100000):
        seek.setValue(value)
        path = seek.timestamp_path()
        bounds = path.boundingRect().adjusted(-2, -2, 2, 2).toAlignedRect()
        expected = QPixmap(seek.size())
        expected.fill(fill if value else rail)
        painter = QPainter(expected)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillPath(path, filled_text if value else unfilled_text)
        painter.end()
        actual = seek.grab().toImage().copy(bounds).convertToFormat(QImage.Format_RGBA8888)
        reference = expected.toImage().copy(bounds).convertToFormat(QImage.Format_RGBA8888)
        assert actual.constBits().tobytes() == reference.constBits().tobytes()

    grid = window.grid
    grid.clear()
    for row in range(8):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, row)
        grid.addItem(item)
    grid.orderChanged.disconnect(window.save_custom_order)
    grid.set_custom_order(True)
    grid.doItemsLayout()
    grid.finish_reflow()
    original = dict(grid._positions)
    original[1] += QPoint(30, 40)
    grid._positions = original
    grid.move_album(1, 5)
    grid.reflow_animation.pause()
    assert [grid.item(row).data(Qt.UserRole) for row in range(8)] == [0, 2, 3, 4, 5, 1, 6, 7]
    assert set(range(1, 6)) <= grid._reflow_targets.keys()
    assert grid._reflow_starts[5] == original[1]
    starts = dict(grid._positions)
    grid.reflow_animation.setCurrentTime(130)
    for row in range(1, 6):
        assert grid._positions[row] != starts[row]
        assert grid._positions[row] != grid._reflow_targets[row]
    grid.reflow_animation.setCurrentTime(260)
    grid.clear()
    window.close()
    QTest.qWait(40)
print('PASS: requested defaults, relative spacing, labels, theme placement, equal slider widths, incremental previews, immediate OK and continuous custom reorder')
