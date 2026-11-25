"""
Five colors are picked once, in order:
1. Background: a color group that fills most of the artwork, otherwise the most used color
   on the theme's side (light or dark).
2. Text: the most used color on the other side that reads on the background.
3. Accent: the most saturated color that stands apart from the first two.
4. Button: a color apart from the others, preferring an unused hue.
5. Background accent: an artwork color that reads on the buttons and shows on the background.

When the artwork has nothing left that fits, a color is invented by mixing two already
picked colors, so it keeps the album's hues and stays within their lightness.
Differences between colors are measured in OKLab, where equal distances look about
equally different to the eye. Between two strong colors the tint gap has to grow with
their strength.
Skin tones are only picked when they cover over 20% of the artwork.
"""
import colorsys
from functools import lru_cache
from io import BytesIO

from PIL import Image
from PySide6.QtGui import QColor

from color_rules import color_contrast, relative_luminance
from themes import COLOR_SETTINGS, PANEL_SHADE

LIGHTNESS_RANGE = (.24, .96)
DARKEST_BACKGROUND = QColor('#2b0200').lightnessF()
DARKEST_GRAY_BACKGROUND = QColor('#1f1f1f').lightnessF()
MIDDLE_LOOK = .5
INVENTED_LIGHTNESS = {'light': .9, 'dark': .3}
CALM_CHROMA = 48
VIVID_CHROMA = 24
DISTINCT = .055
INVENTED_DISTINCT = .03
COLORFUL = .03
TINT_GAP = .06
TINT_SHARE = .5
MINIMUM_SHARE = .001
MAJORITY_SHARE = .53
DOMINANT_SHARE = .4
MEMBER_SHARE = .1
COLORFUL_DARK_SHARE = .05
PICK_SHARE = .0015
SKIN_SHARE = .15
SKIN_CHROMA = 110
PEACH_LIGHTNESS = .6
PEACH_CHROMA = 135
CORAL_CHROMA = 100
TEXT_CONTRAST = 4
PREFERRED_TEXT_CONTRAST = 4.5
BUTTON_CONTRAST = 1.1
BUTTON_ACCENT_CONTRAST = 1.5
INK_BUTTON_CONTRAST = 1.545
INVENTED_INK_BUTTON_CONTRAST = 1.75
INK_BACKGROUND_CONTRAST = 1.1
INK_PANEL_CONTRAST = 1.05
BUTTON_MIX = [step / 100 for step in range(40, 81)] + [step / 100 for step in range(39, 9, -1)]
INK_MIX = [step / 100 for step in range(2, 101)]

ROLES = ('themeBackground', 'textColor', 'themeHighlight', 'themeAccent', 'themeBackgroundAccent')
TEXT_KEYS = ('textColor', 'secondaryTextColor', 'folderArrowColor', 'headingTextColor', 'selectedTextColor',
			'timelineTextColor', 'paperTextColor')
INK_KEYS = ('themeBackgroundAccent', 'buttonTextColor', 'buttonIconColor', 'disabledTextColor')


def simplify_theme_colors(colors):
	colors = dict(colors)
	background = QColor(colors['themeBackground'])
	text = QColor(colors['textColor']).name()
	button = QColor(colors['themeAccent']).name()
	accent = QColor(colors.get('themeHighlight') or colors.get('brandTextColor') or '#cfe10e').name()
	ink = QColor(colors.get('themeBackgroundAccent') or text).name()
	colors.update({key: text for key in TEXT_KEYS})
	colors.update({key: ink for key in INK_KEYS})
	colors.update(themeBackground=background.name(), themeAccent=button, timelineColor=button, buttonFill=button,
				themeHighlight=accent, brandTextColor=accent, brandLineColor=background.darker(110).name())
	return colors


def simplify_color_settings(colors):
	palette = simplify_theme_colors({prop: colors.get(key, default)
									for _, _, key, prop, default in COLOR_SETTINGS})
	return {key: palette[prop] for _, _, key, prop, _ in COLOR_SETTINGS}


