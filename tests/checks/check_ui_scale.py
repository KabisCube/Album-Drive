"""UI scale sits under General → Display, steps through monitor scales, saves on OK, and restarts on request."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication([])

from main import PlayerWindow


def wait_until(condition, seconds=8):
	for _ in range(seconds * 50):
		if condition():
			return
		QTest.qWait(20)
	assert condition()


def open_settings(window):
	window.edit_theme_settings()
	dialog = window.settings_dialog
	wait_until(lambda: 'ui_scale' in getattr(dialog, 'numbers', {}) and dialog.isVisible())
	return dialog, dialog.numbers['ui_scale']


with TemporaryDirectory() as directory:
	root = Path(directory)
	(root / 'Music').mkdir()
	settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
	settings.setValue('folder', str(root / 'Music'))
	settings.setValue('welcome_complete', True)
	window = PlayerWindow(settings)
	window.resize(1100, 800)
	window.show()
	QTest.qWait(300)

	dialog, scale = open_settings(window)
	assert dialog.tabs.tabText(0) == 'General'
	assert dialog.tabs.widget(0).isAncestorOf(scale), 'UI scale belongs on the General tab'
	labels = []
	for position in range(scale.slider.maximum() + 1):
		scale.slider.setValue(position)
		labels.append(scale.label.text())
	assert labels == ['0.5×', '0.75×', '1×', '1.25×', '1.5×', '1.75×', '2×'], labels
	scale.setValue(1.0)
	assert not dialog.scale_restart_button.isEnabled(), 'nothing to restart for at the running scale'
	scale.setValue(1.5)
	assert dialog.scale_restart_button.isEnabled() and '1.5×' in dialog.scale_restart_note.text()

	# Cancel keeps the saved scale.
	dialog.reject()
	wait_until(lambda: window.settings_dialog is None)
	assert settings.value('ui_scale') in (None, 1.0, '1'), settings.value('ui_scale')

	# OK saves it without restarting.
	dialog, scale = open_settings(window)
	scale.setValue(1.25)
	dialog.accept()
	wait_until(lambda: window.settings_dialog is None)
	assert float(settings.value('ui_scale')) == 1.25
	assert not app.property('restartRequested') and window.isVisible()

	# Restart now saves the new scale, then closes the window so main() starts Album Drive again.
	dialog, scale = open_settings(window)
	assert scale.value() == 1.25
	scale.setValue(.75)
	dialog.scale_restart_button.click()
	wait_until(lambda: not window.isVisible())
	assert float(settings.value('ui_scale')) == .75, 'Restart now accepts the dialog, saving every setting'
	assert app.property('restartRequested')
	while window.scanners:
		QTest.qWait(10)
print('PASS: UI scale under General, monitor-scale stops, Cancel keeps it, OK saves it, Restart now saves then restarts')
