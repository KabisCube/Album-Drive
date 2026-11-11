"""Dark rails remain visible and theme extremes stay comfortable."""
import unittest
from PySide6.QtGui import QColor
from color_rules import artwork_text_color, color_contrast, comfortable_color, comfortable_surface, slider_rail, timeline_colors
from app_theme import simplify_theme_colors, soften_theme_colors


class ColorRuleTests(unittest.TestCase):
    def test_timeline_uses_opposite_surface_for_timestamp(self):
        values = ('#393939', '#888888', '#000000', '#ffffff', '#f2efdf', '#162b47', '#e7c977')
        for background in values:
            for accent in (*values, slider_rail(background).lighter(125).name()):
                with self.subTest(background=background, accent=accent):
                    rail, fill, filled_text, unfilled_text = timeline_colors(background, accent)
                    self.assertEqual(fill, QColor(accent))
                    self.assertEqual(rail, slider_rail(background))
                    self.assertEqual(filled_text, rail)
                    self.assertEqual(unfilled_text, fill)

    def test_timeline_preserves_explicit_background_accent(self):
        background = QColor('#6b6e54')
        background_accent = QColor('#303322')
        rail, fill, filled_text, unfilled_text = timeline_colors(background, '#ffb653', background_accent)
        self.assertEqual(fill.name(), '#ffb653')
        self.assertEqual(rail, background_accent)
        self.assertEqual(filled_text, rail)
        self.assertEqual(unfilled_text, fill)

    def test_black_control_faces_leave_room_for_darker_depth(self):
        face = comfortable_surface('#000000')
        self.assertEqual(face.name(), '#242424')
        self.assertLess(face.darker(125).lightnessF(), face.lightnessF())
        self.assertGreaterEqual(face.red() - face.darker(125).red(), 6)
        self.assertEqual(comfortable_surface('#ffffff').name(), '#f4f4f4')

    def test_soft_ink_stays_readable_without_absolute_black_or_white(self):
        for source in ('#000000', '#050505', '#787878', '#857532', '#ffffff'):
            face = comfortable_surface(source)
            ink = artwork_text_color((face,), (source,))
            self.assertNotIn(ink.name(), ('#000000', '#ffffff'))
            self.assertGreaterEqual(color_contrast(face, ink), 4.5)

    def test_preserved_theme_colors_also_soften_extremes(self):
        colors = dict(themeBackground='#000000', themeAccent='#000000', themeHighlight='#000000',
                      buttonFill='#ffffff', textColor='#ffffff', buttonTextColor='#ffffff')
        result = soften_theme_colors(colors)
        self.assertTrue(all(value not in ('#000000', '#ffffff') for value in result.values()))
        self.assertEqual(result['themeAccent'], '#242424')
        self.assertEqual(result['themeHighlight'], '#242424')
        self.assertEqual(result, soften_theme_colors(result))

    def test_cover_ink_wins_over_readable_white(self):
        background = QColor('#122b40')
        result = artwork_text_color((background,), ('#f4f4f4', '#e2b96b', '#9c412f'))
        self.assertEqual(result.name(), '#e2b96b')
        self.assertGreaterEqual(color_contrast(background, result), 4.5)

    def test_unreadable_cover_ink_keeps_its_hue(self):
        source = QColor('#e2b96b')
        result = artwork_text_color((QColor('#f2efdf'),), (source,))
        self.assertNotIn(result.name(), ('#101010', '#f4f4f4'))
        self.assertLess(abs(source.hslHueF() - result.hslHueF()), .01)
        self.assertGreaterEqual(color_contrast(QColor('#f2efdf'), result), 4.5)

    def test_extremes_and_dark_rails(self):
        self.assertEqual(comfortable_color('#000000').name(), '#101010')
        self.assertEqual(comfortable_color('#ffffff').name(), '#f4f4f4')
        for value in ('#000000', '#101010', '#151515'):
            self.assertGreater(slider_rail(value).lightnessF(), comfortable_color(value).lightnessF())
        last = None
        for channel in range(16, 80):
            rail = slider_rail(QColor(channel, channel, channel)).red()
            if last is not None:
                self.assertLessEqual(abs(rail - last), 2)
            last = rail

    def test_all_roles_are_softened(self):
        from themes import COLOR_SETTINGS
        for value in ('#000000', '#ffffff'):
            palette = simplify_theme_colors({prop: value for _, _, _, prop, _ in COLOR_SETTINGS})
            for color in palette.values():
                self.assertNotIn(QColor(color).name(), ('#000000', '#ffffff'))

    def test_rails_contrast_with_every_surface(self):
        values = ['#3b2422', '#393939', '#f2efdf', '#162b47', '#e7c977']
        values.extend(QColor(channel, channel, channel).name() for channel in range(256))
        values.extend(QColor.fromHsl(hue, saturation, lightness).name()
                      for hue in range(0, 360, 30) for saturation in (80, 180, 255)
                      for lightness in (20, 60, 120, 180, 235))
        for value in values:
            background = QColor(value)
            rail = slider_rail(value)
            self.assertGreaterEqual(color_contrast(background, rail), 2.24, value)
            if background.hslSaturationF() > .1:
                self.assertLess(abs(background.hslHueF() - rail.hslHueF()), .02, value)
