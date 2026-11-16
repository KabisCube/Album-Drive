"""Four editable colors, automatic contrast and legacy preset compatibility."""
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from app_theme import artwork_theme_colors, simplify_theme_colors
from themes import PRIMARY_COLOR_KEYS, COLOR_SETTINGS
from theme_settings import ThemeSettingsDialog, custom_color_settings, default_color_themes, saved_color_themes


class SimplePaletteTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.app = QApplication.instance() or QApplication([])

	def test_dynamic_roles_share_their_primary_colors(self):
		for rgb in ((255, 255, 255), (0, 0, 0), (180, 90, 30), (20, 40, 180)):
			data = BytesIO()
			Image.new('RGB', (12, 12), rgb).save(data, format='PNG')
			for mode in ('any', 'dark', 'light'):
				colors = artwork_theme_colors(data.getvalue(), mode)
				roles = ('themeBackground', 'themeAccent', 'timelineColor', 'brandTextColor',
						'buttonFill', 'textColor', 'buttonTextColor', 'buttonIconColor', 'folderArrowColor')
				self.assertLessEqual(len({colors[key] for key in roles}), 6)
				self.assertEqual(colors['brandTextColor'], colors['themeHighlight'])
				self.assertEqual(colors['headingTextColor'], colors['textColor'])
				self.assertEqual(colors['buttonTextColor'], colors['buttonIconColor'])
				self.assertTrue(QColor(colors['themeBackgroundAccent']).isValid())

	def test_buttons_preserve_chosen_ink_for_light_and_dark_surfaces(self):
		for fill in ('#eeeeee', '#111111', '#ac2614', '#2c80ee'):
			for ink in (None, '#122b40'):
				chosen = dict(themeBackground='#202020', themeAccent='#cf8020',
							buttonFill=fill, textColor='#ffffff', brandTextColor='#cfdf0e')
				if ink is not None:
					chosen['themeBackgroundAccent'] = ink
				palette = simplify_theme_colors(chosen)
				expected_ink = palette['themeBackgroundAccent'] if ink else palette['textColor']
				self.assertEqual(palette['buttonTextColor'], expected_ink)
				self.assertEqual(palette['buttonIconColor'], expected_ink)
				self.assertEqual(palette['brandTextColor'], palette['themeHighlight'])
				self.assertEqual(palette['timelineColor'], palette['themeAccent'])

	def test_legacy_saved_theme_gains_highlight_without_disappearing(self):
		with tempfile.TemporaryDirectory() as folder:
			settings = QSettings(str(Path(folder) / 'settings.ini'), QSettings.IniFormat)
			preset = default_color_themes()[0] | {'id': 'legacy', 'name': 'Old album', 'preserve_palette': True}
			preset['colors'].pop('theme_highlight_color')
			settings.setValue('saved_color_themes', json.dumps([preset]))
			loaded = saved_color_themes(settings)
			self.assertEqual(len(loaded), 3)
			self.assertEqual(loaded[2]['colors']['theme_highlight_color'], preset['colors']['theme_brand_text_color'])
			self.assertTrue(loaded[2]['preserve_palette'])

	def test_editable_color_rows_and_old_theme_survive_apply_restart(self):
		with tempfile.TemporaryDirectory() as folder:
			settings = QSettings(str(Path(folder) / 'settings.ini'), QSettings.IniFormat)
			for _, _, key, _, default in COLOR_SETTINGS:
				settings.setValue(key, default)
			settings.setValue('theme_timeline_color', '#ff00aa')
			settings.setValue('artwork_theme_enabled', False)
			dialog = ThemeSettingsDialog(settings)
			exposed = {control.objectName() for control in dialog.colors.values() if control in dialog.option_labels}
			self.assertEqual(exposed, PRIMARY_COLOR_KEYS)
			self.assertTrue(all(dialog.colors[key].isEnabled() for key in exposed))
			dialog.colors['theme_accent_color'].set_color('#2e8aab')
			dialog.colors['theme_brand_text_color'].set_color('#cfe10e')
			dialog.apply()
			self.assertEqual(settings.value('theme_timeline_color'), settings.value('theme_highlight_color'))
			colors = custom_color_settings(settings)
			self.assertEqual(colors['theme_brand_text_color'], colors['theme_accent_color'])
			dialog.accept()
			restored = ThemeSettingsDialog(QSettings(settings.fileName(), QSettings.IniFormat))
			self.assertEqual(restored.colors['theme_accent_color'].color().name(), colors['theme_accent_color'])
			restored.artwork_theme.setChecked(True)
			self.assertTrue(all(not restored.colors[key].isEnabled() for key in PRIMARY_COLOR_KEYS))
			self.assertFalse(restored.saved_theme_choice.isEnabled())
			restored.reject()

if __name__ == '__main__':
	unittest.main()
