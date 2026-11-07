"""Readable application colors sampled from the now-playing artwork."""

import re

from PySide6.QtGui import QColor

from open_case import artwork_accent_palette, artwork_color_range, artwork_palette, artwork_scrollbar_colors, color_contrast
from themes import accent_shade
from color_rules import artwork_text_color, comfortable_color, comfortable_surface, SOFT_BLACK, SOFT_WHITE


MINIMUM_TEXT_CONTRAST = 4.5
FALLBACK_TEXT_CONTRAST = 3
ALBUM_HUE_RANGE = .04
BUTTON_LIGHTNESS = (.3, .8)
BUTTON_BACKGROUND_CONTRAST = 1.4
REAL_COLOR_DISTANCE = 48
MAIN_COLOR_DISTANCE = 40
MAIN_HUE_SHARE = .75
POP_SATURATION = .6
POP_SATURATION_GAIN = 1.3
POP_HUE_GAP = .08
POP_FAMILY_RANGE = .03
POP_MAIN_SHARE = .04
MINIMUM_BACKGROUND_LIGHTNESS = 40 / 255
ALBUM_LIGHTNESS_MARGIN = .04
COMFORTABLE_LIGHTNESS = (16 / 255, 244 / 255)
REAL_INK_CONTRAST = 2.5
MEANINGFUL_SHARE = .02
MINIMUM_DISTINCT_COLORS = 3
MUTED_RANGE = .3
MUTED_MINIMUM_SPAN = .5
MUTED_TEXT_GAP = .02
MUTED_TEXT_STRENGTHS = (.75, .85, .95)  # Between the even shade steps, so text never equals one.
MUTED_TEXT_CONTRAST = 2
SINGLE_HUE_RANGE = .1
OWN_CONTRAST = 3


def contrasting_text(background):
    return max((QColor(SOFT_WHITE), QColor(SOFT_BLACK)),
               key=lambda color: color_contrast(background, color))


def soften_theme_colors(colors):
    surfaces = ('themeAccent', 'themeHighlight', 'themeBackgroundAccent', 'buttonFill')
    return {key: (comfortable_surface(value) if key in surfaces else comfortable_color(value)).name()
            for key, value in colors.items()}


def button_text_color_for_palette(colors):
    return QColor(colors.get('themeBackgroundAccent') or colors['buttonTextColor']).name()


def simplify_theme_colors(colors):
    """Expand five chosen colors into consistent, readable interface roles."""
    colors = soften_theme_colors(colors)
    background = QColor(colors['themeBackground'])
    accent = QColor(colors['themeAccent'])
    fill = QColor(colors['buttonFill'])
    text = QColor(colors['textColor'])
    highlight = QColor(colors.get('themeHighlight', colors.get('brandTextColor', '#cfe10e')))
    button_text = contrasting_text(fill)
    for _ in range(30):
        if color_contrast(QColor(fill.name()), button_text) >= 4.6:
            break
        fill.setHslF(fill.hslHueF(), fill.hslSaturationF(),
                     max(16 / 255, min(244 / 255, fill.lightnessF()
                         + (.005 if button_text == QColor(SOFT_BLACK) else -.005))))
    colors['buttonFill'] = fill.name()
    button_text = QColor(colors.get('themeBackgroundAccent') or text)
    button_icon = button_text
    logo_background = background.darker(110)
    colors.update({key: value.name() for key, value in {
        'themeHighlight': highlight, 'timelineColor': accent, 'brandTextColor': highlight, 'brandLineColor': logo_background,
        'folderArrowColor': text, 'buttonIconColor': button_icon, 'buttonTextColor': button_text,
        'disabledTextColor': button_text, 'secondaryTextColor': text, 'headingTextColor': text,
        'selectedTextColor': text, 'timelineTextColor': text, 'paperTextColor': text,
    }.items()})
    return soften_theme_colors(colors)


def simplify_color_settings(colors):
    """Normalize legacy saved keys without changing the theme file format."""
    from themes import COLOR_SETTINGS
    palette = simplify_theme_colors({prop: colors.get(key, default)
                                    for _, _, key, prop, default in COLOR_SETTINGS})
    return {key: palette[prop] for _, _, key, prop, _ in COLOR_SETTINGS}


