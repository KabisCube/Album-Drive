import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from shiboken6 import isValid

from main import PlayerWindow


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    completed = []
    deleted = []
    def apply_and_close():
        dialog = window.settings_dialog
        iteration = len(completed)
        control = dialog.numbers['button_size']
        dialog.tabs.currentWidget().ensureWidgetVisible(control)
        control.setValue((20, 72, 44)[iteration % 3])
        dialog.numbers['settings_vertical_spacing'].setValue((-8, 0, 20)[iteration % 3])
        dialog.apply()
        if iteration == 3:
            dialog.saved_theme_choice.showPopup()
        if iteration % 2:
            dialog.accept()
        else:
            dialog.reject()
        assert not dialog.scroll_anchor_timer.isActive()
        assert not dialog.color_preview_timer.isActive()
        assert dialog.pending_scroll_anchor is None
        assert window.settings_dialog is None
        deleted.append(dialog)
        completed.append(iteration)
        QTimer.singleShot(30, step)
    def step():
        assert all(not isValid(dialog) for dialog in deleted)
        if len(completed) == 6:
            window.close()
            app.quit()
            return
        window.edit_theme_settings()
        QTimer.singleShot(20, apply_and_close)
    QTimer.singleShot(30, step)
    QTimer.singleShot(10000, app.quit)
    try:
        app.exec()
        assert len(completed) == 6
    finally:
        window.close()
        app.processEvents()
print('PASS: Apply then immediate Cancel/OK, popup cleanup, timer cancellation and repeated dialog destruction')
