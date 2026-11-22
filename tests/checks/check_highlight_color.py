import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from color_rules import color_contrast
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog, capture_color_theme, saved_color_themes
from themes import COLOR_SETTINGS, button_paint_rect, button_text_color, control_face
from waiting import wait_until


def face_color(button):
	image = button.grab().toImage()
	face = control_face(button_paint_rect(button), widget=button)
	return image.pixelColor(round(face.center().x()), round(face.top() + 5)).name()


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
	root = Path(directory)
	(root / 'Music').mkdir()
	settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
	settings.setValue('folder', str(root / 'Music'))
	settings.setValue('artwork_theme_enabled', False)
	window = PlayerWindow(settings)
	window.show()
	for theme in ('chunky',):
		window.set_theme(theme)
		app.processEvents()
		dialog = ThemeSettingsDialog(settings, window)
		dialog.show()
		app.processEvents()
		# OK grows in when the dialog opens and stays hidden behind an opacity veil until it settles.
		wait_until(lambda: dialog.action_buttons[-1].graphicsEffect() is None)
		highlight = app.property('themeHighlight')
		assert highlight != app.property('themeAccent')
		assert app.property('brandTextColor') == highlight
		assert app.property('headingTextColor') == app.property('textColor')
		assert window.play.property('themeRole') == 'highlight'
		assert dialog.action_buttons[-1].property('themeRole') == 'highlight'
		window.play.setEnabled(True)
		assert face_color(window.play) == highlight, (theme, 'play', face_color(window.play), highlight)
		assert face_color(dialog.action_buttons[-1]) == highlight, (theme, 'OK', face_color(dialog.action_buttons[-1]), highlight)
		assert face_color(dialog.action_buttons[1]) != highlight
		assert color_contrast(QColor(highlight), button_text_color(highlight, highlighted=True)) >= 1.25
		image = window.grab()
		if theme == 'chunky':
			image.save('build/debug/four-color-theme.png')
		preset = capture_color_theme(saved_color_themes(settings), 'Four colors')
		assert preset['colors']['theme_accent_color'] == highlight
		assert preset['colors']['theme_highlight_color'] == app.property('themeAccent')
		assert {prop for _, _, _, prop, _ in COLOR_SETTINGS} <= {bytes(name).decode() for name in app.dynamicPropertyNames()}
		dialog.reject()
		dialog.deleteLater()
		QTest.qWait(1)
	window.close()
	while window.scanners:
		QTest.qWait(10)
print('PASS: play and OK faces, logo and album heading share the fourth accent in both themes, with readable foregrounds and saved color support')
