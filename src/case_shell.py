"""Molded jewel-case variants; sleeve artwork is never changed on disk."""
from hashlib import blake2b
from functools import lru_cache
from io import BytesIO
import colorsys
from threading import Lock
from PIL import Image
from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform
from case_finish import paint_case_finish
from case_geometry import CASE_WIDTH, CASE_HEIGHT, CASE_PIXMAP_SIZE, sleeve_rect
from themes import control_body, control_offset, control_property, control_shadow, control_shadow_body


CASE_DEPTH = 6
CASE_SHADOW_ENABLED = True
CASE_SHADOW_DEPTH = 8
CASE_RADIUS = 2.4
CASE_COLOR = '#dddddd'
CASE_COLORS = (
    ('#a7b3b6', '#202224', '#dce2e3'),
    ('#bcc5c6', '#292b2c', '#e6e9e8'),
    ('#899295', '#25282a', '#cbd2d4'),
    ('#b9b9ac', '#252624', '#deded2'),
)


def case_frame_color():
    background = QColor(control_property('themeBackground') or '#808080')
    amount = min(1, max(0, background.lightnessF() * 2))
    amount = amount * amount * (3 - 2 * amount)
    value = round(136 + (221 - 136) * amount)
    return QColor(value, value, value)


def paint_live_frame(painter, target, color):
    painter.save()
    painter.translate(target.topLeft())
    painter.scale(target.width() / CASE_WIDTH, target.height() / CASE_HEIGHT)
    rect = QRectF(0, 0, CASE_WIDTH, CASE_HEIGHT)
    sleeve = sleeve_rect(rect)
    spine = QRectF(0, sleeve.top(), sleeve.left() - 3.4, sleeve.height())
    outline = QPainterPath()
    outline.addRoundedRect(rect.adjusted(.4, .4, -.4, -.4), CASE_RADIUS, CASE_RADIUS)
    contents = QPainterPath()
    contents.addRect(sleeve)
    contents.addRect(spine)
    painter.setClipPath(outline.subtracted(contents), Qt.IntersectClip)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPath(outline)
    painter.setBrush(color.darker(140))
    for area in (sleeve, spine):
        painter.drawRoundedRect(area.adjusted(-1, -1, 1, 1), 1, 1)
    painter.restore()


def fitted_case_rect(rect):
    shadow = control_shadow(CASE_SHADOW_DEPTH)
    available = QRectF(rect).adjusted(CASE_DEPTH - shadow.x(), CASE_DEPTH, -CASE_DEPTH, -shadow.y())
    size = QSizeF(CASE_WIDTH, CASE_HEIGHT).scaled(available.size(), Qt.KeepAspectRatio)
    target = QRectF(QPointF(), size)
    target.moveCenter(available.center())
    return target


