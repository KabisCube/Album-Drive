"""Theme colors picked from the now-playing artwork.

Five colors are picked once, in order:
1. Background: the most used color on the theme's side (light or dark).
2. Text: the most used color on the other side that reads on the background.
3. Accent: the most saturated color that stands apart from the first two.
4. Button: a color apart from the others, preferring an unused hue.
5. Background accent: a cover color that reads on the buttons and shows on the background.
    Colors darker or lighter than the comfortable range are only used as a last resort.
    When the cover has nothing left that fits, a color is invented by mixing two already
    picked colors, so it keeps the album's hues and stays within their lightness.
"""
import colorsys
from io import BytesIO

from PIL import Image
from PySide6.QtGui import QColor

from color_rules import color_contrast, relative_luminance
from themes import PANEL_SHADE

LIGHTNESS_RANGE = (.24, .96)
DARKEST_BACKGROUND = QColor('#2b0200').lightnessF()
DARKEST_GRAY_BACKGROUND = QColor('#1f1f1f').lightnessF()
LIGHT_SIDE = .8
DARK_SIDE = .4
LIGHT_LOOK = .7
DARK_LOOK = .35
INVENTED_LIGHTNESS = {'light': .9, 'dark': .3}
CALM_CHROMA = 48
VIVID_CHROMA = 24
HUE_GAP = 1 / 24
DISTINCT = 32
INVENTED_DISTINCT = 16
MINIMUM_SHARE = .001
DOMINANT_SHARE = .4
MEMBER_SHARE = .1
DOMINANT_FAMILY_LIGHTNESS = .35
PICK_SHARE = .0015
TEXT_CONTRAST = 4
PREFERRED_TEXT_CONTRAST = 4.5
BUTTON_CONTRAST = 1.1
BUTTON_ACCENT_CONTRAST = 1.25
INK_BUTTON_CONTRAST = 1.545
INK_BACKGROUND_CONTRAST = 1.1
INK_PANEL_CONTRAST = 1.05
BUTTON_MIX = [step / 100 for step in range(40, 81)] + [step / 100 for step in range(39, 9, -1)]
INK_MIX = [step / 100 for step in range(2, 101)]

ROLES = ('themeBackground', 'textColor', 'themeHighlight', 'themeAccent', 'themeBackgroundAccent')
TEXT_KEYS = ('textColor', 'secondaryTextColor', 'folderArrowColor', 'headingTextColor', 'selectedTextColor',
             'timelineTextColor', 'paperTextColor')
INK_KEYS = ('themeBackgroundAccent', 'buttonTextColor', 'buttonIconColor', 'disabledTextColor')


def simplify_theme_colors(colors):
    """Every interface role follows one of the five settings colors."""
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
    """Normalize legacy saved keys without changing the theme file format."""
    from themes import COLOR_SETTINGS
    palette = simplify_theme_colors({prop: colors.get(key, default)
                                    for _, _, key, prop, default in COLOR_SETTINGS})
    return {key: palette[prop] for _, _, key, prop, _ in COLOR_SETTINGS}


def cover_colors(artwork):
    """Real cover colors with their share, grouped finely by hue, lightness and colorfulness."""
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


def chroma(color):
    return max(color.getRgb()[:3]) - min(color.getRgb()[:3])


def distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(first.getRgb()[:3], second.getRgb()[:3])) ** .5


def usable(color, bounds=LIGHTNESS_RANGE):
    return bounds[0] <= color.lightnessF() <= bounds[1]


def clamped(color, bounds=LIGHTNESS_RANGE):
    hue, saturation, lightness, _ = color.getHslF()
    level = min(bounds[1], max(bounds[0], lightness))
    if level == lightness:
        return QColor(color)
    saturation = min(1, chroma(color) / 255 / max(.001, 1 - abs(2 * level - 1)))
    return QColor(QColor.fromHslF(max(0, hue), saturation, level).name())


def new_hue(color, picked):
    """True when the color is colorful and its hue is apart from every colorful picked color."""
    if chroma(color) < VIVID_CHROMA:
        return False
    for other in picked:
        if chroma(other) >= VIVID_CHROMA:
            gap = abs(color.hslHueF() - other.hslHueF())
            if min(gap, 1 - gap) < HUE_GAP:
                return False
    return True


def apart(color, picked, gap=DISTINCT):
    return all(distance(color, other) >= gap for other in picked)


