import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout, QWidget
from main import PlayerWindow
from theme_settings import SettingsSectionLabel, ThemeSettingsDialog
from themes import ThemedComboBox, button_text_sizing


app = QApplication([])
Path('build').mkdir(exist_ok=True)

with TemporaryDirectory() as directory:
    root = Path(directory)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root))
    settings.setValue('welcome_complete', True)
    settings.setValue('continuous_playback', False)
    settings.setValue('button_sound_volume', 30)
    settings.setValue('corner_roundness', 50)
    window = PlayerWindow(settings)
    window.show()
    dialog = ThemeSettingsDialog(settings, window)
    dialog.show()
    for width, height in ((1040, 680), (393, 780), (320, 600), (600, 320), (1040, 680)):
        dialog.resize(width, height)
        for index in range(dialog.tabs.count()):
            dialog.tabs.setCurrentIndex(index)
            QTest.qWait(40)
            assert dialog.size().width() == width
            for button in dialog.action_buttons:
                assert dialog.rect().contains(button.geometry()), (width, button.text(), button.geometry())
            area = dialog.tabs.currentWidget()
            page = area.widget()
            if width < 640:
                assert page.width() <= area.viewport().width(), (width, index, page.width(), area.viewport().width(),
                    [(type(widget).__name__, widget.objectName(), widget.minimumSizeHint().width(), widget.minimumWidth())
                     for widget in page.findChildren(QWidget) if widget.minimumSizeHint().width() > 200])
                assert not area.horizontalScrollBar().isVisible()
                assert button_text_sizing().pixel_size >= 12
                for combo in page.findChildren(ThemedComboBox):
                    assert combo.width() > 0
                for heading in page.findChildren(SettingsSectionLabel):
                    assert heading.height() >= heading.heightForWidth(heading.width())
                form = page.layout()
                for row in range(form.rowCount()):
                    label = form.itemAt(row, QFormLayout.LabelRole)
                    field = form.itemAt(row, QFormLayout.FieldRole)
                    if label is not None and field is not None:
                        assert label.geometry().bottom() < field.geometry().top()
            area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
            QTest.qWait(20)
            dialog.grab().save(f'build/settings-{width}-{height}-{index}.png')
    dialog.reject()
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()

print('PASS: every settings tab fits portrait and landscape phone sizes and returns to desktop layout')
