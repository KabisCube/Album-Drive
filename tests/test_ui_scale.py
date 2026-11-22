import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import ui_scale
from ui_scale import SCALE_VARIABLE, apply_ui_scale, nearest_ui_scale, restart_app


def saved(value):
	settings = MagicMock()
	settings.value.return_value = value
	return lambda: settings


class UiScaleTests(unittest.TestCase):
	def setUp(self):
		environment = patch.dict(os.environ)
		environment.start()
		self.addCleanup(environment.stop)
		os.environ.pop(SCALE_VARIABLE, None)
		os.environ.pop('ANDROID_ARGUMENT', None)
		for name, value in (('_active_scale', 1.0), ('_set_by_album_drive', False)):
			reset = patch.object(ui_scale, name, value)
			reset.start()
			self.addCleanup(reset.stop)

	def test_values_snap_to_monitor_scales(self):
		self.assertEqual(nearest_ui_scale(1.3), 1.25)
		self.assertEqual(nearest_ui_scale('1.5'), 1.5)
		self.assertEqual(nearest_ui_scale(9), 2.0)
		self.assertEqual(nearest_ui_scale(.1), .5)
		self.assertEqual(nearest_ui_scale('not a number'), 1.0)
		self.assertEqual(nearest_ui_scale(None), 1.0)

	def test_saved_scale_sets_qt_scale_factor(self):
		apply_ui_scale(saved('1.5'))
		self.assertEqual(os.environ[SCALE_VARIABLE], '1.5')
		self.assertEqual(ui_scale.active_ui_scale(), 1.5)

	def test_normal_scale_leaves_qt_alone(self):
		apply_ui_scale(saved('1'))
		self.assertNotIn(SCALE_VARIABLE, os.environ)
		self.assertEqual(ui_scale.active_ui_scale(), 1.0)

	def test_scale_set_when_starting_the_app_wins(self):
		os.environ[SCALE_VARIABLE] = '3'
		apply_ui_scale(saved('1.5'))
		self.assertEqual(os.environ[SCALE_VARIABLE], '3')
		self.assertEqual(ui_scale.active_ui_scale(), 1.5, 'no restart prompt for the saved choice')

	def test_android_keeps_its_own_scaling(self):
		os.environ['ANDROID_ARGUMENT'] = '/data/app'
		apply_ui_scale(saved('2'))
		self.assertNotIn(SCALE_VARIABLE, os.environ)
		self.assertEqual(ui_scale.active_ui_scale(), 1.0)

	def test_unreadable_settings_start_at_normal_size(self):
		def broken():
			raise OSError('read-only folder')
		apply_ui_scale(broken)
		self.assertNotIn(SCALE_VARIABLE, os.environ)

	def test_restart_runs_the_same_program_without_the_old_scale(self):
		apply_ui_scale(saved('2'))
		with patch('PySide6.QtCore.QProcess.startDetached', return_value=(True, 1)) as start, \
				patch.object(sys, 'argv', ['src/main.py', '--flag']), patch.object(sys, 'frozen', False, create=True):
			self.assertTrue(restart_app())
		program, arguments = start.call_args.args
		self.assertEqual(program, sys.executable)
		self.assertEqual(arguments, [os.path.abspath('src/main.py'), '--flag'])
		self.assertNotIn(SCALE_VARIABLE, os.environ, 'the new run must read the newly saved scale')

	def test_restart_of_a_built_app_runs_its_executable(self):
		with patch('PySide6.QtCore.QProcess.startDetached', return_value=(True, 1)) as start, \
				patch.object(sys, 'argv', ['/opt/AlbumDrive/AlbumDrive']), patch.object(sys, 'frozen', True, create=True):
			restart_app()
		self.assertEqual(start.call_args.args, (sys.executable, []))
