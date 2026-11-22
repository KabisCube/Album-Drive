import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
							QSizePolicy, QVBoxLayout)
from responsive import SHORT_HEIGHT, ScreenFit, running_on_android, wrap_freely
from themes import ThemedButton


class MusicFolderDialog(QDialog):
	"""In-app folder and image browser that follows the app theme on every platform.

	Android needs it because the system picker returns content links instead of file paths.
	The path field also takes a typed folder, absolute or relative to the one shown."""

	def __init__(self, parent, title, directory, file_suffixes=()):
		super().__init__(parent)
		self.file_suffixes = {suffix.lower() for suffix in file_suffixes}
		self.selected_file = None
		self.setWindowTitle(title)
		layout = QVBoxLayout(self)
		layout.setSizeConstraint(QLayout.SetNoConstraint)
		layout.setContentsMargins(12, 12, 12, 12)
		heading = QLabel(title)
		heading.setObjectName('heading')
		heading.setWordWrap(True)
		wrap_freely(heading)
		self.heading = heading
		layout.addWidget(heading)
		self.path_field = QLineEdit()
		self.path_field.setAccessibleName('Folder path')
		self.path_field.setPlaceholderText('Type a folder path and press Enter')
		self.path_field.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
		self.path_field.returnPressed.connect(self.go_to_typed_path)
		layout.addWidget(self.path_field)
		places = QHBoxLayout()
		self.up_button = ThemedButton('Up')
		self.up_button.clicked.connect(lambda: self.open_directory(self.directory.parent))
		self.home_button = ThemedButton('Home')
		self.home_button.clicked.connect(lambda: self.open_directory(home_directory()))
		self.music_button = ThemedButton('Music')
		self.music_button.clicked.connect(lambda: self.open_directory(music_directory()))
		self.music_button.setEnabled(music_directory().is_dir())
		for button in (self.up_button, self.home_button, self.music_button):
			button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
			button.setProperty('fitButtonTextLocally', True)
			places.addWidget(button, 1)
		layout.addLayout(places)
		self.folders = QListWidget()
		self.folders.setAccessibleName('Folders')
		self.folders.setMinimumHeight(60)
		self.folders.setWordWrap(True)
		self.folders.setStyleSheet('QListWidget::item { padding: 12px 8px; }')
		self.folders.itemClicked.connect(self.open_item)
		layout.addWidget(self.folders, 1)
		self.status = QLabel()
		self.status.setWordWrap(True)
		wrap_freely(self.status)
		layout.addWidget(self.status)
		actions = QHBoxLayout()
		cancel = ThemedButton('Cancel')
		cancel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
		cancel.setProperty('fitButtonTextLocally', True)
		cancel.clicked.connect(self.reject)
		actions.addWidget(cancel, 1)
		self.select_button = ThemedButton('Select')
		self.select_button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
		self.select_button.setProperty('fitButtonTextLocally', True)
		self.select_button.setProperty('themeRole', 'highlight')
		self.select_button.clicked.connect(self.choose)
		self.select_button.setVisible(not self.file_suffixes)
		actions.addWidget(self.select_button, 1)
		layout.addLayout(actions)
		# Enter in the path field should only open that folder, not also press a button.
		for button in (self.up_button, self.home_button, self.music_button, cancel, self.select_button):
			button.setAutoDefault(False)
		self.open_directory(directory)
		ScreenFit(self, 480, 680)

	def typed_path(self):
		path = Path(os.path.expanduser(self.path_field.text().strip()))
		# normpath turns "Music/Album/.." into "Music", so the field shows a clean path.
		return Path(os.path.normpath(path if path.is_absolute() else self.directory / path))

	def go_to_typed_path(self):
		"""Open the typed folder, or pick the typed image. Returns False when the path is unusable."""
		path = self.typed_path()
		if path.is_dir():
			self.open_directory(path)
			return True
		if self.file_suffixes and path.is_file() and path.suffix.lower() in self.file_suffixes:
			self.selected_file = path
			self.accept()
			return True
		self.status.setText(f'"{path}" is not a folder.' if not self.file_suffixes
							else f'"{path}" is not a folder or a JPG or PNG image.')
		self.status.setVisible(True)
		return False

	def choose(self):
		# A path typed but not yet opened with Enter is what the person means to select.
		if self.path_field.text().strip() != str(self.directory) and not self.go_to_typed_path():
			return
		if self.select_button.isEnabled():
			self.accept()

	def open_item(self, item):
		target = self.directory / item.data(Qt.UserRole)
		if target.is_dir():
			self.open_directory(target)
		else:
			self.selected_file = target
			self.accept()

	def open_directory(self, directory):
		self.directory = Path(directory)
		self.folders.clear()
		try:
			# Hidden folders like .cache would bury Music and Documents; a typed path still reaches them.
			entries = [path for path in self.directory.iterdir() if not path.name.startswith('.')]
			folders = sorted((path.name for path in entries if path.is_dir()), key=str.casefold)
			files = sorted((path.name for path in entries if path.is_file() and path.suffix.lower() in self.file_suffixes),
						key=str.casefold)
		except OSError:
			self.status.setText('Cannot open this folder. Check storage access in Android settings.' if running_on_android()
								else 'Cannot open this folder. You may not have permission to read it.')
			self.select_button.setEnabled(False)
		else:
			for name in folders:
				item = QListWidgetItem(name + '/' if self.file_suffixes else name)
				item.setData(Qt.UserRole, name)
				self.folders.addItem(item)
			for name in files:
				item = QListWidgetItem(name)
				item.setData(Qt.UserRole, name)
				self.folders.addItem(item)
			if self.file_suffixes:
				self.status.setText('' if files else 'No images in this folder.')
			else:
				self.status.setText('No subfolders. You can select this folder.' if not folders else '')
			self.select_button.setEnabled(True)
		self.status.setVisible(bool(self.status.text()))
		self.up_button.setEnabled(self.directory.parent != self.directory)
		self.path_field.setText(str(self.directory))

	def resizeEvent(self, event):
		super().resizeEvent(event)
		self.heading.setHidden(self.height() < SHORT_HEIGHT)


def home_directory():
	# On Android, Path.home() is the app's private folder; people mean the shared storage instead.
	if running_on_android():
		return Path('/storage/emulated/0')
	return Path.home()


def music_directory():
	return home_directory() / 'Music'


def choose_music_directory(parent, title, directory):
	if running_on_android():
		if not str(directory).startswith('/storage/'):
			directory = music_directory()
		if not Path(directory).is_dir():
			directory = '/storage/emulated/0'
	elif not Path(directory).is_dir():
		directory = Path.home()
	dialog = MusicFolderDialog(parent, title, directory)
	return str(dialog.directory) if dialog.exec() == QDialog.Accepted else ''


def choose_image_file(parent, title, directory):
	suffixes = ('.jpg', '.jpeg', '.png')
	if running_on_android():
		if not Path(directory).is_dir():
			directory = '/storage/emulated/0/Pictures'
		if not Path(directory).is_dir():
			directory = '/storage/emulated/0'
	elif not Path(directory).is_dir():
		directory = Path.home()
	dialog = MusicFolderDialog(parent, title, directory, suffixes)
	return str(dialog.selected_file) if dialog.exec() == QDialog.Accepted and dialog.selected_file else ''
