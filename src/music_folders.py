from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QLayout, QListWidget, QListWidgetItem,
                               QSizePolicy, QVBoxLayout)
from responsive import SHORT_HEIGHT, ScreenFit, running_on_android, wrap_freely
from themes import ThemedButton


class MusicFolderDialog(QDialog):
    """In-app browser for Android, where the system picker returns content links instead of file paths."""

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
        self.path_label = QLabel()
        self.path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.path_label)
        self.up_button = ThemedButton('Up')
        self.up_button.clicked.connect(lambda: self.open_directory(self.directory.parent))
        layout.addWidget(self.up_button)
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
        self.select_button.clicked.connect(self.accept)
        self.select_button.setVisible(not self.file_suffixes)
        actions.addWidget(self.select_button, 1)
        layout.addLayout(actions)
        self.open_directory(directory)
        ScreenFit(self, 480, 680)

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
            entries = list(self.directory.iterdir())
            folders = sorted((path.name for path in entries if path.is_dir()), key=str.casefold)
            files = sorted((path.name for path in entries if path.is_file() and path.suffix.lower() in self.file_suffixes),
                           key=str.casefold)
        except OSError:
            self.status.setText('Cannot open this folder. Check storage access in Android settings.')
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
        self.update_path()

    def update_path(self):
        path = str(self.directory)
        self.path_label.setText(self.path_label.fontMetrics().elidedText(path, Qt.ElideMiddle, self.path_label.width()))
        self.path_label.setToolTip(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.heading.setHidden(self.height() < SHORT_HEIGHT)
        self.update_path()


def music_directory():
    if running_on_android():
        return Path('/storage/emulated/0/Music')
    return Path.home() / 'Music'


def choose_music_directory(parent, title, directory):
    options = QFileDialog.ShowDirsOnly
    if running_on_android():
        if not str(directory).startswith('/storage/'):
            directory = music_directory()
        if not Path(directory).is_dir():
            directory = '/storage/emulated/0'
        dialog = MusicFolderDialog(parent, title, directory)
        return str(dialog.directory) if dialog.exec() == QDialog.Accepted else ''
    return QFileDialog.getExistingDirectory(parent, title, str(directory), options)


def choose_image_file(parent, title, directory):
    suffixes = ('.jpg', '.jpeg', '.png')
    if running_on_android():
        if not Path(directory).is_dir():
            directory = '/storage/emulated/0/Pictures'
        if not Path(directory).is_dir():
            directory = '/storage/emulated/0'
        dialog = MusicFolderDialog(parent, title, directory, suffixes)
        return str(dialog.selected_file) if dialog.exec() == QDialog.Accepted and dialog.selected_file else ''
    path, _ = QFileDialog.getOpenFileName(parent, title, str(directory), 'Cover images (*.jpg *.jpeg *.png)')
    return path
