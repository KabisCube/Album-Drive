"""Check whether folders can be reached without freezing the window.

A music folder on a network share (a NAS) that is asleep or offline can take up to a minute to
answer even a simple "is this a folder?" question. That wait happens here, on a plain daemon thread
the app never waits for, so neither the window nor quitting is held up by a share that won't answer."""
import threading

from PySide6.QtCore import QObject, Signal

from file_paths import filesystem_path


class FolderProbe(QObject):
	answered = Signal(int, object)  # request number, first reachable folder or None

	def __init__(self, parent=None):
		super().__init__(parent)
		self.request = 0

	def check(self, folders):
		"""Look for the first of these folders that exists; the answer arrives later through `answered`."""
		self.request += 1
		request = self.request
		folders = list(folders)

		def run():
			found = None
			for folder in folders:
				try:
					if filesystem_path(folder).is_dir():
						found = folder
						break
				except OSError:
					pass
			try:
				# Qt queues this over to the window's thread, since it's sent from another one.
				self.answered.emit(request, found)
			except RuntimeError:
				pass  # The window closed while the share was still deciding.

		threading.Thread(target=run, name='folder-probe', daemon=True).start()
		return request

	def cancel(self):
		"""Ignore any answer still on its way."""
		self.request += 1