def paint_cd_case(painter, widget, rect, pixmap, key='', angle=0, visible=None, shadow=True):
    offset = control_offset(widget, rect, CASE_DEPTH)
    target = rect.translated(-offset)
    scale_x, scale_y = rect.width() / CASE_WIDTH, rect.height() / CASE_HEIGHT
    face = target.adjusted(scale_x * .4, scale_y * .4, -scale_x * .4, -scale_y * .4)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.translate(rect.center())
    painter.rotate(angle)
    painter.translate(-rect.center())
    geometry = tuple(round(value, 3) for value in
                     (face.width(), face.height(), CASE_RADIUS * min(scale_x, scale_y), offset.x(), offset.y()))
    shadow_offset = QTransform().rotate(-angle).map(control_shadow(CASE_SHADOW_DEPTH))
    if CASE_SHADOW_ENABLED and shadow and not shadow_offset.isNull():
        footprint = control_shadow_body(*geometry, round(shadow_offset.x(), 3), round(shadow_offset.y(), 3))
        painter.fillPath(footprint.translated(face.topLeft()), QColor(0, 0, 0, 65))
    body = control_body(*geometry).translated(face.topLeft())
    frame = case_frame_color()
    painter.fillPath(body, frame.darker(125))
    if offset.x() < 0:
        sleeve = sleeve_rect(target)
        top = QPointF(face.left(), sleeve.top())
        bottom = QPointF(face.left(), sleeve.bottom())
        tray_body = QPainterPath()
        tray_body.addPolygon(QPolygonF((top, bottom, bottom + offset, top + offset)))
        tray_body.closeSubpath()
        tray = pixmap.toImage().pixelColor(round(pixmap.width() * 2.3 / CASE_WIDTH), pixmap.height() // 2)
        painter.save()
        painter.setClipPath(body, Qt.IntersectClip)
        painter.fillPath(tray_body, tray.darker(125))
        painter.restore()
    painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
    paint_live_frame(painter, target, frame)
    painter.restore()
    painted = rect.translated(QTransform().rotate(angle).map(-offset))
    paint_case_finish(painter, painted, angle, key, visible)
    return painted


def case_variant(key):
    if not key:
        return 0
    return int.from_bytes(blake2b(str(key).encode('utf-8', 'surrogatepass'), digest_size=4,
                                person=b'casebody').digest(), 'big') % 4


@lru_cache(maxsize=256)
def artwork_tray_color(artwork):
    """Reserve colored trays for mostly neutral sleeves with isolated vivid ink."""
    if not artwork:
        return None
    try:
        with Image.open(BytesIO(artwork)) as source:
            image = source.convert('RGBA')
            side = min(image.size)
            left, top = (image.width - side) // 2, (image.height - side) // 2
            image = image.crop((left, top, left + side, top + side)).resize((48, 48))
        total = neutral = vivid = 0
        hues = [0] * 24
        colors = []
        for count, rgba in image.getcolors(2304) or ():
            r, g, b, alpha = rgba
            if alpha < 128:
                continue
            total += count
            hue, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if max(r, g, b) - min(r, g, b) < 22 or saturation < .18:
                neutral += count
            elif saturation >= .55 and value >= .3:
                vivid += count
                hues[int(hue * 24) % 24] += count
                colors.append((count, hue, r, g, b))
        if not total or neutral / total < .3 or not .025 <= vivid / total <= .65:
            return None
        if (total - neutral - vivid) / total > .15:
            return None
        # One or two concentrated hues; broad photographic palettes stay black.
        peak = max(range(24), key=lambda index: sum(hues[(index + offset) % 24] for offset in (-1, 0, 1)))
        primary = sum(hues[(peak + offset) % 24] for offset in (-1, 0, 1))
        remaining = [count if min((index - peak) % 24, (peak - index) % 24) > 2 else 0
                     for index, count in enumerate(hues)]
        secondary = max(sum(remaining[(index + offset) % 24] for offset in (-1, 0, 1)) for index in range(24))
        if primary / vivid < .68 or (primary + secondary) / vivid < .94:
            return None
        ink = [(count, r, g, b) for count, hue, r, g, b in colors
               if min((hue - peak / 24) % 1, (peak / 24 - hue) % 1) <= 1.5 / 24]
        weight = sum(row[0] for row in ink)
        if not weight:
            return None
        color = QColor(*(round(sum(row[0] * row[channel] for row in ink) / weight) for channel in (1, 2, 3)))
        color.setHslF(color.hslHueF(), color.hslSaturationF(), max(.3, min(.58, color.lightnessF())))
        return color.name()
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


_shell_lock = Lock()


def shell_image(tray_color=''):
    # Shared by the case loader threads; QImage is safe to paint from any thread.
    with _shell_lock:
        return cached_shell_image(tray_color)


@lru_cache(maxsize=32)
def shell_pixmap(tray_color=''):
    return QPixmap.fromImage(shell_image(tray_color))


@lru_cache(maxsize=32)
def cached_shell_image(tray_color=''):
    pixmap = QImage(CASE_PIXMAP_SIZE, QImage.Format_ARGB32_Premultiplied)
    pixmap.setDevicePixelRatio(CASE_PIXMAP_SIZE.width() / CASE_WIDTH)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    rect = QRectF(0, 0, CASE_WIDTH, CASE_HEIGHT)
    frame = QColor(CASE_COLOR)
    painter.setBrush(frame)
    painter.drawRoundedRect(rect.adjusted(.4, .4, -.4, -.4), CASE_RADIUS, CASE_RADIUS)
    sleeve = sleeve_rect(rect)
    painter.setBrush(frame.darker(140))
    painter.drawRoundedRect(sleeve.adjusted(-1, -1, 1, 1), 1, 1)
    painter.fillRect(sleeve, QColor('#f2efdf'))
    tray = QColor(tray_color or '#343936')
    spine = QRectF(0, sleeve.top(), sleeve.left() - 3.4, sleeve.height())
    outline = QPainterPath()
    outline.addRoundedRect(rect.adjusted(.4, .4, -.4, -.4), CASE_RADIUS, CASE_RADIUS)
    painter.save()
    painter.setClipPath(outline, Qt.IntersectClip)
    painter.setBrush(frame.darker(140))
    painter.drawRoundedRect(spine.adjusted(-1, -1, 1, 1), 1, 1)
    painter.fillRect(spine, tray)
    painter.setPen(QPen(tray.lighter(125), .65, Qt.SolidLine, Qt.FlatCap))
    stripes = max(2, round(spine.width() / 2.3))
    for index in range(stripes):
        x = (index + .5) * spine.width() / stripes
        painter.drawLine(QPointF(x, spine.top()), QPointF(x, spine.bottom()))
    painter.restore()
    painter.end()
    return pixmap


def paint_shell(painter, key, artwork=b'', tray_color=None):
    tray = artwork_tray_color(artwork) if tray_color is None else tray_color
    shell = shell_image(QColor(tray).name() if tray else '')
    painter.drawImage(QRectF(0, 0, CASE_WIDTH, CASE_HEIGHT), shell, QRectF(shell.rect()))
