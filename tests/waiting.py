"""Waiting helpers for checks that drive the real app.

Much of Album Drive works through timers, animations and background workers, so a check often has
to wait for a result. Waiting for a condition instead of a fixed time keeps checks quick on fast
machines, patient on slow ones, and clear about what never happened.
"""

import time

from PySide6.QtTest import QTest


def wait_until(condition, seconds=8, message=None):
	"""Keep Qt running until condition() is true, and fail the check if it is not after `seconds`.

	`message` explains a timeout. It may be a function, to describe the app's state at that moment.
	"""
	deadline = time.monotonic() + seconds
	while not condition() and time.monotonic() < deadline:
		QTest.qWait(20)  # Unlike time.sleep, this lets Qt run timers, animations and events meanwhile.
		time.sleep(.005)  # A moment for background threads, such as library scanners.
	if not condition():
		raise AssertionError(message() if callable(message) else message or f'Timed out after {seconds} s')


def wait_for_saved_library(window, seconds=8):
	"""Wait until the saved music folder has either opened or been found unreachable.

	The folder is checked in the background (it may be a sleeping network share), so it opens a
	moment after the window does, not during startup itself."""
	wait_until(lambda: window.library_waiting is None or window.library_retry.isActive(), seconds,
			lambda: f'The saved music folder never answered: {window.library_waiting}')
