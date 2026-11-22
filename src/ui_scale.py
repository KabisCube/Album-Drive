"""The interface scale people choose in Settings, applied through Qt's own scale factor.

Qt reads QT_SCALE_FACTOR once, while QApplication starts, and then scales every widget, font and
painted control sharply. So the scale is read from settings before the app exists, and a change
applies when Album Drive restarts. It multiplies the operating system's display scale, so 4K and
8K screens already scaled by Windows or the desktop only need it as a personal adjustment.
"""

import os
import sys

UI_SCALE_KEY = 'ui_scale'
UI_SCALE_DEFAULT = 1.0
# The usual monitor scales, one per slider step.
UI_SCALE_STOPS = (.5, .75, 1.0, 1.25, 1.5, 1.75, 2.0)
SCALE_VARIABLE = 'QT_SCALE_FACTOR'

_active_scale = UI_SCALE_DEFAULT
_set_by_album_drive = False


def nearest_ui_scale(value):
	try:
		value = float(value)
	except (TypeError, ValueError):
		return UI_SCALE_DEFAULT
	return min(UI_SCALE_STOPS, key=lambda stop: abs(stop - value))


def ui_scale_supported():
	# Phones have their own scaling, and the Android layout fits every window to the screen.
	# QApplication cannot tell the platform yet when this runs, so check what Python and the launcher know.
	return not (sys.platform == 'android' or 'ANDROID_ARGUMENT' in os.environ)


def apply_ui_scale(open_settings):
	"""Set Qt's scale factor from the saved setting. Call before QApplication is created."""
	global _active_scale, _set_by_album_drive
	if not ui_scale_supported():
		return
	try:
		scale = nearest_ui_scale(open_settings().value(UI_SCALE_KEY, UI_SCALE_DEFAULT))
	except Exception:
		return  # Unreadable settings are reported once the window opens them; start at the normal size.
	_active_scale = scale
	if SCALE_VARIABLE in os.environ:
		return  # Someone set Qt's scale themselves when starting the app; theirs wins.
	if scale != UI_SCALE_DEFAULT:
		os.environ[SCALE_VARIABLE] = f'{scale:g}'
		_set_by_album_drive = True


def active_ui_scale():
	"""The scale this run started with, to tell whether a new choice still needs a restart."""
	return _active_scale


def restart_app():
	"""Start a new Album Drive. Call after this one has closed, so the new one reads saved settings."""
	from PySide6.QtCore import QProcess
	if _set_by_album_drive:
		# The new process inherits this environment, and must read the newly chosen scale instead.
		os.environ.pop(SCALE_VARIABLE, None)
	if getattr(sys, 'frozen', False):
		program, arguments = sys.executable, sys.argv[1:]
	else:
		program, arguments = sys.executable, [os.path.abspath(sys.argv[0]), *sys.argv[1:]]
	started, _pid = QProcess.startDetached(program, arguments)
	return started