def application_controls(background, palette, details=()):
    ordered = tuple(palette[1:]) + tuple(palette[:1])
    surfaces = (background, background.darker(110))
    vivid = tuple(color for color in details if color.hslSaturationF() >= .35
                  and max(color.getRgbF()[:3]) - min(color.getRgbF()[:3]) >= .2
                  and sum((first - second) ** 2 for first, second in
                          zip(background.getRgb()[:3], color.getRgb()[:3])) >= 48 ** 2)
    def vibrancy(color):
        chroma = max(color.getRgbF()[:3]) - min(color.getRgbF()[:3])
        hue_distance = abs(color.hslHueF() - background.hslHueF())
        separation = min(hue_distance, 1 - hue_distance) * 2 if background.hslSaturationF() >= .15 else 1
        return .65 * chroma + .25 * color.hslSaturationF() + .1 * separation
    accent = QColor(max(vivid, key=vibrancy)) if vivid else artwork_text_color(surfaces, ordered)
    _, fill = artwork_scrollbar_colors(background, (accent,) + tuple(palette))
    return accent, fill


def colors_too_similar(first, second):
    first, second = QColor(first), QColor(second)
    distance = sum((a - b) ** 2 for a, b in zip(first.getRgb()[:3], second.getRgb()[:3])) ** .5
    lightness_distance = abs(first.lightnessF() - second.lightnessF())
    hue_a, hue_b = first.hslHueF(), second.hslHueF()
    hue_distance = abs(hue_a - hue_b) if hue_a >= 0 and hue_b >= 0 else 0
    hue_distance = min(hue_distance, 1 - hue_distance)
    low_saturation = min(first.hslSaturationF(), second.hslSaturationF()) < .15
    return distance < 62 and lightness_distance < .17 and (hue_distance < .125 or low_saturation)


def distinct_artwork_color(background, accent, palette):
    options = []
    for source in palette:
        color = QColor(source)
        hue, saturation, lightness, _ = color.getHslF()
        for target in (.04, .96):
            for step in range(1, 257):
                level = lightness + (target - lightness) * step / 256
                candidate = QColor(QColor.fromHslF(hue, saturation, level).name())
                if (not colors_too_similar(candidate, accent)
                        and color_contrast(candidate, background) >= 1.3):
                    options.append((step, candidate.name()))
                    break
    if options:
        return QColor(min(options)[1])
    hue, saturation, lightness, _ = QColor(accent).getHslF()
    for target in (.04, .96):
        candidate = QColor(QColor.fromHslF(hue, saturation, target).name())
        if not colors_too_similar(candidate, accent):
            return candidate
    return QColor(accent).lighter(180)


def readable_background(background, mode='any'):
    """Nudge a mid-tone background only as far as needed for text to read on it and its panels."""
    def legible(color):
        surfaces = (color, color.darker(120), color.darker(130))
        return any(min(color_contrast(surface, QColor(ink)) for surface in surfaces) >= MINIMUM_TEXT_CONTRAST
                   for ink in (SOFT_WHITE, SOFT_BLACK))
    if legible(background):
        return background
    hue, saturation, lightness, _ = background.getHslF()
    directions = {'dark': (-1,), 'light': (1,)}.get(mode, (-1, 1) if lightness < .5 else (1, -1))
    for step in range(1, 65):
        for direction in directions:
            level = max(0, min(1, lightness + direction * step / 128))
            candidate = QColor(QColor.fromHslF(hue, saturation, level).name())
            if legible(candidate):
                return candidate
    return background


def sampled_artwork_text_color(surfaces, palette, minimum, prefer_dark, avoid=(), paper=None):
    colors = tuple(dict.fromkeys(QColor(color).name() for color in palette))
    interface = tuple(surfaces)
    surfaces = interface + ((paper,) if paper is not None else ())
    candidates = [QColor(color) for color in colors
                  if not any(colors_too_similar(QColor(color), other) for other in avoid)]
    if not candidates:
        candidates = [QColor(color) for color in colors]
    def contrast(color):
        return min(color_contrast(surface, color) for surface in surfaces)
    readable = [color for color in candidates if contrast(color) >= minimum]
    if not readable:
        # Near single-color art has nothing legible, so tune a cover color until it reads.
        # Only as far as it takes to read comfortably, so it stays close to the artwork.
        tuned = artwork_text_color(surfaces, colors, FALLBACK_TEXT_CONTRAST)
        if min(color_contrast(surface, tuned) for surface in interface) >= FALLBACK_TEXT_CONTRAST:
            return tuned
        # A light paper on a dark background has no shared ink; the paper then gets its own.
        return artwork_text_color(interface, colors, FALLBACK_TEXT_CONTRAST)
    return max(readable, key=lambda color: (contrast(color), color.hslSaturationF()))


