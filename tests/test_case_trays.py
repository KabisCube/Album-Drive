"""Accent trays are reserved for neutral covers with isolated vivid colors."""
from io import BytesIO
import unittest
from PIL import Image, ImageDraw
from case_shell import artwork_tray_color
from PySide6.QtGui import QColor


def cover(background, blocks=()):
    image = Image.new('RGB', (100, 100), background)
    draw = ImageDraw.Draw(image)
    for rect, color in blocks:
        draw.rectangle(rect, fill=color)
    data = BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


class CaseTrayTests(unittest.TestCase):
    def test_neutral_and_fully_colorful_covers_keep_black_trays(self):
        for color in ('#242424', '#efefef', '#e02020', '#3030ea'):
            self.assertIsNone(artwork_tray_color(cover(color)))
        self.assertIsNone(artwork_tray_color(b'invalid image'))

    def test_one_or_two_isolated_colors_pick_the_main_ink(self):
        for blocks in (
            (((0, 0, 29, 99), '#f0c020'),),
            (((0, 0, 29, 99), '#f0c020'), ((30, 0, 39, 99), '#e02030')),
        ):
            selected = QColor(artwork_tray_color(cover('#a0a0a0', blocks)))
            self.assertTrue(selected.isValid())
            self.assertLess(abs(selected.hueF() - QColor('#f0c020').hueF()), .025)

    def test_broad_palette_and_tiny_accents_keep_black_trays(self):
        blocks = tuple(((index * 10, 0, index * 10 + 9, 99), color)
                       for index, color in enumerate(('#ee2020', '#20ee20', '#2020ee', '#eee020', '#ee20ee')))
        self.assertIsNone(artwork_tray_color(cover('#999999', blocks)))
        self.assertIsNone(artwork_tray_color(cover('#999999', (((0, 0, 1, 10), '#ee2020'),))))
