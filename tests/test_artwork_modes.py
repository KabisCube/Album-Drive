"""Album colors: five picks in order, kept within the comfortable range, never tuned afterwards."""

from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app_theme import DARKEST_BACKGROUND, INVENTED_DISTINCT, LIGHTNESS_RANGE, ROLES, artwork_theme_colors, distance
from color_rules import color_contrast
from themes import PANEL_SHADE
from theme_settings import ThemeSettingsDialog


def cover(*colors):
	image = Image.new('RGB', (len(colors), 1))
	image.putdata(colors)
	output = BytesIO()
	image.save(output, format='PNG')
	return output.getvalue()


COVERS = {
	'snow': [(238, 251, 249)] * 50 + [(1, 1, 1)] * 30 + [(67, 73, 71)] * 8 + [(138, 164, 153)] * 6 + [(233, 6, 17)] * 2,
	'beige': [(227, 213, 187)] * 60 + [(165, 162, 83)] * 10 + [(44, 67, 59)] * 10 + [(78, 95, 80)] * 6
			+ [(247, 234, 212)] * 5,
	'white': [(250, 251, 250)] * 80 + [(8, 12, 6)] * 6 + [(180, 41, 21)] * 2 + [(200, 202, 198)] * 3,
	'black': [(0, 0, 0)] * 100,
	'gray': [(0, 0, 0)] * 84 + [(187, 187, 187)] * 4 + [(78, 78, 78)] * 4 + [(255, 255, 255)] * 4 + [(133, 133, 133)] * 4,
	'blue': [(20, 40, 180)] * 100,
}


class ArtworkModeTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.app = QApplication.instance() or QApplication([])

	def themes(self):
		for name, pixels in COVERS.items():
			for mode in ('any', 'dark', 'light'):
				yield name, mode, artwork_theme_colors(cover(*pixels), mode)

	def test_five_colors_never_repeat(self):
		for name, mode, colors in self.themes():
			values = [QColor(colors[role]) for role in ROLES]
			for index, first in enumerate(values):
				for second in values[index + 1:]:
					self.assertGreaterEqual(distance(first, second), INVENTED_DISTINCT - .001, (name, mode, [v.name() for v in values]))

	def test_colors_stay_within_the_comfortable_range(self):
		for name, mode, colors in self.themes():
			for role in ('themeBackground', 'themeHighlight', 'themeAccent', 'themeBackgroundAccent'):
				level = QColor(colors[role]).lightnessF()
				floor = DARKEST_BACKGROUND if role in ('themeBackground', 'themeBackgroundAccent') else LIGHTNESS_RANGE[0]
				self.assertGreaterEqual(level, floor - .01, (name, mode, role, colors[role]))
				self.assertLessEqual(level, LIGHTNESS_RANGE[1] + .01, (name, mode, role, colors[role]))

	def test_minimum_contrasts(self):
		for name, mode, colors in self.themes():
			background, text = QColor(colors['themeBackground']), QColor(colors['textColor'])
			button, ink = QColor(colors['themeAccent']), QColor(colors['themeBackgroundAccent'])
			self.assertGreaterEqual(color_contrast(background, text), 4, (name, mode))
			self.assertGreaterEqual(color_contrast(background, button), 1.1, (name, mode))
			self.assertGreaterEqual(color_contrast(button, ink), 1.545, (name, mode))
			self.assertGreaterEqual(color_contrast(background, ink), 1.1, (name, mode))
			self.assertGreaterEqual(color_contrast(background.darker(PANEL_SHADE), ink), 1.05, (name, mode))

	def test_every_role_follows_one_of_the_five_colors(self):
		for name, mode, colors in self.themes():
			for key in ('secondaryTextColor', 'folderArrowColor', 'headingTextColor', 'selectedTextColor',
						'timelineTextColor', 'paperTextColor'):
				self.assertEqual(colors[key], colors['textColor'])
			for key in ('buttonTextColor', 'buttonIconColor', 'disabledTextColor'):
				self.assertEqual(colors[key], colors['themeBackgroundAccent'])
			self.assertEqual(colors['brandTextColor'], colors['themeHighlight'])
			self.assertEqual(colors['timelineColor'], colors['themeAccent'])
			self.assertEqual(colors['buttonFill'], colors['themeAccent'])
			self.assertEqual(colors['paperBackgroundColor'], colors['themeBackground'])

	def test_light_and_dark_sides(self):
		for name in COVERS:
			light = QColor(artwork_theme_colors(cover(*COVERS[name]), 'light')['themeBackground'])
			dark = QColor(artwork_theme_colors(cover(*COVERS[name]), 'dark')['themeBackground'])
			self.assertGreater(light.lightnessF(), dark.lightnessF(), name)

	def test_black_is_a_last_resort_moved_to_the_edge(self):
		colors = artwork_theme_colors(cover(*COVERS['snow']), 'dark')
		self.assertEqual(colors['themeBackground'], '#434947')
		colors = artwork_theme_colors(cover(*COVERS['black']), 'dark')
		self.assertEqual(colors['themeBackground'], '#1f1f1f')

	def test_white_is_a_last_resort_moved_to_the_edge(self):
		colors = artwork_theme_colors(cover(*COVERS['white']), 'light')
		self.assertAlmostEqual(QColor(colors['themeBackground']).lightnessF(), LIGHTNESS_RANGE[1], delta=.01)
		colors = artwork_theme_colors(cover(*([(255, 255, 255)] * 90 + [(20, 20, 20)] * 10)), 'light')
		self.assertAlmostEqual(QColor(colors['themeBackground']).lightnessF(), LIGHTNESS_RANGE[1], delta=.01)

	def test_largest_color_group_on_the_side_is_the_background(self):
		pixels = [(251, 29, 12)] * 28 + [(245, 15, 3)] * 26 + [(242, 171, 27)] * 6 + [(8, 4, 90)] * 6 + [(250, 250, 250)] * 2 + [(10, 2, 5)] * 2
		self.assertEqual(artwork_theme_colors(cover(*pixels), 'light')['themeBackground'], '#fb1d0c')
		dark = QColor(artwork_theme_colors(cover(*pixels), 'dark')['themeBackground'])
		self.assertGreater(dark.blue(), 2 * dark.red())

	def test_dominant_color_in_the_lighter_half_is_the_light_background(self):
		pixels = [(60, 175, 238)] * 60 + [(252, 253, 252)] * 30 + [(7, 25, 36)] * 10
		colors = artwork_theme_colors(cover(*pixels), 'light')
		self.assertEqual(colors['themeBackground'], '#3cafee')
		self.assertGreaterEqual(color_contrast(QColor('#3cafee'), QColor(colors['textColor'])), 4)

	def test_most_used_light_color_is_the_light_background(self):
		self.assertEqual(artwork_theme_colors(cover(*COVERS['beige']), 'light')['themeBackground'], '#e3d5bb')

	def test_accent_is_the_saturated_pop(self):
		self.assertEqual(artwork_theme_colors(cover(*COVERS['snow']), 'light')['themeHighlight'], '#e90611')
		self.assertEqual(artwork_theme_colors(cover(*COVERS['white']), 'light')['themeHighlight'], '#b42915')

	def test_invented_button_sits_between_background_and_text(self):
		colors = artwork_theme_colors(cover(*COVERS['black']), 'light')
		background, text, button = (QColor(colors[key]).lightnessF() for key in
									('themeBackground', 'textColor', 'themeAccent'))
		self.assertLess(min(background, text), button)
		self.assertLess(button, max(background, text))

	def test_any_follows_the_most_used_color(self):
		art = cover(*COVERS['beige'])
		self.assertEqual(artwork_theme_colors(art), artwork_theme_colors(art, 'light'))
		self.assertEqual(artwork_theme_colors(art), artwork_theme_colors(art, 'invalid'))

	def test_missing_art(self):
		for mode in ('any', 'dark', 'light'):
			self.assertIsNone(artwork_theme_colors(b'broken', mode))
			self.assertIsNone(artwork_theme_colors(b'', mode))

	def test_settings_apply_cancel_restore_and_restart(self):
		app = QApplication.instance() or QApplication([])
		with tempfile.TemporaryDirectory() as directory:
			settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
			dialog = ThemeSettingsDialog(settings)
			self.assertEqual([dialog.artwork_theme_mode.itemText(i) for i in range(3)],
							['Best fit', 'Dark', 'Light'])
			self.assertEqual(dialog.artwork_theme_mode.currentData(), 'any')
			dialog.artwork_theme_mode.setCurrentIndex(1)
			dialog.reject()
			self.assertFalse(settings.contains('artwork_theme_mode'))
			dialog = ThemeSettingsDialog(settings)
			for mode in ('dark', 'light'):
				dialog.artwork_theme_mode.setCurrentIndex(dialog.artwork_theme_mode.findData(mode))
				dialog.apply()
				settings.sync()
				reopened = ThemeSettingsDialog(QSettings(settings.fileName(), QSettings.IniFormat))
				self.assertEqual(reopened.artwork_theme_mode.currentData(), mode)
				reopened.close()
			dialog.artwork_theme.setChecked(False)
			self.assertTrue(dialog.artwork_theme_mode.isEnabled())
			self.assertLess(dialog.artwork_theme_mode.findData('any'), 0)
			dialog.restore_defaults()
			self.assertEqual(dialog.artwork_theme_mode.currentData(), 'any')
			self.assertTrue(dialog.artwork_theme_mode.isEnabled())
			dialog.apply()
			self.assertEqual(settings.value('artwork_theme_mode'), 'any')
			dialog.close()


if __name__ == '__main__':
	unittest.main()