def application_highlight(background, accent, text, palette):
    existing = (background, accent, QColor(text))
    def hue_distance(color):
        distance = abs(color.hslHueF() - background.hslHueF())
        return min(distance, 1 - distance)
    chromatic_background = background.hslSaturationF() >= .12
    distinct = tuple(color for color in palette if not colors_too_similar(color, accent))
    different_hues = tuple(color for color in distinct if color.hslSaturationF() >= .12
                          and max(color.getRgb()[:3]) - min(color.getRgb()[:3]) >= 12
                          and hue_distance(color) >= 1 / 12
                          and sum((a - b) ** 2 for a, b in zip(background.getRgb()[:3], color.getRgb()[:3])) >= 32 ** 2
                          ) if chromatic_background else ()
    candidates = different_hues or tuple(color for color in distinct if color_contrast(background, color) >= 1.3)
    if not candidates:
        return distinct_artwork_color(background, accent, palette)
    def distinction(color):
        distance = min(sum((a - b) ** 2 for a, b in zip(color.getRgbF()[:3], other.getRgbF()[:3]))
                       for other in existing)
        separation = .8 * hue_distance(color) if different_hues else 0
        return distance + .08 * color.hslSaturationF() + separation
    return max(candidates, key=distinction)


def artwork_background_accent(background, button_color, palette):
    background = QColor(background)
    button_color = QColor(button_color)
    options = []
    fallbacks = []
    for source in dict.fromkeys(QColor(color).name() for color in palette):
        original = QColor(source)
        hue, saturation, lightness, _ = original.getHslF()
        saturation = min(saturation, .38) if hue >= 0 else 0
        for target in (lightness, .04, .96):
            steps = 1 if target == lightness else 256
            for step in range(steps + 1):
                level = lightness if steps == 1 else lightness + (target - lightness) * step / steps
                color = QColor(QColor.fromHslF(hue, saturation, level).name())
                button_contrast = color_contrast(color, button_color)
                background_contrast = color_contrast(color, background)
                distance = sum((a - b) ** 2 for a, b in zip(color.getRgb()[:3], background.getRgb()[:3])) ** .5
                score = (min(button_contrast, 3) / 3 + min(background_contrast, 1.4) / 1.4
                         + min(distance, 36) / 36)
                fallbacks.append((score, color.name()))
                separated = background_contrast >= 1.4 and distance >= 36
                if button_contrast >= 3 and separated:
                    change = abs(level - lightness) + .35 * abs(saturation - original.hslSaturationF())
                    options.append((change, abs(saturation - .24), color.name()))
                    break
    if options:
        return QColor(min(options)[2])
    return QColor(max(fallbacks)[1]) if fallbacks else QColor(button_color)


def spread_from(color, others, acceptable=lambda candidate: True):
    """Nearest lighter or darker shade that stays distinct from others; never an invented hue."""
    color = QColor(color)
    hue, saturation, lightness, _ = color.getHslF()
    hue = max(0, hue)
    def usable(candidate):
        return acceptable(candidate) and not any(colors_too_similar(candidate, other) for other in others)
    for step in range(0, 129):
        for direction in (1, -1):
            level = lightness + direction * step / 128
            if 16 / 255 <= level <= 244 / 255:
                candidate = QColor(QColor.fromHslF(hue, saturation, level).name())
                if usable(candidate):
                    return candidate
    return color


def range_color(color_range, acceptable):
    """The most prominent, most colorful real cover color that meets a need."""
    options = [(share * (max(color.getRgb()[:3]) - min(color.getRgb()[:3])), color.name())
               for color, share in color_range if acceptable(color)]
    return QColor(max(options)[1]) if options else None


