"""Comfortable theme extremes and visible slider rails on dark backgrounds."""
from functools import lru_cache
from PySide6.QtGui import QColor

SOFT_BLACK = '#101010'
SOFT_WHITE = '#f4f4f4'


def disabled_text_color(value):
	return QColor(value).darker(120)


def relative_luminance(color):
	channels = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
				for channel in (color.redF(), color.greenF(), color.blueF())]
	return sum(channel * weight for channel, weight in zip(channels, (.2126, .7152, .0722)))


def color_contrast(first, second):
	light, dark = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
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


def timeline_colors(background, accent, rail=None):
	background = QColor(background)
	filled = QColor(accent)
	unfilled = QColor(rail) if rail else QColor(background).darker(130)
	filled_text = unfilled
	unfilled_text = filled
	return unfilled, filled, filled_text, unfilled_text
