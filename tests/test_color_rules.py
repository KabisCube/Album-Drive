"""Timeline colors use the theme's own colors."""
import unittest
from PySide6.QtGui import QColor
from color_rules import timeline_colors
from app_theme import simplify_theme_colors


class ColorRuleTests(unittest.TestCase):
    def test_timeline_preserves_explicit_background_accent(self):
        background_accent = QColor('#303322')
        rail, fill, filled_text, unfilled_text = timeline_colors('#6b6e54', '#ffb653', background_accent)
        self.assertEqual(fill.name(), '#ffb653')
        self.assertEqual(rail, background_accent)
        self.assertEqual(filled_text, rail)
        self.assertEqual(unfilled_text, fill)

    def test_theme_colors_are_never_tuned(self):
        colors = dict(themeBackground='#000000', themeAccent='#ffffff', themeHighlight='#123456',
                      textColor='#ffffff', themeBackgroundAccent='#000001', buttonFill='#777777')
        result = simplify_theme_colors(colors)
        for key in ('themeBackground', 'themeAccent', 'themeHighlight', 'textColor', 'themeBackgroundAccent'):
            self.assertEqual(result[key], colors[key])
        self.assertEqual(result['buttonFill'], '#ffffff')
        self.assertEqual(result['folderArrowColor'], '#ffffff')