def separate_button_colors(colors, color_range=()):
    others = [QColor(colors[key]) for key in ('themeBackground', 'textColor', 'themeHighlight')]
    background = others[0]
    accent = QColor(colors['themeAccent'])

    def stands_apart(candidate, *taken):
        return not any(colors_too_similar(candidate, other) for other in others + list(taken))

    def visibly_different(candidate, *taken):
        # Real cover colors already belong together, so they only need to be told apart.
        return all(sum((a - b) ** 2 for a, b in zip(candidate.getRgb()[:3], other.getRgb()[:3])) ** .5 >= REAL_COLOR_DISTANCE
                   for other in others + list(taken))

    def within_album(color):
        # Fallbacks may not go lighter or darker than anything on the cover.
        levels = [source.lightnessF() for source, share in color_range if share >= MEANINGFUL_SHARE]
        color = QColor(color)
        return shade_at(color, max(min(levels), min(max(levels), color.lightnessF()))) if levels else color

    if not BUTTON_LIGHTNESS[0] <= accent.lightnessF() <= BUTTON_LIGHTNESS[1]:
        # Buttons read best in a mid-tone the cover really has, not its darkest line work.
        accent = range_color(color_range, lambda candidate: (
            BUTTON_LIGHTNESS[0] <= candidate.lightnessF() <= BUTTON_LIGHTNESS[1] and stands_apart(candidate)
            and color_contrast(background, candidate) >= BUTTON_BACKGROUND_CONTRAST)) or accent

    def readable_ink(surface):
        for minimum in (MINIMUM_TEXT_CONTRAST, REAL_INK_CONTRAST):
            ink = range_color(color_range, lambda candidate: color_contrast(surface, candidate) >= minimum
                              and visibly_different(candidate, surface))
            if ink is not None:
                return ink

        def legible(candidate):
            return color_contrast(surface, candidate) >= FALLBACK_TEXT_CONTRAST
        ink = spread_from(within_album(colors['themeBackgroundAccent']), others + [surface], legible)
        return ink if legible(ink) and visibly_different(ink, surface) else None

    ink = readable_ink(accent)
    if ink is None:
        # Mid tones leave room for one readable ink only, so give the accent a small nudge.
        hue, saturation, lightness, _ = accent.getHslF()
        for level in sorted((step / 16 for step in range(3, 15)), key=lambda value: abs(value - lightness)):
            candidate = QColor(comfortable_surface(QColor.fromHslF(max(0, hue), saturation, level)).name())
            if stands_apart(candidate):
                ink = readable_ink(candidate)
                if ink is not None:
                    accent = candidate
                    break
    ink = ink or max((color for color, _ in color_range), key=lambda color: color_contrast(accent, color),
                     default=contrasting_text(accent))
    colors['themeAccent'] = accent.name()
    colors['themeBackgroundAccent'] = ink.name()
    fill = range_color(color_range, lambda candidate: visibly_different(candidate, accent, ink)
                       and color_contrast(background, candidate) >= BUTTON_BACKGROUND_CONTRAST)
    colors['buttonFill'] = (fill or spread_from(within_album(colors['buttonFill']), others + [accent, ink])).name()


def unique_artwork_colors(colors, palette, text_palette, text_minimum, paper=None, color_range=()):
    # Text must stay readable, so the decorative colors make way for it instead.
    keys = ('themeBackground', 'textColor', 'themeHighlight', 'themeAccent', 'themeBackgroundAccent', 'buttonFill')
    seen = []
    background = QColor(colors['themeBackground'])
    paper_background = QColor(paper or (palette[0] if palette else background))
    surfaces = tuple(background.darker(factor) for factor in (100, 120, 130))
    text_minimum = 7.0 if paper_background.lightnessF() >= .5 else 4.5
    for key in keys:
        color = QColor(colors[key])
        if key == 'textColor':
            color = sampled_artwork_text_color(surfaces, text_palette, text_minimum,
                                               paper_background.lightnessF() >= .5, seen, paper_background)
        elif any(colors_too_similar(color, prior) for prior in seen):
            candidates = []
            for index, source in enumerate(palette):
                candidate = QColor(source)
                if any(colors_too_similar(candidate, prior) for prior in seen):
                    continue
                if key == 'themeAccent' and color_contrast(candidate, background) < 1.3:
                    continue
                if key == 'themeBackgroundAccent':
                    if color_contrast(candidate, background) < 1.4 or color_contrast(candidate, QColor(colors['themeAccent'])) < 3:
                        continue
                    if sum((a - b) ** 2 for a, b in zip(candidate.getRgb()[:3], background.getRgb()[:3])) ** .5 < 36:
                        continue
                elif key == 'buttonFill':
                    if color_contrast(candidate, background) < 3 or color_contrast(candidate, QColor(colors['themeAccent'])) < 1.25:
                        continue
                distance = sum((a - b) ** 2 for a, b in zip(candidate.getRgb()[:3], color.getRgb()[:3]))
                candidates.append((distance, index, candidate.name()))
            if candidates:
                color = QColor(min(candidates)[2])
            else:
                hue, saturation, lightness, _ = color.getHslF()
                variants = []
                for target in (.04, .96):
                    for step in range(1, 257):
                        level = lightness + (target - lightness) * step / 256
                        candidate = QColor(QColor.fromHslF(hue, saturation, level).name())
                        if not any(colors_too_similar(candidate, prior) for prior in seen):
                            variants.append((step, candidate.name()))
                            break
                if variants:
                    color = QColor(min(variants)[1])
        colors[key] = color.name()
        seen.append(color)
    if chroma(QColor(colors['themeAccent'])) > chroma(QColor(colors['themeHighlight'])):
        colors['themeAccent'], colors['themeHighlight'] = colors['themeHighlight'], colors['themeAccent']
    separate_button_colors(colors, color_range)
    colors['timelineColor'] = colors['themeAccent']
    colors['brandTextColor'] = colors['themeHighlight']
    colors['secondaryTextColor'] = colors['textColor']
    colors['headingTextColor'] = colors['textColor']
    colors['selectedTextColor'] = colors['textColor']
    colors['timelineTextColor'] = colors['textColor']
    text = QColor(colors['textColor'])
    if color_contrast(paper_background, text) < FALLBACK_TEXT_CONTRAST:
        text = artwork_text_color((paper_background,), palette, FALLBACK_TEXT_CONTRAST)
    colors['paperTextColor'] = text.name()
    colors['paperBackgroundColor'] = paper_background.name()
    colors['buttonTextColor'] = colors['themeBackgroundAccent']
    colors['buttonIconColor'] = colors['themeBackgroundAccent']
    colors['disabledTextColor'] = colors['themeBackgroundAccent']
    return colors


