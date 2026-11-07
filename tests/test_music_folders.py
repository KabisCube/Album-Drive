from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QFileDialog
from music_folders import MusicFolderDialog, choose_music_directory, music_directory


class MusicFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_desktop_preserves_directory_and_native_picker(self):
        with patch.object(QApplication, 'platformName', return_value='offscreen'), \
                patch.object(QFileDialog, 'getExistingDirectory', return_value='/music') as picker:
            self.assertEqual(choose_music_directory(None, 'Music', '/chosen'), '/music')
            self.assertEqual(picker.call_args.args[2], '/chosen')
            self.assertFalse(picker.call_args.args[3] & QFileDialog.DontUseNativeDialog)
            self.assertEqual(music_directory(), Path.home() / 'Music')

    def test_android_uses_a_filesystem_picker_and_shared_music(self):
        with patch.object(QApplication, 'platformName', return_value='android'), \
                patch.object(Path, 'is_dir', return_value=True), \
                patch('music_folders.MusicFolderDialog') as picker:
            picker.return_value.exec.return_value = QDialog.Accepted
            picker.return_value.directory = Path('/storage/emulated/0/Music')
            self.assertEqual(Path(choose_music_directory(None, 'Music', 'content://old-picker/tree')), Path('/storage/emulated/0/Music'))
            self.assertEqual(Path(picker.call_args.args[2]), Path('/storage/emulated/0/Music'))

    def test_android_falls_back_to_shared_storage(self):
        with patch.object(QApplication, 'platformName', return_value='android'), \
                patch.object(Path, 'is_dir', return_value=False), \
                patch('music_folders.MusicFolderDialog') as picker:
            picker.return_value.exec.return_value = QDialog.Rejected
            self.assertEqual(choose_music_directory(None, 'Music', '/missing'), '')
            self.assertEqual(picker.call_args.args[2], '/storage/emulated/0')

    def test_phone_picker_navigation_selection_and_fit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Artist' / 'Album').mkdir(parents=True)
            (root / 'song.mp3').touch()
            dialog = MusicFolderDialog(None, 'Choose music library root', root)
            dialog.resize(320, 600)
            dialog.show()
            self.app.processEvents()
            self.assertEqual(dialog.width(), 320)
            self.assertTrue(dialog.rect().contains(dialog.select_button.geometry()))
            self.assertEqual(dialog.folders.count(), 1)
            dialog.folders.itemClicked.emit(dialog.folders.item(0))
            self.assertEqual(dialog.directory, root / 'Artist')
            dialog.up_button.click()
            self.assertEqual(dialog.directory, root)
            dialog.folders.itemClicked.emit(dialog.folders.item(0))
            dialog.select_button.click()
            self.assertEqual(dialog.result(), QDialog.Accepted)
            self.assertEqual(dialog.directory, root / 'Artist')

    def test_unreadable_folder_cannot_be_selected(self):
        with patch.object(Path, 'iterdir', side_effect=PermissionError):
            dialog = MusicFolderDialog(None, 'Music', '/storage/emulated/0/Music')
            self.assertFalse(dialog.select_button.isEnabled())
            self.assertIn('storage access', dialog.status.text())
            dialog.reject()
