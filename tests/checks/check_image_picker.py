"""The in-app image browser used on Android opens folders and returns the tapped image file."""
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])

from music_folders import MusicFolderDialog, choose_image_file

root = Path(tempfile.mkdtemp())
(root / 'Covers').mkdir()
Image.new('RGB', (8, 8), '#336699').save(root / 'Covers' / 'front.jpg')
(root / 'Covers' / 'notes.txt').write_text('not an image')
(root / 'track.wav').write_bytes(b'')


def names(dialog):
    return [dialog.folders.item(row).text() for row in range(dialog.folders.count())]


def open_dialog():
    return next(widget for widget in app.topLevelWidgets() if isinstance(widget, MusicFolderDialog) and widget.isVisible())


def browse_and_pick():
    dialog = open_dialog()
    assert names(dialog) == ['Covers/'], names(dialog)
    assert dialog.select_button.isHidden()
    dialog.open_item(dialog.folders.item(0))
    assert names(dialog) == ['front.jpg'], names(dialog)
    dialog.open_item(dialog.folders.item(0))


with patch('music_folders.running_on_android', return_value=True):
    QTimer.singleShot(0, browse_and_pick)
    chosen = choose_image_file(None, 'Choose cover image', root)
assert Path(chosen) == root / 'Covers' / 'front.jpg', chosen

with patch('music_folders.running_on_android', return_value=True):
    QTimer.singleShot(0, lambda: open_dialog().reject())
    assert choose_image_file(None, 'Choose cover image', root) == ''

folders = MusicFolderDialog(None, 'Choose music library root', root)
assert names(folders) == ['Covers']
assert not folders.select_button.isHidden()
folders.close()
print('PASS: Android image browser lists folders and images only, opens folders and returns the tapped image')