def cover_colors(artwork):
	try:
		with Image.open(BytesIO(artwork)) as image:
			rgba = image.convert('RGBA').resize((128, 128), Image.Resampling.NEAREST)
			data = rgba.get_flattened_data() if hasattr(rgba, 'get_flattened_data') else rgba.getdata()
			pixels = [pixel[:3] for pixel in data if pixel[3] >= 128]
	except (OSError, ValueError, Image.DecompressionBombError):
		return []
	groups = {}
	for rgb in pixels:
		hue, lightness, _ = colorsys.rgb_to_hls(*(channel / 255 for channel in rgb))
		spread = max(rgb) - min(rgb)
		key = (-1 if spread < 16 else int(hue * 24), int(lightness * 16), min(spread // 48, 3))
		groups.setdefault(key, []).append(rgb)
	colors = [(QColor(*(round(sum(rgb[channel] for rgb in group) / len(group)) for channel in range(3))),
			len(group) / len(pixels)) for group in groups.values() if len(group) >= len(pixels) * MINIMUM_SHARE]
	return sorted(colors, key=lambda entry: entry[1], reverse=True)


def skin_tone(color):
	hue = color.hslHueF() * 360
	if 20 <= hue <= 30 and VIVID_CHROMA <= chroma(color) <= PEACH_CHROMA and color.lightnessF() >= PEACH_LIGHTNESS:
		return True
	# Bright coral pinks are redder and stronger than skin.
	if (hue < 10 or hue >= 350) and chroma(color) >= CORAL_CHROMA and color.lightnessF() >= PEACH_LIGHTNESS:
		return False
	return (hue <= 28 or hue >= 350) and VIVID_CHROMA <= chroma(color) <= SKIN_CHROMA and color.lightnessF() >= .35


def without_rare_skin(cover):
	if total_share(entry for entry in cover if skin_tone(entry[0])) >= SKIN_SHARE:
		return cover
	return [entry for entry in cover if not skin_tone(entry[0])]


def total_share(entries):
	return sum(share for _, share in entries)


def chroma(color):
	return max(color.getRgb()[:3]) - min(color.getRgb()[:3])


def hue_family(color):
	return round(color.hslHueF() * 12) % 12


def shade(hue, saturation, lightness):
	return QColor(QColor.fromHslF(max(0, hue), saturation, lightness).name())


def mixed(first, second, amount):
	return QColor(*(round(a + (b - a) * amount) for a, b in zip(first.getRgb()[:3], second.getRgb()[:3])))


def mixes(first, second, amounts):
	return (mixed(first, second, amount) for amount in amounts)


@lru_cache(maxsize=4096)
def _oklab(rgb):
	red, green, blue = (channel / 3294.6 if channel <= 10 else ((channel / 255 + .055) / 1.055) ** 2.4
						for channel in rgb)
	long = (.4122214708 * red + .5363325363 * green + .0514459929 * blue) ** (1 / 3)
	medium = (.2119034982 * red + .6806995451 * green + .1073969566 * blue) ** (1 / 3)
	short = (.0883024619 * red + .2817188376 * green + .6299787005 * blue) ** (1 / 3)
	return (.2104542553 * long + .7936177850 * medium - .0040720468 * short,
			1.9779984951 * long - 2.4285922050 * medium + .4505937099 * short,
			.0259040371 * long + .7827717662 * medium - .8086757660 * short)


def oklab(color):
	return _oklab(color.getRgb()[:3])


def distance(first, second):
	return sum((a - b) ** 2 for a, b in zip(oklab(first), oklab(second))) ** .5


def colorfulness(color):
	_, a, b = oklab(color)
	return (a * a + b * b) ** .5


def tint_distance(first, second):
	(_, a, b), (_, c, d) = oklab(first), oklab(second)
	return ((a - c) ** 2 + (b - d) ** 2) ** .5


def perceived_lightness(color):
	luminance = relative_luminance(color)
	return (116 * luminance ** (1 / 3) - 16) / 100 if luminance > .008856 else 9.033 * luminance


def apart(color, picked, gap=DISTINCT):
	return all(distance(color, other) >= gap for other in picked)


def newness(color, picked):
	strength = colorfulness(color)
	if strength < COLORFUL:
		return .5
	nearest = min((tint_distance(color, other) / max(TINT_GAP, TINT_SHARE * min(strength, colorfulness(other)))
				for other in picked), default=1)
	return int(min(1, nearest) * 4) / 4


def new_hue(color, picked):
	return newness(color, picked) >= 1


def usable(color, bounds=LIGHTNESS_RANGE):
	return bounds[0] <= color.lightnessF() <= bounds[1]


def clamped(color, bounds=LIGHTNESS_RANGE):
	hue, saturation, lightness, _ = color.getHslF()
	level = min(bounds[1], max(bounds[0], lightness))
	if level == lightness:
		return QColor(color)
	return shade(hue, min(1, chroma(color) / 255 / max(.001, 1 - abs(2 * level - 1))), level)


def lifted(color, bounds=LIGHTNESS_RANGE):
	lightness = color.lightnessF()
	level = min(bounds[1], max(bounds[0], lightness))
	if level == lightness:
		return QColor(color)
	scale = level / max(lightness, 1 / 510)
	return QColor(*(min(255, round(max(channel, .5) * scale)) for channel in color.getRgb()[:3]))


def theme_side(cover, mode):
	if mode in ('light', 'dark'):
		return mode
	for side in ('light', 'dark'):
		if majority(cover, side):
			return side
	return 'light' if cover[0][0].lightnessF() >= .5 else 'dark'


def in_half(color, side):
	return color.lightnessF() >= .5 if side == 'light' else color.lightnessF() <= .5


def pick_background(cover, side):
	bounds = (DARKEST_BACKGROUND, LIGHTNESS_RANGE[1]) if side == 'dark' else LIGHTNESS_RANGE
	background = next(color for color in (pick(cover, side, bounds) for pick in
										(majority_background, dominant_background, voted_background, invented_background))
					if color is not None)
	if chroma(background) < VIVID_CHROMA and background.lightnessF() < DARKEST_GRAY_BACKGROUND:
		return lifted(background, (DARKEST_GRAY_BACKGROUND, LIGHTNESS_RANGE[1]))
	return background


def side_groups(cover, side):
	groups = {}
	for color, share in cover:
		looks = perceived_lightness(color)
		if looks >= MIDDLE_LOOK if side == 'light' else looks < MIDDLE_LOOK:
			key = -1 if chroma(color) < VIVID_CHROMA else hue_family(color)
			groups.setdefault(key, []).append((color, share))
	return groups


def majority(cover, side):
	members = max(side_groups(cover, side).values(), key=total_share, default=[])
	return members if total_share(members) >= MAJORITY_SHARE else []


def group_background(members, bounds):
	top, top_share = members[0]
	if usable(top, bounds):
		return top
	inside = [color for color, share in members if usable(color, bounds) and share >= top_share * MEMBER_SHARE]
	return inside[0] if inside else lifted(top, bounds)


def majority_background(cover, side, bounds):
	members = majority(cover, side)
	return group_background(members, bounds) if members else None


def dominant_background(cover, side, bounds):
	dominant, share = cover[0]
	if share >= DOMINANT_SHARE and usable(dominant, bounds) and in_half(dominant, side):
		return dominant
	families = {}
	for color, share in cover:
		if chroma(color) >= VIVID_CHROMA:
			families.setdefault(hue_family(color), []).append((color, share))
	family = max(families.values(), key=total_share, default=[])
	total = total_share(family)
	if total < DOMINANT_SHARE:
		return None
	looks = sum(perceived_lightness(color) * share for color, share in family) / total
	fits = looks >= MIDDLE_LOOK if side == 'light' else looks < MIDDLE_LOOK
	color = clamped(family[0][0], bounds)
	return color if fits and in_half(color, side) else None


def voted_background(cover, side, bounds):
	groups = side_groups(cover, side)
	if not groups:
		return None
	members = max(groups.values(), key=total_share)
	colorful = max((entries for key, entries in groups.items() if key >= 0), key=total_share, default=[])
	if side == 'dark' and total_share(colorful) >= COLORFUL_DARK_SHARE:
		members = colorful
	return group_background(members, bounds)


def invented_background(cover, side, bounds):
	extreme = max(cover, key=lambda entry: entry[0].lightnessF() if side == 'light' else -entry[0].lightnessF())[0]
	hue, saturation, _, _ = extreme.getHslF()
	return clamped(shade(hue, saturation, INVENTED_LIGHTNESS[side]), bounds)


def pick_text(cover, background):
	def reads(color, minimum=TEXT_CONTRAST):
		return color_contrast(background, color) >= minimum

	def calm(color):
		return chroma(color) <= CALM_CHROMA

	def muted(color):
		return chroma(color) <= 2 * CALM_CHROMA

	colors = [color for color, _ in cover]
	tiers = ((calm, True, PREFERRED_TEXT_CONTRAST), (calm, True, TEXT_CONTRAST), (calm, False, TEXT_CONTRAST),
			(muted, True, TEXT_CONTRAST), (muted, False, TEXT_CONTRAST))
	for quiet, inside, minimum in tiers:
		found = [color for color in colors
				if quiet(color) and (usable(color) or not inside) and reads(clamped(color), minimum)]
		if found:
			return clamped(found[0] if quiet is calm else min(found, key=chroma))
	beyond = [color for color in colors if muted(color) and reads(color)]
	if beyond:
		color = min(beyond, key=lambda option: (not calm(option), -color_contrast(background, option)))
		hue, saturation, level, _ = color.getHslF()
		target = clamped(color).lightnessF()
		steps = (shade(hue, saturation, target + (level - target) * step / 100) for step in range(101))
		return next((step for step in steps if reads(step, PREFERRED_TEXT_CONTRAST)), color)
	if chroma(background) < VIVID_CHROMA:
		vivid = [color for color in colors if usable(color) and reads(color)]
		if vivid:
			return max(vivid, key=lambda option: color_contrast(background, option))
	hue, saturation, _, _ = background.getHslF()
	darker = relative_luminance(background) >= .18
	shades = [shade(hue, saturation, step / 100) for step in (range(50, -1, -1) if darker else range(50, 101))]
	readable = [color for color in shades if reads(color)]
	return next((color for color in readable if usable(color)), readable[0] if readable else shades[-1])


def pick_accent(cover, background, text):
	picked = (background, text)
	fits = [(color, share) for color, share in cover if usable(color) and apart(color, picked)]
	if fits:
		return max(fits, key=lambda entry: (new_hue(entry[0], picked), chroma(entry[0]) ** 2 * entry[1] ** .25))[0]
	return next((color for color in mixes(background, text, BUTTON_MIX) if apart(color, picked, INVENTED_DISTINCT)),
				mixed(background, text, .5))


def pick_button(cover, background, text, accent):
	picked = (background, text, accent)

	def fits(color, invented=False):
		return (apart(color, picked, INVENTED_DISTINCT if invented else DISTINCT)
				and color_contrast(background, color) >= BUTTON_CONTRAST
				and color_contrast(accent, color) >= BUTTON_ACCENT_CONTRAST)

	found = [color for color, share in cover if share >= PICK_SHARE and usable(color) and fits(color)]
	if found:
		return max(found, key=lambda color: (new_hue(color, picked), newness(color, picked)))
	return next((color for color in mixes(background, text, BUTTON_MIX) if fits(color, True)),
				mixed(background, text, .5))


def pick_background_accent(cover, background, text, accent, button):
	picked = (background, text, accent, button)
	panel = background.darker(PANEL_SHADE)
	real_button = any(button == color for color, _ in cover)

	def fits(color, invented=False):
		contrast = INVENTED_INK_BUTTON_CONTRAST if invented or not real_button else INK_BUTTON_CONTRAST
		return (apart(color, picked, INVENTED_DISTINCT if invented else DISTINCT)
				and color_contrast(button, color) >= contrast
				and color_contrast(background, color) >= INK_BACKGROUND_CONTRAST
				and color_contrast(panel, color) >= INK_PANEL_CONTRAST)

	found = [color for color, share in cover if share >= PICK_SHARE and usable(color) and fits(color)]
	def between(toward):
		levels = sorted((background.lightnessF(), toward.lightnessF()))
		return [color for color in found if levels[0] <= color.lightnessF() <= levels[1]]

	inside = between(button)
	if inside:
		return max(inside, key=lambda color: (new_hue(color, picked), newness(color, picked),
											color_contrast(button, color)))
	# The cover is sorted by share, so the first of equals is the most common.
	inside = between(text)
	if inside:
		return max(inside, key=lambda color: new_hue(color, picked))
	if found and chroma(background) < VIVID_CHROMA and chroma(text) > 2 * CALM_CHROMA:
		return max(found, key=lambda color: (new_hue(color, picked), color_contrast(button, color)))
	for toward in (button, text):
		invented = next((color for color in mixes(background, toward, INK_MIX) if fits(color, True)), None)
		if invented is not None:
			return invented
	if found:
		return max(found, key=lambda color: new_hue(color, picked))
	return max((color for color in mixes(background, text, INK_MIX) if apart(color, picked, INVENTED_DISTINCT)),
			key=lambda color: color_contrast(button, color), default=mixed(background, text, .5))


def artwork_theme_colors(artwork, mode='any'):
	cover = without_rare_skin(cover_colors(artwork)) if artwork else []
	if not cover:
		return None
	side = theme_side(cover, mode)
	background = pick_background(cover, side)
	text = pick_text(cover, background)
	accent = pick_accent(cover, background, text)
	button = pick_button(cover, background, text, accent)
	ink = pick_background_accent(cover, background, text, accent, button)
	colors = simplify_theme_colors({'themeBackground': background.name(), 'textColor': text.name(),
									'themeHighlight': accent.name(), 'themeAccent': button.name(),
									'themeBackgroundAccent': ink.name()})
	colors['paperBackgroundColor'] = colors['themeBackground']
	return colors