def is_chromatic(color):
    return color.hslSaturationF() >= .12 and max(color.getRgb()[:3]) - min(color.getRgb()[:3]) >= 12


def hue_gap(first, second):
    gap = abs(first.hslHueF() - second.hslHueF())
    return min(gap, 1 - gap)


def album_shade(color, artwork_colors):
    """Keep a color's lightness but make sure its hue really is on the album."""
    color = QColor(color)
    chromatic = [source for source in artwork_colors if is_chromatic(source)]
    neutral = [source for source in artwork_colors if not is_chromatic(source)]
    if is_chromatic(color):
        if not chromatic:
            source = min(neutral, key=lambda option: abs(option.lightnessF() - color.lightnessF()))
        else:
            source = min(chromatic, key=lambda option: hue_gap(color, option))
            if hue_gap(color, source) <= ALBUM_HUE_RANGE:
                return color
    elif neutral or not chromatic:
        return color
    else:
        source = max(chromatic, key=lambda option: option.hslSaturationF())
    return QColor(QColor.fromHslF(max(0, source.hslHueF()), source.hslSaturationF(), color.lightnessF()).name())


def keep_album_hues(colors, artwork_colors):
    """The last word on every picked color: fallbacks may change lightness, never invent a hue."""
    artwork_colors = tuple(QColor(color) for color in artwork_colors)
    return {key: album_shade(value, artwork_colors).name() for key, value in colors.items()}


def keep_album_lightness(colors, color_range, artwork_colors=()):
    real = [color for color, share in color_range if share >= MEANINGFUL_SHARE]
    if not real:
        return colors
    low = min(color.lightnessF() for color in real) - ALBUM_LIGHTNESS_MARGIN
    high = max(color.lightnessF() for color in real) + ALBUM_LIGHTNESS_MARGIN
    background = QColor(colors['themeBackground'])
    options = [color for color in real if rgb_distance(color, background) >= REAL_COLOR_DISTANCE]
    if not options:
        return colors

    def replacement(role):
        color = QColor(colors[role])
        if low <= color.lightnessF() <= high or any(
                rgb_distance(color, other) < MAIN_COLOR_DISTANCE for other in artwork_colors):
            return color
        if role == 'themeBackgroundAccent':
            return max(options, key=lambda option: color_contrast(option, QColor(colors['themeAccent'])))
        return min(options, key=lambda option: abs(option.lightnessF() - color.lightnessF()))

    colors = dict(colors)
    for role in ('themeHighlight', 'themeAccent', 'buttonFill', 'themeBackgroundAccent'):
        colors[role] = replacement(role).name()
    ink = colors['themeBackgroundAccent']
    colors.update(timelineColor=colors['themeAccent'], brandTextColor=colors['themeHighlight'],
                  buttonTextColor=ink, buttonIconColor=ink, disabledTextColor=ink)
    return colors


def has_limited_colors(palette):
    """True when a cover offers fewer than three clearly different colors."""
    distinct = []
    for color in palette:
        if not any(colors_too_similar(color, other) for other in distinct):
            distinct.append(QColor(color))
    return len(distinct) < MINIMUM_DISTINCT_COLORS


def single_hue_without_contrast(palette, background):
    """True for covers built from one hue and its tints, with no color that stands out from it."""
    hues = [color.hslHueF() for color in palette
            if color.hslSaturationF() >= .12 and max(color.getRgb()[:3]) - min(color.getRgb()[:3]) >= 12]
    gaps = [min(abs(first - second), 1 - abs(first - second)) for first in hues for second in hues]
    return max(gaps, default=0) <= SINGLE_HUE_RANGE and strongest_contrast(palette, background) < OWN_CONTRAST


