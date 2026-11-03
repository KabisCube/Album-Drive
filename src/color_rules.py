"""Comfortable theme extremes and visible slider rails on dark backgrounds."""
from functools import lru_cache
from PySide6.QtGui import QColor

SOFT_BLACK = '#101010'
SOFT_WHITE = '#f4f4f4'


def emphasized_text(text, background, amount=.14):
    color = QColor(text)
    lightness = color.lightnessF()
    lightness += (1 - lightness) * amount if QColor(background).lightnessF() < .5 else -lightness * amount
    color.setHslF(color.hslHueF(), color.hslSaturationF(), lightness, color.alphaF())
    return color


def settings_title_color(text, background):
    return QColor(*(round(first * .88 + second * .12) for first, second in
                    zip(QColor(text).getRgb()[:3], QColor(background).getRgb()[:3])))


def disabled_text_color(value):
    color = QColor(value)
    color.setAlphaF(color.alphaF() * .45)
    return color


def color_contrast(first, second):
    def luminance(color):
        channels = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
                    for channel in (color.redF(), color.greenF(), color.blueF())]
        return sum(channel * weight for channel, weight in zip(channels, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


def artwork_text_color(backgrounds, palette, minimum=4.6):
    return QColor(_artwork_text_color(tuple(QColor(color).name() for color in backgrounds),
                                      tuple(comfortable_color(color).name() for color in palette), minimum))


@lru_cache(maxsize=1024)
def _artwork_text_color(backgrounds, palette, minimum):
    surfaces = tuple(QColor(color) for color in backgrounds)
    colors = tuple(QColor(color) for color in dict.fromkeys(palette))
    colorful = tuple(color for color in colors if color.hslSaturationF() >= .12
                     and max(color.getRgb()[:3]) - min(color.getRgb()[:3]) >= 12)
    originals = colors
    colors = colorful or colors or (QColor(SOFT_WHITE), QColor(SOFT_BLACK))
    def contrast(color):
        return min(color_contrast(surface, color) for surface in surfaces)
    for color in colors:
        if contrast(color) >= minimum:
            return color.name()
    for color in originals:
        if contrast(color) >= minimum:
            return color.name()
    colors = originals or colors
    variants = []
    for index, color in enumerate(colors):
        for lightness in (16 / 255, 244 / 255):
            target = QColor.fromHslF(color.hslHueF(), color.hslSaturationF(), lightness)
            if contrast(target) < minimum:
                continue
            low, high = 0, 1
            for _ in range(14):
                amount = (low + high) / 2
                candidate = QColor.fromHslF(color.hslHueF(), color.hslSaturationF(),
                                            color.lightnessF() + (lightness - color.lightnessF()) * amount)
                if contrast(QColor(candidate.name())) >= minimum:
                    high = amount
                else:
                    low = amount
            candidate = QColor.fromHslF(color.hslHueF(), color.hslSaturationF(),
                                        color.lightnessF() + (lightness - color.lightnessF()) * high)
            variants.append((abs(candidate.lightnessF() - color.lightnessF()) + index * .005, candidate.name()))
    if variants:
        return min(variants)[1]
    extremes = [QColor.fromHslF(color.hslHueF(), color.hslSaturationF(), lightness)
                for color in colors for lightness in (16 / 255, 244 / 255)]
    extremes.extend((QColor(SOFT_BLACK), QColor(SOFT_WHITE)))
    return max(extremes, key=contrast).name()


def comfortable_color(value):
    color = QColor(value)
    lightness = color.lightnessF()
    if lightness < 16 / 255 or lightness > 244 / 255:
        color.setHslF(color.hslHueF(), color.hslSaturationF(),
                      max(16 / 255, min(244 / 255, lightness)), color.alphaF())
    return color


def comfortable_surface(value):
    return QColor(_comfortable_surface(QColor(value).name()))


@lru_cache(maxsize=512)
def _comfortable_surface(value):
    color = comfortable_color(value)
    hue, saturation, lightness, alpha = color.getHslF()
    lightness = max(36 / 255, lightness)
    color = QColor.fromHslF(hue, saturation, lightness, alpha)
    inks = (QColor(SOFT_BLACK), QColor(SOFT_WHITE))
    def readable(candidate):
        return max(color_contrast(candidate, ink) for ink in inks) >= 4.6
    if readable(color):
        return color.name()
    candidates = []
    for target in (36 / 255, 244 / 255):
        low, high = 0, 1
        for _ in range(14):
            amount = (low + high) / 2
            candidate = QColor(QColor.fromHslF(hue, saturation, lightness + (target - lightness) * amount).name())
            if readable(candidate):
                high = amount
            else:
                low = amount
        candidate = QColor.fromHslF(hue, saturation, lightness + (target - lightness) * high)
        candidates.append((abs(candidate.lightnessF() - lightness), candidate.name()))
    return min(candidates)[1]


def slider_rail(value):
    return QColor(_slider_rail(QColor(value).name()))


def timeline_colors(background, accent):
    background = QColor(background)
    unfilled = slider_rail(background)
    filled = QColor(accent).darker(125)
    if min(color_contrast(surface, filled) for surface in (background, unfilled)) < 2.25:
        filled = artwork_text_color((background, unfilled), (filled,), minimum=2.25)
    return unfilled, filled, unfilled, filled


@lru_cache(maxsize=256)
def _slider_rail(value):
    background = QColor(value)
    hue, saturation, lightness, _ = background.getHslF()
    target = max((.04, .96), key=lambda level: color_contrast(
        background, QColor.fromHslF(hue, saturation, level)))
    low, high = 0, 1
    for _ in range(14):
        amount = (low + high) / 2
        color = QColor(QColor.fromHslF(hue, saturation, lightness + (target - lightness) * amount).name())
        if color_contrast(background, color) >= 2.25:
            high = amount
        else:
            low = amount
    return QColor.fromHslF(hue, saturation, lightness + (target - lightness) * high).name()
