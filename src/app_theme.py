"""Readable application colors sampled from the now-playing artwork."""

import re

from PySide6.QtGui import QColor

from open_case import artwork_accent_palette, artwork_palette, artwork_scrollbar_colors, color_contrast
from themes import accent_shade
from color_rules import artwork_text_color, comfortable_color, comfortable_surface, SOFT_BLACK, SOFT_WHITE


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


def sampled_artwork_text_color(surfaces, palette, minimum, prefer_dark, avoid=()):
    colors = tuple(dict.fromkeys(QColor(color).name() for color in palette))
    candidates = [QColor(color) for color in colors
                  if not any(colors_too_similar(QColor(color), other) for other in avoid)]
    if not candidates:
        candidates = [QColor(color) for color in colors]
    def contrast(color):
        return min(color_contrast(surface, color) for surface in surfaces)
    readable = [color for color in candidates if contrast(color) >= minimum]
    return max(readable or candidates,
               key=lambda color: (contrast(color), color.hslSaturationF()))


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


def unique_artwork_colors(colors, palette, text_palette, text_minimum):
    keys = ('themeBackground', 'themeHighlight', 'themeAccent', 'textColor', 'themeBackgroundAccent', 'buttonFill')
    seen = []
    background = QColor(colors['themeBackground'])
    paper_background = QColor(palette[0]) if palette else background
    surfaces = tuple(background.darker(factor) for factor in (100, 120, 130)) + (paper_background,)
    text_minimum = 7.0 if paper_background.lightnessF() >= .5 else 4.5
    for key in keys:
        color = QColor(colors[key])
        if key == 'textColor':
            color = sampled_artwork_text_color(surfaces, text_palette, text_minimum,
                                               paper_background.lightnessF() >= .5, seen)
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
                else:
                    for hue_step in range(12):
                        candidate_hue = (hue + hue_step / 12) % 1 if hue >= 0 else hue_step / 12
                        for candidate_saturation in (saturation, max(.2, saturation), .7):
                            for candidate_lightness in (.04, .25, .5, .75, .96):
                                candidate = QColor(QColor.fromHslF(
                                    candidate_hue, candidate_saturation, candidate_lightness).name())
                                if not any(colors_too_similar(candidate, prior) for prior in seen):
                                    distance = sum((a - b) ** 2 for a, b in zip(
                                        candidate.getRgb()[:3], color.getRgb()[:3]))
                                    variants.append((distance, candidate.name()))
                    if variants:
                        color = QColor(min(variants)[1])
        colors[key] = color.name()
        seen.append(color)
    colors['timelineColor'] = colors['themeAccent']
    colors['brandTextColor'] = colors['themeHighlight']
    colors['secondaryTextColor'] = colors['textColor']
    colors['headingTextColor'] = colors['textColor']
    colors['selectedTextColor'] = colors['textColor']
    colors['timelineTextColor'] = colors['textColor']
    colors['paperTextColor'] = colors['textColor']
    colors['buttonTextColor'] = colors['themeBackgroundAccent']
    colors['buttonIconColor'] = colors['themeBackgroundAccent']
    colors['disabledTextColor'] = colors['themeBackgroundAccent']
    return colors


def artwork_theme_colors(artwork, mode='any'):
    """Use this cover, falling back to saved colors for unusable artwork."""
    sampled_palette = tuple(artwork_palette(artwork, colors=32, minimum=.002))
    palette = tuple(comfortable_color(color) for color in artwork_palette(artwork))
    if not palette:
        return None
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
    paper_background = palette[0]
    text_minimum = 7.0 if paper_background.lightnessF() >= .5 else 4.5
    text = sampled_artwork_text_color(
        tuple(background.darker(factor) for factor in (100, 120, 130)) + (paper_background,),
        sampled_palette, text_minimum, paper_background.lightnessF() >= .5)
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
    paper_background = palette[0]
    text_palette = tuple(sorted(sampled_palette, key=lambda color: color.lightnessF(),
                                reverse=paper_background.lightnessF() < .5))
    text_minimum = 7.0 if paper_background.lightnessF() >= .5 else 4.5
    text = sampled_artwork_text_color(
        tuple(background.darker(factor) for factor in (100, 120, 130)) + (paper_background,),
        text_palette, text_minimum, paper_background.lightnessF() >= .5).name()
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
    return unique_artwork_colors(soften_theme_colors(colors), palette + details,
                                 sampled_palette, text_minimum)


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