def strongest_contrast(palette, background):
    return max((color_contrast(background, color) for color in palette), default=1)


def shade_at(color, level):
    """A color at another lightness with no more color in it, so near-white cannot turn tan."""
    hue, saturation, lightness, _ = color.getHslF()
    chroma = saturation * (1 - abs(2 * lightness - 1))
    room = 1 - abs(2 * level - 1)
    return QColor(QColor.fromHslF(max(0, hue), min(saturation, chroma / room if room else 0), level).name())


def muted_shades(color, toward=None):
    """Five shades of a color close to it, strongest first, for covers with little else to use.

    With toward set, shades on that color's side come first, so a pale cover stays pale."""
    color = QColor(color)
    hue, saturation, lightness, _ = color.getHslF()
    low = max(16 / 255, lightness - MUTED_RANGE)
    high = min(244 / 255, lightness + MUTED_RANGE)
    if high - low < MUTED_MINIMUM_SPAN:
        low, high = (low, low + MUTED_MINIMUM_SPAN) if low == 16 / 255 else (high - MUTED_MINIMUM_SPAN, high)
    levels = [low + (high - low) * step / 5 for step in range(6)]
    levels.remove(min(levels, key=lambda level: abs(level - lightness)))
    shades = [shade_at(color, level) for level in levels]
    def rank(shade):
        same_side = toward is not None and (shade.lightnessF() > lightness) == (toward.lightnessF() > lightness)
        return same_side, color_contrast(color, shade)
    return sorted(shades, key=rank, reverse=True)


def muted_text(surface, toward=None, avoid=()):
    """The strongest shade eased back toward the surface, stopping before it gets hard to see."""
    surface, shade = QColor(surface), muted_shades(surface, toward)[0]
    span = shade.lightnessF() - surface.lightnessF()
    for strength in MUTED_TEXT_STRENGTHS:
        level = surface.lightnessF() + span * strength
        candidate = shade_at(surface, level)
        distinct = all(abs(candidate.lightnessF() - other.lightnessF()) >= MUTED_TEXT_GAP for other in avoid)
        if distinct and color_contrast(surface, candidate) >= MUTED_TEXT_CONTRAST:
            return candidate
    return shade


def rgb_distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(first.getRgb()[:3], second.getRgb()[:3])) ** .5


def chroma(color):
    return max(color.getRgb()[:3]) - min(color.getRgb()[:3])


def one_main_hue(main_colors):
    chromatic = [(color, share) for color, share in main_colors if is_chromatic(color)]
    if not chromatic:
        return False
    leader = chromatic[0][0]
    together = sum(share for color, share in chromatic if hue_gap(color, leader) <= SINGLE_HUE_RANGE)
    return together >= sum(share for _, share in chromatic) * MAIN_HUE_SHARE


def artwork_pop(details, main_colors):
    """A small vivid detail that stands out from a cover's main colors."""
    chromatic = [color for color, _ in main_colors if is_chromatic(color)]
    strongest = max((color.hsvSaturationF() for color, share in main_colors
                     if is_chromatic(color) and share >= POP_MAIN_SHARE), default=0)
    single_hue = one_main_hue(main_colors)

    def pops(color):
        far_from_main = all(rgb_distance(color, other) >= MAIN_COLOR_DISTANCE for other, _ in main_colors)
        new_hue = single_hue and all(hue_gap(color, other) >= POP_HUE_GAP for other in chromatic)
        saturated = color.hsvSaturationF() >= max(POP_SATURATION, strongest * POP_SATURATION_GAIN)
        return far_from_main and is_chromatic(color) and (saturated or new_hue)

    candidates = [color for color in details if pops(color)]
    if not candidates:
        return None
    leader = max(candidates, key=lambda color: color.hsvSaturationF())
    family = [color for color in candidates if hue_gap(color, leader) <= POP_FAMILY_RANGE]
    return QColor(*(round(sum(color.getRgb()[channel] for color in family) / len(family)) for channel in range(3)))


