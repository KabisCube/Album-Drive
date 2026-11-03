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
from app_theme import application_highlight, artwork_theme_colors, simplify_theme_colors
from open_case import color_contrast
from themes import PRIMARY_COLOR_KEYS, COLOR_SETTINGS
from theme_settings import ThemeSettingsDialog, custom_color_settings, default_color_theme, saved_color_themes


class SimplePaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_buttons_prefer_another_hue_even_if_it_matches_text(self):
        background, brown, clouds, accent = map(QColor, ('#cea968', '#7c6444', '#091619', '#eb553f'))
        selected = application_highlight(background, accent, clouds, (background, brown, clouds))
        self.assertEqual(selected.name(), clouds.name())
        self.assertEqual(background.name(), '#cea968')

    def test_monochrome_buttons_can_still_use_another_shade(self):
        selected = application_highlight(QColor('#202020'), QColor('#eeeeee'), QColor('#eeeeee'),
                                         tuple(map(QColor, ('#202020', '#787878', '#b0b0b0'))))
        self.assertLess(selected.hslSaturationF(), .01)
        self.assertGreaterEqual(color_contrast(QColor('#202020'), selected), 1.3)

    def test_another_hue_is_preferred_even_at_similar_brightness(self):
        background, brown, blue = map(QColor, ('#c2a879', '#80603e', '#80b3cc'))
        self.assertLess(color_contrast(background, blue), 1.3)
        selected = application_highlight(background, QColor('#f25b30'), QColor('#202020'),
                                         (background, brown, blue))
        self.assertEqual(selected.name(), blue.name())

    def test_dynamic_roles_share_highlight_and_remain_readable(self):
        for rgb in ((255, 255, 255), (0, 0, 0), (180, 90, 30), (20, 40, 180)):
            data = BytesIO()
            Image.new('RGB', (12, 12), rgb).save(data, format='PNG')
            for mode in ('any', 'dark', 'light'):
                colors = artwork_theme_colors(data.getvalue(), mode)
                roles = ('themeBackground', 'themeAccent', 'timelineColor', 'brandTextColor',
                         'buttonFill', 'textColor', 'buttonTextColor', 'buttonIconColor', 'folderArrowColor')
                self.assertLessEqual(len({colors[key] for key in roles}), 6)
                self.assertEqual(colors['brandTextColor'], colors['themeHighlight'])
                self.assertEqual(colors['headingTextColor'], colors['brandTextColor'])

    def test_buttons_use_readable_text_for_light_and_dark_surfaces(self):
        for fill in ('#eeeeee', '#111111', '#ac2614', '#2c80ee'):
            palette = simplify_theme_colors(dict(themeBackground='#202020', themeAccent='#cf8020',
                buttonFill=fill, textColor='#ffffff', brandTextColor='#cfdf0e'))
            self.assertGreaterEqual(color_contrast(QColor(palette['themeAccent']), QColor(palette['buttonTextColor'])), 4.5)
            self.assertEqual(palette['brandTextColor'], palette['themeHighlight'])
            self.assertEqual(palette['timelineColor'], palette['themeAccent'])

    def test_minor_cover_color_supplies_distinct_readable_highlight(self):
        image = Image.new('RGB', (100, 1))
        image.putdata([(32, 35, 43)] * 55 + [(199, 189, 174)] * 25
                      + [(220, 55, 88)] * 12 + [(112, 190, 186)] * 8)
        output = BytesIO()
        image.save(output, format='PNG')
        for mode in ('any', 'dark', 'light'):
            colors = artwork_theme_colors(output.getvalue(), mode)
            highlight = QColor(colors['themeHighlight'])
            self.assertNotEqual(colors['themeAccent'], colors['themeBackground'])
            self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']), QColor(colors['buttonTextColor'])), 4.5)
            self.assertEqual(colors['brandTextColor'], highlight.name())
            self.assertEqual(colors['headingTextColor'], colors['brandTextColor'])
        colors = artwork_theme_colors(output.getvalue(), 'dark')
        hue = QColor(colors['themeHighlight']).hslHueF()
        self.assertLess(min(abs(hue - 0.966), 1 - abs(hue - 0.966)), .03)

    def test_legacy_saved_theme_gains_highlight_without_disappearing(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / 'settings.ini'), QSettings.IniFormat)
            preset = default_color_theme() | {'id': 'legacy', 'name': 'Old album', 'preserve_palette': True}
            preset['colors'].pop('theme_highlight_color')
            settings.setValue('saved_color_themes', json.dumps([preset]))
            loaded = saved_color_themes(settings)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[1]['colors']['theme_highlight_color'], preset['colors']['theme_brand_text_color'])
            self.assertTrue(loaded[1]['preserve_palette'])

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
