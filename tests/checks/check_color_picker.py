"""Themed color field, RGB/hex synchronization and staged accept/cancel."""

import os
from pathlib import Path
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from color_picker import ColorPickerDialog
from color_rules import comfortable_surface
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'missing'))
    window = PlayerWindow(settings)
    picker = ColorPickerDialog(QColor('#162b47'), window, 'Main accent')
    picker.show()
    QTest.qWait(30)
    assert picker.original.color().name() == '#162b47'
    assert picker.hex_edit.text() == '#162b47'
    picker.channels['red'].setValue(127)
    assert picker.color.red() == 127 and picker.channels['green'].value() == 43
    assert picker.hex_edit.text() == '#7f2b47'
    picker.hex_edit.setFocus()
    picker.hex_edit.selectAll()
    QTest.keyClicks(picker.hex_edit, '#39bda2')
    assert picker.color.name() == '#39bda2'
    assert picker.preview.color() == picker.color
    assert picker.channels['red'].value() == 57
    picker.hex_edit.selectAll()
    QTest.keyClicks(picker.hex_edit, '#oops')
    assert not picker.accept_button.isEnabled()
    assert picker.color.name() == '#39bda2'
    picker.channels['blue'].setValue(220)
    assert picker.accept_button.isEnabled()
    assert picker.hex_edit.text() == picker.color.name()
    QTest.mouseClick(picker.field, Qt.LeftButton,
                     pos=QPoint(picker.field.width() - 5, 5))
    assert picker.color.hsvSaturationF() > .98 and picker.color.valueF() > .98
    picker.channels['hue'].setValue(120)
    assert picker.color.green() > 250 and picker.color.red() < 8
    assert picker.original.color().name() == '#162b47'
    Path('build').mkdir(exist_ok=True)
    picker.grab().save('build/color-picker.png')
    picker.cancel_button.click()
    assert picker.result() == QDialog.Rejected

    def accept_color():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, ColorPickerDialog)
        dialog.set_color(QColor('#be5632'))
        dialog.accept_button.click()

    parent = ThemeSettingsDialog(settings, window)
    button = parent.colors['theme_accent_color']
    initial = settings.value('theme_accent_color')
    QTimer.singleShot(30, accept_color)
    parent.choose_color(button, 'Main accent')
    assert button.color() == comfortable_surface('#be5632')
    assert settings.value('theme_accent_color') == initial
    QTimer.singleShot(30, lambda: app.activeModalWidget().reject())
    parent.choose_color(button, 'Main accent')
    assert button.color() == comfortable_surface('#be5632')
    parent.reject()
    window.close()

print('PASS: themed color picker, click/drag field, RGB/HSV/hex sync, invalid hex and staged accept/cancel')
