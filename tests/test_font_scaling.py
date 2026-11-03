import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QSettings
from themes import FONT_BASE_SIZES, FONT_SCALE_KEYS, MAX_FONT_SIZE, font_sizes, migrate_font_settings


class FontScalingTests(unittest.TestCase):
    def test_default_proportions_and_master_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
            migrate_font_settings(settings)
            self.assertEqual(font_sizes(settings), FONT_BASE_SIZES)
            settings.setValue('main_font_size', 100)
            sizes = font_sizes(settings)
            self.assertEqual(sizes['main_font_size'], MAX_FONT_SIZE)
            self.assertLessEqual(sizes['button_font_size'], MAX_FONT_SIZE)
            self.assertEqual(sizes['heading_font_size'], round(26 * MAX_FONT_SIZE / 16))

    def test_fine_tuning_changes_only_one_role(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
            migrate_font_settings(settings)
            before = font_sizes(settings)
            settings.setValue(FONT_SCALE_KEYS['folder_font_size'], 125)
            after = font_sizes(settings)
            self.assertEqual(after['folder_font_size'], round(14 * 1.25))
            self.assertEqual({key: value for key, value in before.items() if key != 'folder_font_size'},
                             {key: value for key, value in after.items() if key != 'folder_font_size'})

    def test_legacy_values_migrate_without_resetting_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
            for key, value in FONT_BASE_SIZES.items():
                settings.setValue(key, value)
            settings.setValue('main_font_size', 18)
            migrate_font_settings(settings)
            sizes = font_sizes(settings)
            for key, value in FONT_BASE_SIZES.items():
                if key not in ('main_font_size', 'menu_font_size', 'secondary_font_size'):
                    self.assertEqual(sizes[key], value, key)
            settings.setValue(FONT_SCALE_KEYS['logo_font_size'], 110)
            migrate_font_settings(settings)
            self.assertEqual(settings.value(FONT_SCALE_KEYS['logo_font_size'], type=int), 110)