def mixed(first, second, amount):
    return QColor(*(round(a + (b - a) * amount) for a, b in zip(first.getRgb()[:3], second.getRgb()[:3])))


def theme_side(cover, mode):
    if mode in ('light', 'dark'):
        return mode
    return 'light' if cover[0][0].lightnessF() >= .5 else 'dark'


def on_side(color, side, light=LIGHT_SIDE, dark=DARK_SIDE):
    """Light or dark enough for its side, leaving room for text at the far edge of the range to read on it."""
    level = LIGHTNESS_RANGE[0] if side == 'light' else LIGHTNESS_RANGE[1]
    edge = QColor(QColor.fromHslF(0, 0, level).name())
    near = color.lightnessF() >= light if side == 'light' else color.lightnessF() <= dark
    return near and color_contrast(clamped(color), edge) >= PREFERRED_TEXT_CONTRAST


def perceived_lightness(color):
    """CIE lightness from 0 to 1, how bright a color looks rather than its HSL value."""
    luminance = relative_luminance(color)
    return (116 * luminance ** (1 / 3) - 16) / 100 if luminance > .008856 else 9.033 * luminance


def lifted(color, bounds=LIGHTNESS_RANGE):
    """A color beyond the range brightened or dimmed as a whole, so it keeps its hue and its share of color."""
    lightness = color.lightnessF()
    level = min(bounds[1], max(bounds[0], lightness))
    if level == lightness:
        return QColor(color)
    scale = level / max(lightness, 1 / 510)
    return QColor(*(min(255, round(max(channel, .5) * scale)) for channel in color.getRgb()[:3]))


def pick_background(cover, side):
    """Near-gray blacks stay a little brighter than colorful darks, so shadows still show on them."""
    background = pick_cover_background(cover, side)
    if chroma(background) < VIVID_CHROMA and background.lightnessF() < DARKEST_GRAY_BACKGROUND:
        return lifted(background, (DARKEST_GRAY_BACKGROUND, LIGHTNESS_RANGE[1]))
    return background


def pick_cover_background(cover, side):
    """Dark backgrounds may go down to DARKEST_BACKGROUND. A color, or one hue family, covering most of the
    cover only has to be in its side's half of the lightness range."""
    bounds = (DARKEST_BACKGROUND, LIGHTNESS_RANGE[1]) if side == 'dark' else LIGHTNESS_RANGE
    dominant, share = cover[0]
    if share >= DOMINANT_SHARE and usable(dominant, bounds) and on_side(dominant, side, .5, .5):
        return dominant
    families = {}
    for color, share in cover:
        if chroma(color) >= VIVID_CHROMA:
            families.setdefault(round(color.hslHueF() * 12) % 12, []).append((color, share))
    family = max(families.values(), key=lambda members: sum(share for _, share in members), default=[])
    total = sum(share for _, share in family)
    if total >= DOMINANT_SHARE:
        looks = sum(perceived_lightness(color) * share for color, share in family) / total
        clearly = looks >= 1 - DOMINANT_FAMILY_LIGHTNESS if side == 'light' else looks <= DOMINANT_FAMILY_LIGHTNESS
        shade = clamped(family[0][0], bounds)
        if clearly and on_side(shade, side, .5, .5):
            return shade
    groups = {}
    for color, share in cover:
        looks = perceived_lightness(color)
        if (looks >= LIGHT_LOOK if side == 'light' else looks <= DARK_LOOK) and on_side(clamped(color, bounds), side, 0, 1):
            key = -1 if chroma(color) < VIVID_CHROMA else round(color.hslHueF() * 12) % 12
            groups.setdefault(key, []).append((color, share))
    if groups:
        members = max(groups.values(), key=lambda entries: sum(share for _, share in entries))
        top, top_share = members[0]
        if usable(top, bounds):
            return top
        inside = [color for color, share in members if usable(color, bounds) and share >= top_share * MEMBER_SHARE]
        return inside[0] if inside else lifted(top, bounds)
    extreme = max(cover, key=lambda entry: entry[0].lightnessF() if side == 'light' else -entry[0].lightnessF())[0]
    hue, saturation, _, _ = extreme.getHslF()
    level, step = INVENTED_LIGHTNESS[side], (.01 if side == 'light' else -.01)
    invented = QColor(QColor.fromHslF(max(0, hue), saturation, level).name())
    while not on_side(invented, side) and LIGHTNESS_RANGE[0] < level < LIGHTNESS_RANGE[1]:
        level += step
        invented = QColor(QColor.fromHslF(max(0, hue), saturation, level).name())
    return clamped(invented, bounds)


