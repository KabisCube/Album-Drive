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
    surfaces = ('themeAccent', 'themeHighlight', 'buttonFill')
    return {key: (comfortable_surface(value) if key in surfaces else comfortable_color(value)).name()
            for key, value in colors.items()}


def button_text_color_for_palette(colors):
    background = QColor(colors['themeAccent'])
    current = QColor(colors['buttonTextColor'])
    if color_contrast(background, current) >= 4.5:
        return current.name()
    return artwork_text_color((background,), tuple(colors[prop] for prop in
                              ('buttonTextColor', 'textColor', 'themeHighlight', 'themeBackground'))).name()


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
    button_text = artwork_text_color((accent,), (text, highlight, background))
    logo_background = background.darker(110)
    paper_text = QColor(SOFT_BLACK)
    colors.update({key: value.name() for key, value in {
        'themeHighlight': highlight, 'timelineColor': accent, 'brandTextColor': highlight, 'brandLineColor': logo_background,
        'folderArrowColor': text, 'buttonIconColor': button_text, 'buttonTextColor': button_text,
        'disabledTextColor': button_text, 'secondaryTextColor': text, 'headingTextColor': highlight,
        'selectedTextColor': contrasting_text(QColor(accent_shade(accent.name(), .32))),
        'timelineTextColor': contrasting_text(background.darker(130)),
        'paperTextColor': paper_text,
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


def application_highlight(background, accent, text, palette):
    existing = (background, accent, QColor(text))
    def hue_distance(color):
        distance = abs(color.hslHueF() - background.hslHueF())
        return min(distance, 1 - distance)
    chromatic_background = background.hslSaturationF() >= .12
    different_hues = tuple(color for color in palette if color.hslSaturationF() >= .12
                          and max(color.getRgb()[:3]) - min(color.getRgb()[:3]) >= 12
                          and hue_distance(color) >= 1 / 12
                          and sum((a - b) ** 2 for a, b in zip(background.getRgb()[:3], color.getRgb()[:3])) >= 32 ** 2
                          ) if chromatic_background else ()
    candidates = different_hues or tuple(color for color in palette if color_contrast(background, color) >= 1.3)
    if not candidates:
        return artwork_scrollbar_colors(background, palette)[0]
    def distinction(color):
        distance = min(sum((a - b) ** 2 for a, b in zip(color.getRgbF()[:3], other.getRgbF()[:3]))
                       for other in existing)
        separation = .8 * hue_distance(color) if different_hues else 0
        return distance + .08 * color.hslSaturationF() + separation
    return max(candidates, key=distinction)


def artwork_theme_colors(artwork, mode='any'):
    """Use this cover, falling back to saved colors for unusable artwork."""
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
        background = palette[0]
    text = (QColor(SOFT_WHITE) if mode == 'dark' else QColor(SOFT_BLACK) if mode == 'light'
            else max((QColor(SOFT_WHITE), QColor(SOFT_BLACK)),
                     key=lambda candidate: min(color_contrast(background.darker(factor), candidate)
                                               for factor in (100, 120, 130))))
    for _ in range(100):
        background = comfortable_color(QColor(background.name()))
        if min(color_contrast(background.darker(factor), text) for factor in (100, 120, 130)) >= 4.6:
            break
        background.setHslF(background.hslHueF(), background.hslSaturationF(),
                           max(16 / 255, min(244 / 255, background.lightnessF()
                               + (-.01 if text == QColor(SOFT_WHITE) else .01))))
    for _ in range(100):
        surfaces = tuple(background.darker(factor) for factor in (100, 120, 130))
        artwork_text = artwork_text_color(surfaces, palette)
        if min(color_contrast(surface, artwork_text) for surface in surfaces) >= 4.6:
            break
        background.setHslF(background.hslHueF(), background.hslSaturationF(),
                           max(16 / 255, min(244 / 255, background.lightnessF()
                               + (-.005 if text == QColor(SOFT_WHITE) else .005))))
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
    text = artwork_text_color(tuple(background.darker(factor) for factor in (100, 120, 130)), palette).name()
    button_text = artwork_text_color((accent,), palette).name()
    paper_text = artwork_text_color((QColor('#f2efdf'),), palette).name()
    colors.update({key: text for key in ('textColor', 'secondaryTextColor', 'folderArrowColor')})
    colors.update({key: button_text for key in ('buttonTextColor', 'buttonIconColor', 'disabledTextColor')})
    colors.update({
        'selectedTextColor': artwork_text_color((QColor(accent_shade(accent.name(), .32)),), palette).name(),
        'timelineTextColor': artwork_text_color((background.darker(130),), palette).name(),
        'paperTextColor': paper_text,
    })
    highlight = comfortable_surface(application_highlight(background, accent, text, palette + details)).name()
    accent = comfortable_surface(accent)
    colors['themeHighlight'] = accent.name()
    colors.update({key: accent.name() for key in ('brandTextColor', 'headingTextColor')})
    colors.update(themeAccent=highlight, timelineColor=highlight,
                  selectedTextColor=artwork_text_color((QColor(accent_shade(highlight, .32)),), palette).name())
    button_text = artwork_text_color((QColor(highlight),), palette).name()
    colors.update({key: button_text for key in ('buttonTextColor', 'buttonIconColor', 'disabledTextColor')})
    return soften_theme_colors(colors)


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
