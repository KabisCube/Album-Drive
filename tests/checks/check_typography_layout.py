import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout
from main import PlayerWindow
from theme_settings import SETTING_LABEL_WIDTH, ThemeSettingsDialog
from themes import FONT_BASE_SIZES, FONT_SCALE_KEYS, font_sizes


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    QTest.qWait(100)
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    dialog.resize(1040, 680)
    dialog.show()
    QTest.qWait(50)
    for master in (8, 16, 18, 19, 25, 16):
        positions = set()
        dialog.numbers['main_font_size'].setValue(master)
        dialog.apply()
        QTest.qWait(30)
        for index in range(dialog.tabs.count()):
            form = dialog.forms[dialog.tabs.tabText(index)]
            for row in range(form.rowCount()):
                label = form.itemAt(row, QFormLayout.LabelRole)
                field = form.itemAt(row, QFormLayout.FieldRole)
                if label is not None and field is not None:
                    column = dialog.label_column_width()
                    assert label.widget().width() == column <= SETTING_LABEL_WIDTH
                    text_width = label.widget().fontMetrics().horizontalAdvance(label.widget().text())
                    assert column == SETTING_LABEL_WIDTH or label.widget().heightForWidth(column) <= label.widget().fontMetrics().height() * 1.6, \
                        (label.widget().text(), column, text_width)
                    assert label.widget().wordWrap()
                    positions.add(field.geometry().left())
        assert app.property('headingFontSize') == round(FONT_BASE_SIZES['heading_font_size'] * master / 16)
        assert len(positions) == 1, (master, positions)
    for key in FONT_SCALE_KEYS:
        if key in dialog.numbers and key not in ('dropdown_font_size', 'menu_font_size', 'secondary_font_size'):
            assert dialog.numbers[key].value() == 100
            assert dialog.numbers[key].slider.minimum() == 75
            assert dialog.numbers[key].slider.maximum() == 125
    dialog.numbers['logo_font_size'].setValue(110)
    dialog.apply()
    assert app.property('logoFontSize') == round(27 * 1.1)
    assert dialog.numbers['main_font_size'].maximum() == 25
    for width, height in ((1040, 180), (600, 180), (1040, 680)):
        dialog.resize(width, height)
        QTest.qWait(40)
        for button in dialog.action_buttons:
            assert button.height() == button.sizeHint().height()
            assert dialog.rect().contains(button.geometry())
    dialog.reject()
    assert font_sizes(settings) == FONT_BASE_SIZES
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    QTest.qWait(100)
print('PASS: fixed columns, master font ratios, bounded relative scales, short-window footer and Cancel rollback')