def pick_text(cover, background):
    def reads(minimum):
        return lambda color: color_contrast(background, color) >= minimum
    def calm(color):
        return chroma(color) <= CALM_CHROMA

    def muted(color):
        return chroma(color) <= 2 * CALM_CHROMA
    tests = (lambda color: usable(color) and calm(color) and reads(PREFERRED_TEXT_CONTRAST)(color),
             lambda color: usable(color) and calm(color) and reads(TEXT_CONTRAST)(color),
             lambda color: calm(color) and reads(TEXT_CONTRAST)(clamped(color)),
             lambda color: usable(color) and muted(color) and reads(TEXT_CONTRAST)(color),
             lambda color: muted(color) and reads(TEXT_CONTRAST)(clamped(color)))
    for index, test in enumerate(tests):
        found = [color for color, _ in cover if test(color)]
        if found:
            # Without a calm color, the calmest readable one; vivid colors are left for the accent.
            return clamped(found[0] if index < 3 else min(found, key=chroma))
    hue, saturation, _, _ = background.getHslF()
    darker = background.lightnessF() >= .5
    levels = [step / 100 for step in (range(50, -1, -1) if darker else range(50, 101))]
    shades = [QColor(QColor.fromHslF(max(0, hue), saturation, level).name()) for level in levels]
    return next((shade for shade in shades if usable(shade) and reads(TEXT_CONTRAST)(shade)),
                next((shade for shade in shades if reads(TEXT_CONTRAST)(shade)), shades[-1]))


def pick_accent(cover, background, text):
    picked = (background, text)
    fits = [(color, share) for color, share in cover if usable(color) and apart(color, picked)]
    if fits:
        return max(fits, key=lambda entry: (new_hue(entry[0], picked), chroma(entry[0]) ** 2 * entry[1] ** .25))[0]
    return next((color for color in (mixed(background, text, amount) for amount in BUTTON_MIX)
                 if apart(color, picked, INVENTED_DISTINCT)),
                mixed(background, text, .5))


def pick_button(cover, background, text, accent):
    picked = (background, text, accent)

    def fits(color, gap):
        return (apart(color, picked, gap) and color_contrast(background, color) >= BUTTON_CONTRAST
                and color_contrast(accent, color) >= BUTTON_ACCENT_CONTRAST)
    found = [color for color, share in cover if share >= PICK_SHARE and usable(color) and fits(color, DISTINCT)]
    if found:
        return max(found, key=lambda color: new_hue(color, picked))
    return next((color for color in (mixed(background, text, amount) for amount in BUTTON_MIX)
                 if fits(color, INVENTED_DISTINCT)), mixed(background, text, .5))


def pick_background_accent(cover, background, text, accent, button):
    picked = (background, text, accent, button)
    panel = background.darker(PANEL_SHADE)

    def fits(color, gap):
        return (apart(color, picked, gap) and color_contrast(button, color) >= INK_BUTTON_CONTRAST
                and color_contrast(background, color) >= INK_BACKGROUND_CONTRAST
                and color_contrast(panel, color) >= INK_PANEL_CONTRAST)
    def between(color):
        return min(background.lightnessF(), button.lightnessF()) <= color.lightnessF() <= max(
            background.lightnessF(), button.lightnessF())
    found = [color for color, share in cover if share >= PICK_SHARE and usable(color) and fits(color, DISTINCT)]
    inside = [color for color in found if between(color)]
    if inside:
        return max(inside, key=lambda color: (new_hue(color, picked), color_contrast(button, color)))
    for toward in (button, text):
        invented = next((color for color in (mixed(background, toward, amount) for amount in INK_MIX)
                         if fits(color, INVENTED_DISTINCT)), None)
        if invented is not None:
            return invented
    if found:
        return max(found, key=lambda color: new_hue(color, picked))
    return max((mixed(background, text, amount) for amount in INK_MIX if
                apart(mixed(background, text, amount), picked, INVENTED_DISTINCT)),
               key=lambda color: color_contrast(button, color), default=mixed(background, text, .5))


def artwork_theme_colors(artwork, mode='any'):
    cover = cover_colors(artwork) if artwork else []
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