def main_artwork_colors(color_range, mode, details=()):
    """Five real cover colors, or None when a cover does not clearly have them."""
    merged = []
    for color, share in color_range:
        if not any(rgb_distance(color, other) < MAIN_COLOR_DISTANCE for other, _ in merged):
            merged.append((color, share))
    if len(merged) < 5:
        return None
    dominant = merged[0][0]
    text = max((color for color, share in merged[1:] if share >= MEANINGFUL_SHARE),
               key=lambda color: color_contrast(dominant, color), default=None)
    if text is None or color_contrast(dominant, text) < MINIMUM_TEXT_CONTRAST:
        return None
    remaining = [entry for entry in merged[1:] if entry[0] != text]
    picked = []
    while remaining and len(picked) < 3:
        best = max(remaining, key=lambda entry: entry[1] ** .5 * min(
            rgb_distance(entry[0], other) for other in [dominant, text] + picked))
        remaining.remove(best)
        picked.append(best[0])
    if len(picked) < 3:
        return None
    accent = artwork_pop(details, merged)
    if accent is None:
        accent = max(picked, key=chroma)
        picked.remove(accent)
    hue_from_background = (lambda color: hue_gap(color, dominant)) if is_chromatic(dominant) else chroma
    button = max(picked, key=hue_from_background)
    picked.remove(button)
    background = dominant
    if (mode == 'dark' and background.lightnessF() > text.lightnessF()) or (
            mode == 'light' and background.lightnessF() < text.lightnessF()):
        background, text = text, background
    return assembled_colors(background, text, button, accent, picked[0], picked[0], background, text)


def muted_artwork_colors(background, paper, toward=None):
    _, button_text, highlight, fill, accent = muted_shades(background, toward)
    text = muted_text(background, toward, (button_text, highlight, fill, accent))
    return assembled_colors(background, text, accent, highlight, button_text, fill, paper,
                            muted_text(paper, toward))


def assembled_colors(background, text, accent, highlight, button_text, fill, paper, paper_text):
    colors = simplify_theme_colors({'themeBackground': background.name(), 'themeAccent': accent.name(),
                                    'buttonFill': fill.name(), 'textColor': text.name(),
                                    'brandTextColor': highlight.name()})
    colors.update({'themeBackground': background.name(), 'themeAccent': accent.name(), 'buttonFill': fill.name(),
                   'themeHighlight': highlight.name(), 'themeBackgroundAccent': button_text.name(),
                   'timelineColor': accent.name(), 'brandTextColor': highlight.name(),
                   'paperBackgroundColor': paper.name(), 'paperTextColor': paper_text.name()})
    colors.update({key: text.name() for key in ('textColor', 'secondaryTextColor', 'folderArrowColor', 'headingTextColor',
                                                'selectedTextColor', 'timelineTextColor')})
    colors.update({key: button_text.name() for key in ('buttonTextColor', 'buttonIconColor', 'disabledTextColor')})
    return colors


def vivid_accent(colors):
    highlight, button = QColor(colors['themeHighlight']), QColor(colors['themeAccent'])
    if chroma(button) > chroma(highlight) and BUTTON_LIGHTNESS[0] <= highlight.lightnessF() <= BUTTON_LIGHTNESS[1]:
        colors = dict(colors, themeAccent=highlight.name(), themeHighlight=button.name(),
                      timelineColor=highlight.name(), brandTextColor=button.name())
    return colors


def comfortable_artwork_colors(colors):
    """Pure black and white are too harsh, and black hides shadows and darker panels."""
    def within(value, low):
        color = QColor(value)
        return shade_at(color, max(low, min(COMFORTABLE_LIGHTNESS[1], color.lightnessF()))).name()

    backgrounds = ('themeBackground', 'paperBackgroundColor')
    return {key: within(value, MINIMUM_BACKGROUND_LIGHTNESS if key in backgrounds else COMFORTABLE_LIGHTNESS[0])
            for key, value in colors.items()}


def artwork_theme_colors(artwork, mode='any'):
    """Use this cover, falling back to saved colors for unusable artwork."""
    colors = picked_artwork_colors(artwork, mode)
    return comfortable_artwork_colors(vivid_accent(colors)) if colors else colors


