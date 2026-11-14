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

from app_theme import artwork_theme_colors, hue_gap, ink_reads, is_chromatic
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

    def test_small_vivid_details_survive_sampling_without_isolated_noise(self):
        for vivid in ('#f87913', '#f1de15'):
            for background in ('#283943', '#d4cebe'):
                image = Image.new('RGB', (64, 64), background)
                image.paste('#777c7d', (0, 0, 16, 64))
                image.paste(vivid, (30, 30, 38, 38))
                image.putpixel((60, 60), (255, 0, 255))
                output = BytesIO()
                image.save(output, format='PNG')
                details = [color.name() for color in artwork_accent_palette(output.getvalue())]
                self.assertIn(vivid, details)
                self.assertNotIn('#ff00ff', details)
                self.assertNotIn(vivid, [color.name() for color in artwork_palette(output.getvalue())])

    def test_cover_colors_supply_ui_and_track_list_ink(self):
        artwork = cover(*([(18, 43, 64)] * 7 + [(226, 185, 107)] * 2 + [(156, 65, 47)]))
        for mode in ('any', 'dark', 'light'):
            colors = artwork_theme_colors(artwork, mode)
            for role in ('textColor', 'buttonTextColor', 'timelineTextColor', 'selectedTextColor', 'paperTextColor'):
                self.assertGreater(QColor(colors[role]).hslSaturationF(), .1, (mode, role, colors[role]))
        colors = artwork_theme_colors(artwork)
        self.assertEqual(colors['textColor'], '#e2b96b')
        self.assertEqual(colors['buttonTextColor'], colors['themeBackgroundAccent'])
        self.assertGreaterEqual(color_contrast(QColor(colors['themeBackground']), QColor(colors['textColor'])), 4.5)
        foreground = readable_paper_text(QColor('#122b40'), QColor('#f4f4f4'), artwork_palette(artwork))
        self.assertEqual(foreground.name(), '#e2b96b')

    def test_any_preserves_existing_behavior(self):
        artwork = cover((25, 60, 100), (220, 180, 90))
        self.assertEqual(artwork_theme_colors(artwork), artwork_theme_colors(artwork, 'any'))
        self.assertEqual(artwork_theme_colors(artwork), artwork_theme_colors(artwork, 'invalid'))

    def test_simple_cover_keeps_pink_ink_and_highlight_hue(self):
        for background in ((45, 228, 220), (24, 43, 71)):
            pink = (220, 109, 164)
            artwork = cover(*([background] * 60 + [(48, 51, 51)] * 25 + [pink] * 15))
            colors = artwork_theme_colors(artwork)
            sampled_pink = min(artwork_palette(artwork), key=lambda color:
                               sum((actual - expected) ** 2 for actual, expected in zip(color.getRgb()[:3], pink)))
            self.assertTrue(all(abs(actual - expected) <= 2 for actual, expected in zip(sampled_pink.getRgb()[:3], pink)))
            # The icon keeps the cover's pink hue, shaded only as far as it must be to read on the button.
            ink = QColor(colors['buttonTextColor'])
            self.assertLess(hue_gap(ink, sampled_pink), .02)
            self.assertTrue(ink_reads(QColor(colors['themeAccent']), ink))
            self.assertLess(hue_gap(QColor(colors['themeHighlight']), sampled_pink), .02)
            self.assertEqual(colors['headingTextColor'], colors['textColor'])

    def test_readable_cover_neutral_supplies_main_text(self):
        artwork = cover(*([(45, 228, 220)] * 60 + [(48, 51, 51)] * 25 + [(220, 109, 164)] * 15))
        colors = artwork_theme_colors(artwork)
        charcoal = min(artwork_palette(artwork), key=lambda color: color.lightnessF())
        text = QColor(colors['textColor'])
        self.assertTrue(all(abs(actual - expected) <= 2 for actual, expected in
                            zip(text.getRgb()[:3], charcoal.getRgb()[:3])))
        self.assertLess(hue_gap(text, charcoal), .02)
        self.assertGreaterEqual(color_contrast(QColor(colors['themeBackground']), text), 4.5)

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
                    # Single-color covers stay close to the artwork instead of forcing full contrast.
                    self.assertGreaterEqual(color_contrast(background, QColor(colors['textColor'])), 1.9)
                    self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']),
                                                          QColor(colors['buttonTextColor'])), 1.5)
                    self.assertEqual(colors['brandTextColor'], colors['themeHighlight'])

    def test_low_color_covers_get_gentle_distinct_shades_of_the_artwork(self):
        roles = ('themeBackground', 'textColor', 'themeAccent', 'themeHighlight', 'themeBackgroundAccent', 'buttonFill')
        for rgb in ((157, 151, 139), (128, 128, 128), (0, 0, 0), (255, 255, 255), (192, 48, 32),
                    (16, 24, 64), (242, 239, 223), (38, 34, 30)):
            for mode in ('any', 'dark', 'light'):
                with self.subTest(rgb=rgb, mode=mode):
                    colors = artwork_theme_colors(cover(rgb), mode)
                    self.assertEqual(len({colors[role] for role in roles}), len(roles))
                    background = QColor(colors['themeBackground'])
                    # Icons may leave the gentle range: they must read on the button first.
                    lightness = [QColor(colors[role]).lightnessF() for role in roles if role != 'themeBackgroundAccent']
                    self.assertTrue(ink_reads(QColor(colors['themeAccent']), QColor(colors['themeBackgroundAccent'])))
                    self.assertLessEqual(max(abs(level - background.lightnessF()) for level in lightness), .51)
                    self.assertGreaterEqual(color_contrast(background, QColor(colors['textColor'])), 1.9)
                    if background.hslSaturationF() > .1:
                        hue_gap = abs(QColor(colors['textColor']).hslHueF() - background.hslHueF())
                        self.assertLess(min(hue_gap, 1 - hue_gap), .02, 'shades keep the album hue')

    def test_five_real_colors_are_used_as_they_are_and_flip_for_dark(self):
        wanted = ('#fadec8', '#56222e', '#897091', '#e06869', '#f59d89')
        artwork = cover(*[QColor(value).getRgb()[:3] for value in
                          [wanted[0]] * 62 + [wanted[1]] * 14 + [wanted[4]] * 12 + [wanted[3]] * 6 + [wanted[2]] * 6])
        for mode in ('any', 'light'):
            colors = artwork_theme_colors(artwork, mode)
            self.assertEqual((colors['themeBackground'], colors['textColor']), wanted[:2])
            self.assertEqual({colors['themeAccent'], colors['themeHighlight']}, {wanted[2], wanted[3]})
            # The coral icon keeps its hue, made paler only as far as it must be to read on the button.
            ink = QColor(colors['themeBackgroundAccent'])
            self.assertLess(hue_gap(ink, QColor(wanted[4])), .02)
            self.assertTrue(ink_reads(QColor(colors['themeAccent']), ink))
        dark = artwork_theme_colors(artwork, 'dark')
        self.assertEqual((dark['themeBackground'], dark['textColor']), (wanted[1], wanted[0]))
        self.assertEqual(dark['paperBackgroundColor'], wanted[1])

    def test_four_color_covers_never_invent_a_lighter_color(self):
        image = Image.new('RGB', (256, 256), '#e4d6bc')
        image.paste('#284038', (10, 10, 110, 90))
        image.paste('#a8a453', (120, 10, 220, 110))
        image.paste('#6d775f', (10, 120, 90, 200))
        output = BytesIO()
        image.save(output, format='PNG')
        for mode in ('any', 'light', 'dark'):
            colors = artwork_theme_colors(output.getvalue(), mode)
            for role in ('themeHighlight', 'themeAccent', 'themeBackgroundAccent', 'buttonFill'):
                with self.subTest(mode=mode, role=role, value=colors[role]):
                    self.assertLessEqual(QColor(colors[role]).lightnessF(), .87)

    def test_never_pure_black_or_white(self):
        for rgb in ((0, 0, 0), (255, 255, 255)):
            for mode in ('any', 'dark', 'light'):
                colors = artwork_theme_colors(cover(rgb, (128, 128, 128)), mode)
                for value in colors.values():
                    self.assertNotIn(value, ('#000000', '#ffffff'))
        artwork = cover(*([(0, 0, 0)] * 50 + [(255, 255, 255)] * 20 + [(200, 40, 40)] * 15
                          + [(40, 80, 200)] * 10 + [(240, 200, 60)] * 5))
        colors = artwork_theme_colors(artwork)
        self.assertGreaterEqual(QColor(colors['themeBackground']).lightnessF(), .115)
        self.assertLess(QColor(colors['textColor']).lightnessF(), .97)

    def test_accent_is_always_the_most_saturated_pick(self):
        artwork = cover(*([(232, 217, 190)] * 60 + [(14, 72, 78)] * 18 + [(84, 176, 180)] * 12
                          + [(133, 154, 138)] * 6 + [(180, 190, 170)] * 4))
        colors = artwork_theme_colors(artwork)
        vividness = lambda value: max(QColor(value).getRgb()[:3]) - min(QColor(value).getRgb()[:3])
        self.assertGreaterEqual(vividness(colors['themeHighlight']), vividness(colors['themeAccent']))
        self.assertGreaterEqual(vividness(colors['themeHighlight']), vividness(colors['themeBackgroundAccent']))

    def test_small_vivid_pop_becomes_the_accent(self):
        muted = ('#e3d5bb', '#30453c', '#9f9b60', '#818a63', '#e5c38e')
        image = Image.new('RGB', (256, 256), muted[0])
        for index, (height, value) in enumerate(((60, muted[1]), (50, muted[2]), (40, muted[3]), (30, muted[4]))):
            image.paste(value, (index * 50, 0, index * 50 + 46, height))
        image.paste('#f8883a', (10, 190, 40, 220))
        image.paste('#f8b055', (50, 190, 80, 220))
        output = BytesIO()
        image.save(output, format='PNG')
        accent = QColor(artwork_theme_colors(output.getvalue())['themeHighlight'])
        self.assertLess(hue_gap(accent, QColor('#f99a5a')), .03, accent.name())
        self.assertGreater(accent.hslSaturationF(), .8)

    def test_fine_line_covers_keep_their_real_mid_tones_for_buttons(self):
        image = Image.new('RGB', (256, 256), (250, 218, 195))
        image.paste((243, 154, 135), (20, 20, 110, 110))
        for x in range(0, 256, 6):
            image.paste((91, 33, 46), (x, 120, x + 2, 256))
        output = BytesIO()
        image.save(output, format='PNG')
        colors = artwork_theme_colors(output.getvalue())
        accent = QColor(colors['themeHighlight'])
        self.assertTrue(.3 <= accent.lightnessF() <= .8, accent.name())
        for role in ('themeAccent', 'buttonFill', 'themeBackgroundAccent'):
            self.assertGreaterEqual(QColor(colors[role]).lightnessF(), .2, role)
        self.assertGreaterEqual(color_contrast(QColor(colors['themeAccent']), QColor(colors['buttonTextColor'])), 4.5)

    def test_every_picked_hue_comes_from_the_album(self):
        covers = (cover(*([(38, 191, 224)] * 70 + [(240, 240, 235)] * 30)),
                  cover(*([(192, 48, 32)] * 60 + [(240, 210, 80)] * 25 + [(20, 60, 40)] * 15)),
                  cover(*([(120, 40, 140)] * 50 + [(200, 170, 210)] * 50)),
                  cover(*([(45, 228, 220)] * 60 + [(48, 51, 51)] * 25 + [(220, 109, 164)] * 15)))
        for artwork in covers:
            sources = artwork_palette(artwork, colors=32, minimum=.002) + artwork_accent_palette(artwork)
            hues = [color for color in sources if is_chromatic(color)]
            for mode in ('any', 'dark', 'light'):
                colors = artwork_theme_colors(artwork, mode)
                for role, value in colors.items():
                    with self.subTest(mode=mode, role=role, value=value):
                        color = QColor(value)
                        if is_chromatic(color):
                            self.assertLessEqual(min(hue_gap(color, hue) for hue in hues), .05)

    def test_single_hue_covers_stay_on_their_hue_and_side(self):
        artwork = cover(*([(38, 191, 224)] * 80 + [(123, 203, 220)] * 12 + [(194, 217, 222)] * 8))
        colors = artwork_theme_colors(artwork)
        background = QColor(colors['themeBackground'])
        self.assertGreater(QColor(colors['textColor']).lightnessF(), background.lightnessF(), 'a pale cover keeps pale text')
        for role in ('textColor', 'themeAccent', 'themeHighlight', 'themeBackgroundAccent', 'buttonFill'):
            color = QColor(colors[role])
            gap = abs(color.hslHueF() - background.hslHueF())
            self.assertLess(min(gap, 1 - gap), .04, role)
            self.assertGreater(color.lightnessF(), .18, role)

    def test_track_list_paper_follows_brightness_with_album_colors(self):
        artwork = cover((240, 210, 80), (40, 90, 120))
        for mode, low, high in (('dark', 0, .455), ('light', .645, 1)):
            with self.subTest(mode=mode):
                colors = artwork_theme_colors(artwork, mode)
                paper = QColor(colors['paperBackgroundColor'])
                self.assertTrue(low <= paper.lightnessF() <= high, paper.name())
                self.assertGreaterEqual(color_contrast(paper, QColor(colors['paperTextColor'])), 1.9)
        single = cover((240, 210, 80))
        paper = QColor(artwork_theme_colors(single, 'dark')['paperBackgroundColor'])
        self.assertLess(abs(paper.hslHueF() - QColor(240, 210, 80).hslHueF()), .02, 'paper keeps the album hue')
        self.assertEqual(artwork_theme_colors(artwork, 'any')['paperBackgroundColor'], artwork_palette(artwork)[0].name())

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
                             ['Any', 'Dark', 'Light'])
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
