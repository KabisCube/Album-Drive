"""Brightness preferences preserve cover hues and readable application colors."""

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

from app_theme import artwork_theme_colors
from open_case import artwork_accent_palette, artwork_palette, color_contrast, readable_paper_text
from theme_settings import ThemeSettingsDialog


def cover(*colors):
    image = Image.new('RGB', (len(colors), 1))
    image.putdata(colors)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


class ArtworkModeTests(unittest.TestCase):
    def test_small_vivid_regions_survive_a_busy_photographic_palette(self):
        for vivid, expected_hue in (('#ec981f', .1), ('#e5d715', .155)):
            image = Image.new('RGB', (128, 128))
            image.putdata([(5 + x * 80 // 127, 45 + y * 100 // 127, 90 + (x + y) * 120 // 254)
                           for y in range(128) for x in range(128)])
            image.paste(vivid, (20, 55, 28, 63))
            output = BytesIO()
            image.save(output, format='PNG')
            for mode in ('any', 'dark', 'light'):
                accent = QColor(artwork_theme_colors(output.getvalue(), mode)['themeHighlight'])
                self.assertLess(abs(accent.hslHueF() - expected_hue), .025)
                self.assertGreater(accent.hslSaturationF(), .7)

    def test_small_vivid_details_supply_the_accent_without_recoloring_it(self):
        for vivid in ('#f87913', '#f1de15'):
            for background in ('#283943', '#d4cebe'):
                image = Image.new('RGB', (64, 64), background)
                image.paste('#777c7d', (0, 0, 16, 64))
                image.paste(vivid, (30, 30, 38, 38))
                image.putpixel((60, 60), (255, 0, 255))
                output = BytesIO()
                image.save(output, format='PNG')
                colors = artwork_theme_colors(output.getvalue())
                accent = QColor(colors['themeHighlight'])
                self.assertEqual(accent.name(), vivid)
                self.assertGreater(accent.hslSaturationF(), .8)
                self.assertEqual(colors['brandTextColor'], accent.name())
                self.assertEqual(colors['headingTextColor'], accent.name())
                self.assertGreaterEqual(color_contrast(accent, QColor('#101010')), 4.5)
                self.assertNotIn(vivid, [color.name() for color in artwork_palette(output.getvalue())])

    def test_cover_colors_supply_ui_and_track_list_ink(self):
        artwork = cover(*([(18, 43, 64)] * 7 + [(226, 185, 107)] * 2 + [(156, 65, 47)]))
        for mode in ('any', 'dark', 'light'):
            colors = artwork_theme_colors(artwork, mode)
            for role in ('textColor', 'buttonTextColor', 'timelineTextColor', 'selectedTextColor', 'paperTextColor'):
                self.assertGreater(QColor(colors[role]).hslSaturationF(), .1, (mode, role, colors[role]))
        colors = artwork_theme_colors(artwork)
        self.assertEqual(colors['textColor'], '#e2b96b')
        self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']), QColor(colors['buttonTextColor'])), 4.5)
        foreground = readable_paper_text(QColor('#122b40'), QColor('#f4f4f4'), artwork_palette(artwork))
        self.assertEqual(foreground.name(), '#e2b96b')

    def test_any_preserves_existing_behavior(self):
        artwork = cover((25, 60, 100), (220, 180, 90))
        self.assertEqual(artwork_theme_colors(artwork), artwork_theme_colors(artwork, 'any'))
        self.assertEqual(artwork_theme_colors(artwork), artwork_theme_colors(artwork, 'invalid'))

    def test_simple_cover_keeps_sampled_pink_instead_of_darkening_it(self):
        for background in ((45, 228, 220), (24, 43, 71)):
            pink = (220, 109, 164)
            artwork = cover(*([background] * 60 + [(48, 51, 51)] * 25 + [pink] * 15))
            colors = artwork_theme_colors(artwork)
            sampled_pink = min(artwork_palette(artwork), key=lambda color:
                               sum((actual - expected) ** 2 for actual, expected in zip(color.getRgb()[:3], pink)))
            self.assertEqual(colors['themeAccent'], sampled_pink.name())
            self.assertTrue(all(abs(actual - expected) <= 2 for actual, expected in zip(sampled_pink.getRgb()[:3], pink)))
            self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']), QColor(colors['buttonTextColor'])), 4.5)
            self.assertIn(colors['themeHighlight'], [color.name() for color in artwork_accent_palette(artwork)])

    def test_readable_cover_neutral_wins_over_an_invented_color(self):
        artwork = cover(*([(45, 228, 220)] * 60 + [(48, 51, 51)] * 25 + [(220, 109, 164)] * 15))
        colors = artwork_theme_colors(artwork)
        charcoal = min(artwork_palette(artwork), key=lambda color: color.lightnessF()).name()
        self.assertEqual(colors['textColor'], charcoal)
        ink = QColor(colors['buttonTextColor'])
        self.assertLessEqual(ink.lightnessF(), QColor(charcoal).lightnessF())
        self.assertLess(abs(ink.hslHueF() - QColor(charcoal).hslHueF()), .02)
        self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']), ink), 4.5)

    def test_brightness_and_contrast_for_extreme_and_colored_covers(self):
        for rgb in ((0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
                    (0, 0, 255), (120, 120, 120), (240, 210, 80)):
            for mode in ('dark', 'light'):
                with self.subTest(rgb=rgb, mode=mode):
                    colors = artwork_theme_colors(cover(rgb), mode)
                    background = QColor(colors['themeBackground'])
                    if mode == 'dark':
                        self.assertLessEqual(background.lightnessF(), .455)
                    else:
                        self.assertGreaterEqual(background.lightnessF(), .645)
                    for surface in (background, background.darker(120), background.darker(130)):
                        self.assertGreaterEqual(color_contrast(surface, QColor(colors['textColor'])), 4.5)
                    self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']),
                                                          QColor(colors['buttonTextColor'])), 4.5)
                    self.assertEqual(colors['brandTextColor'], colors['themeHighlight'])

    def test_prefers_existing_cover_shades(self):
        artwork = cover((30, 50, 70), (220, 230, 240))
        self.assertEqual(artwork_theme_colors(artwork, 'dark')['themeBackground'], '#1e3246')
        self.assertEqual(artwork_theme_colors(artwork, 'light')['themeBackground'], '#dce6f0')

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
                             ['any', 'dark', 'light'])
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
            self.assertFalse(dialog.artwork_theme_mode.isEnabled())
            dialog.restore_defaults()
            self.assertEqual(dialog.artwork_theme_mode.currentData(), 'any')
            self.assertTrue(dialog.artwork_theme_mode.isEnabled())
            dialog.apply()
            self.assertEqual(settings.value('artwork_theme_mode'), 'any')
            dialog.close()


if __name__ == '__main__':
    unittest.main()
