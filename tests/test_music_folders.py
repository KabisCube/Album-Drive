from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog
from music_folders import MusicFolderDialog, choose_image_file, choose_music_directory, music_directory


class MusicFolderTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.app = QApplication.instance() or QApplication([])

	def test_desktop_uses_the_themed_picker_at_the_given_folder(self):
		with TemporaryDirectory() as directory, \
				patch.object(QApplication, 'platformName', return_value='offscreen'), \
				patch('music_folders.MusicFolderDialog') as picker:
			picker.return_value.exec.return_value = QDialog.Accepted
			picker.return_value.directory = Path(directory) / 'Albums'
			self.assertEqual(Path(choose_music_directory(None, 'Music', directory)), Path(directory) / 'Albums')
			self.assertEqual(Path(picker.call_args.args[2]), Path(directory))
			self.assertEqual(music_directory(), Path.home() / 'Music')

	def test_desktop_falls_back_to_home_for_a_missing_folder(self):
		with patch.object(QApplication, 'platformName', return_value='offscreen'), \
				patch('music_folders.MusicFolderDialog') as picker:
			picker.return_value.exec.return_value = QDialog.Rejected
			self.assertEqual(choose_music_directory(None, 'Music', '/no/such/folder'), '')
			self.assertEqual(Path(picker.call_args.args[2]), Path.home())
			self.assertEqual(choose_image_file(None, 'Cover', '/no/such/folder'), '')
			self.assertEqual(picker.call_args.args[3], ('.jpg', '.jpeg', '.png'))

	def test_typed_path_opens_folders_and_reports_bad_ones(self):
		with TemporaryDirectory() as directory:
			root = Path(directory)
			(root / 'Artist' / 'Album').mkdir(parents=True)
			dialog = MusicFolderDialog(None, 'Music', root)
			self.assertEqual(dialog.path_field.text(), str(root))
			dialog.path_field.setText(str(root / 'Artist' / 'Album'))
			dialog.path_field.returnPressed.emit()
			self.assertEqual(dialog.directory, root / 'Artist' / 'Album')
			dialog.path_field.setText('..')
			dialog.path_field.returnPressed.emit()
			self.assertEqual(dialog.directory, root / "Artist")
			dialog.path_field.setText(str(root / 'missing'))
			dialog.path_field.returnPressed.emit()
			self.assertEqual(dialog.directory, root / "Artist")
			self.assertIn('is not a folder', dialog.status.text())
			self.assertEqual(dialog.result(), 0, 'Enter in the path field must not press a button')
			dialog.select_button.click()
			self.assertNotEqual(dialog.result(), QDialog.Accepted, 'a bad typed path cannot be selected')
			dialog.path_field.setText(str(root / 'Artist' / 'Album'))
			dialog.select_button.click()
			self.assertEqual(dialog.result(), QDialog.Accepted)
			self.assertEqual(dialog.directory, root / 'Artist' / 'Album')

	def test_home_and_music_shortcuts(self):
		with TemporaryDirectory() as directory:
			home = Path(directory)
			(home / 'Music' / 'Jazz').mkdir(parents=True)
			with patch('music_folders.home_directory', return_value=home):
				dialog = MusicFolderDialog(None, 'Music', home / 'Music' / 'Jazz')
				self.assertTrue(dialog.music_button.isEnabled())
				dialog.home_button.click()
				self.assertEqual(dialog.directory, home)
				dialog.music_button.click()
				self.assertEqual(dialog.directory, home / 'Music')
				self.assertEqual(dialog.path_field.text(), str(home / 'Music'))
				(home / 'Music' / 'Jazz').rmdir()
				(home / 'Music').rmdir()
				without_music = MusicFolderDialog(None, 'Music', home)
				self.assertFalse(without_music.music_button.isEnabled(), 'no Music folder, nothing to jump to')

	def test_android_home_is_shared_storage(self):
		with patch.object(QApplication, 'platformName', return_value='android'):
			from music_folders import home_directory
			self.assertEqual(home_directory(), Path('/storage/emulated/0'))
			self.assertEqual(music_directory(), Path('/storage/emulated/0/Music'))

	def test_typed_image_path_is_picked(self):
		with TemporaryDirectory() as directory:
			root = Path(directory)
			(root / 'front.PNG').touch()
			(root / 'notes.txt').touch()
			dialog = MusicFolderDialog(None, 'Cover', root, ('.jpg', '.jpeg', '.png'))
			dialog.path_field.setText('notes.txt')
			dialog.path_field.returnPressed.emit()
			self.assertIsNone(dialog.selected_file)
			self.assertIn('JPG or PNG', dialog.status.text())
			dialog.path_field.setText('front.PNG')
			dialog.path_field.returnPressed.emit()
			self.assertEqual(dialog.selected_file, root / 'front.PNG')
			self.assertEqual(dialog.result(), QDialog.Accepted)

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
			(root / '.cache').mkdir()
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
			self.assertIn('Cannot open this folder', dialog.status.text())
			dialog.reject()