def picked_artwork_colors(artwork, mode):
    sampled_palette = tuple(artwork_palette(artwork, colors=32, minimum=.002))
    palette = tuple(comfortable_color(color) for color in artwork_palette(artwork))
    if not palette:
        return None
    color_range = artwork_color_range(artwork)
    main_colors = main_artwork_colors(color_range, mode, artwork_accent_palette(artwork))
    if main_colors is not None:
        return main_colors
    if mode in ('dark', 'light'):
        low, high = (0, .45) if mode == 'dark' else (.65, 1)
        preferred = tuple(color for color in palette if low <= color.lightnessF() <= high)
        background = QColor(preferred[0] if preferred else palette[0])
        if not preferred:
            if max(background.getRgb()[:3]) - min(background.getRgb()[:3]) < 16:
                background.setHslF(-1, 0, background.lightnessF())
            background.setHslF(background.hslHueF(), background.hslSaturationF(),
                               min(high, max(low, background.lightnessF())))
    else:
        background = QColor(palette[0])
    # The track list paper keeps the album's color but follows the Brightness setting too.
    paper_background = QColor(background)
    artwork_colors = sampled_palette + tuple(artwork_accent_palette(artwork))
    if has_limited_colors(artwork_colors):
        return keep_album_hues(muted_artwork_colors(background, paper_background), artwork_colors)
    if single_hue_without_contrast(artwork_colors, background):
        toward = max(artwork_colors, key=lambda color: color_contrast(background, color))
        return keep_album_hues(muted_artwork_colors(background, paper_background, toward), artwork_colors)
    background = readable_background(background, mode)
    text_minimum = 7.0 if paper_background.lightnessF() >= .5 else 4.5
    text = sampled_artwork_text_color(
        tuple(background.darker(factor) for factor in (100, 120, 130)),
        sampled_palette, text_minimum, paper_background.lightnessF() >= .5, paper=paper_background)
    details = tuple(comfortable_color(color) for color in artwork_accent_palette(artwork))
    accent, fill = application_controls(background, palette, details)
    colors = simplify_theme_colors({key: color.name() for key, color in {
        'themeBackground': background,
        'themeAccent': accent,
        'buttonFill': fill,
        'textColor': text,
        'brandTextColor': accent,
    }.items()})
    background = QColor(colors['themeBackground'])
    accent = QColor(colors['themeAccent'])
    text_palette = tuple(sorted(sampled_palette, key=lambda color: color.lightnessF(),
                                reverse=paper_background.lightnessF() < .5))
    text_minimum = 7.0 if paper_background.lightnessF() >= .5 else 4.5
    text = sampled_artwork_text_color(
        tuple(background.darker(factor) for factor in (100, 120, 130)),
        text_palette, text_minimum, paper_background.lightnessF() >= .5, paper=paper_background).name()
    colors.update({key: text for key in ('textColor', 'secondaryTextColor', 'folderArrowColor')})
    button_icon = artwork_text_color((accent,), palette).name()
    colors.update({key: text for key in ('buttonTextColor', 'disabledTextColor')})
    colors['buttonIconColor'] = button_icon
    colors.update({
        'selectedTextColor': text,
        'timelineTextColor': text,
        'paperTextColor': text,
    })
    accent = comfortable_surface(accent)
    highlight = comfortable_surface(application_highlight(background, accent, text, palette + details))
    if colors_too_similar(highlight, accent):
        highlight = comfortable_surface(distinct_artwork_color(background, accent, palette + details))
    highlight = highlight.name()
    colors['themeHighlight'] = accent.name()
    colors['themeBackgroundAccent'] = artwork_background_accent(
        background, highlight, palette + details).name()
    colors['brandTextColor'] = accent.name()
    colors['headingTextColor'] = text
    colors.update(themeAccent=highlight, timelineColor=highlight, selectedTextColor=text)
    button_icon = QColor(colors['themeBackgroundAccent']).name()
    colors.update({key: colors['themeBackgroundAccent'] for key in
                   ('buttonTextColor', 'disabledTextColor', 'buttonIconColor')})
    colors = keep_album_hues(unique_artwork_colors(soften_theme_colors(colors), palette + details, sampled_palette,
                                                   text_minimum, paper_background, color_range),
                             artwork_colors + tuple(color for color, _ in color_range))
    return keep_album_lightness(colors, color_range, artwork_colors)


def classic_artwork_style(style, colors):
    """Retain classic geometry while recoloring all of its fixed surfaces."""
    background = QColor(colors['themeBackground'])
    accent = QColor(colors['themeAccent'])
    replacements = {
        '#16191e': background.name(), '#1c2128': background.darker(110).name(),
        '#191d23': background.darker(119).name(), '#222831': background.darker(115).name(),
        '#262e38': background.darker(120).name(), '#303945': background.lighter(115).name(),
        '#38424d': background.darker(130).name(), '#2b333e': colors['buttonFill'],
        '#3b4654': accent.name(), '#3b4959': colors['buttonFill'],
        '#36414e': accent.name(), '#3b4c3a': accent_shade(accent.name(), .32),
        '#222b30': background.darker(115).name(), '#344735': accent_shade(accent.name(), .32),
        '#bddc9c': accent.name(), '#e0edcf': colors['buttonFill'],
        '#566272': accent.name(),
    }
    # Replace in one pass so a sampled color cannot be replaced again.
    return re.sub(r'#[0-9a-fA-F]{6}', lambda match: replacements.get(match[0], match[0]), style)
