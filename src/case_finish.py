"""Soft, stable per-album plastic finishes drawn separately from sleeve art."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QApplication
from case_geometry import sleeve_rect


@dataclass(frozen=True)
class Scratch:
    points: tuple
    width: float
    alphas: tuple


@dataclass(frozen=True)
class CaseFinish:
    variant: int
    center: float
    spread: float
    strength: int
    direction: float
    scratches: tuple


# One light source for the whole view; only wear belongs to individual cases.
SHARED_LIGHT = CaseFinish(0, .52, .46, 88, 36, ())


def worn_plastic(rng, light=False):
    """Loose crossing hairlines, with tapered ends and intermittent abrasion."""
    scratches = []
    for group in range(1 if light else rng.randint(2, 3)):
        direction = math.radians(rng.uniform(-78, -48) if group % 2 == 0 else rng.uniform(48, 78))
        center_x, center_y = rng.uniform(.2, .8), rng.uniform(.25, .75)
        for _ in range(rng.randint(4, 6) if light else rng.randint(4, 7)):
            angle = direction + rng.uniform(-.23, .23)
            length = rng.uniform(.06, .28) if light else rng.uniform(.07, .4)
            dx, dy = math.cos(angle) * length, math.sin(angle) * length
            x = max(.02, min(.98, center_x + rng.gauss(0, .17))) - dx / 2
            y = max(.02, min(.98, center_y + rng.gauss(0, .17))) - dy / 2
            bend = length * rng.uniform(-.025, .025)
            points = tuple((x + dx * t - math.sin(angle) * bend * math.sin(math.pi * t),
                            y + dy * t + math.cos(angle) * bend * math.sin(math.pi * t))
                           for t in (step / 10 for step in range(11)))
            opacity = rng.randint(55, 95) if light else rng.randint(55, 110)
            # Shallow portions catch less light; no uniformly bright cut lines.
            alphas = []
            for step in range(10):
                exposure = rng.uniform(.18, .45) if rng.random() < .18 else rng.uniform(.6, 1)
                alphas.append(round(opacity * math.sin(math.pi * (step + .5) / 10) ** .6 * exposure))
            scratches.append(Scratch(points, rng.uniform(.15, .3), tuple(alphas)))
    return tuple(scratches)


@lru_cache(maxsize=1024)
def finish_for_album(key):
    """Randomize each case once, retaining its finish through sorts/restarts."""
    seed = int.from_bytes(hashlib.blake2b(str(key).encode('utf-8', 'surrogatepass'), digest_size=8).digest(), 'big')
    rng = random.Random(seed)
    variant = rng.randrange(5)
    center, spread = rng.uniform(.2, .8), rng.uniform(.32, .56)
    strength, direction = rng.randint(65, 90), rng.uniform(30, 43)
    scratches = worn_plastic(rng, light=rng.random() >= .28)
    return CaseFinish(variant, center, spread, strength, direction, scratches)


def reflection_gradient(rect, finish, background='#393939'):
    """Lighting coordinates deliberately have no case-rotation parameter."""
    angle = math.radians(finish.direction)
    dx, dy = math.cos(angle) * rect.width() * .8, math.sin(angle) * rect.height() * .8
    gradient = QLinearGradient(rect.center() - QPointF(dx, dy), rect.center() + QPointF(dx, dy))
    ambient = QColor(background)
    for step in range(49):
        position = step / 48
        distance = (position - finish.center) / finish.spread
        glow = math.exp(-distance * distance * 2.5)
        if finish.variant in (1, 4):
            glow = .65 * glow + .3 * math.exp(-((position - .85) / .5) ** 2 * 3)
        if finish.variant == 2:
            glow *= .6
        if finish.variant == 3:
            glow = .7 * math.exp(-((position - .15) / .6) ** 2 * 2)
        # A broad reflection plus a softly focused light strip reads as a lid,
        # rather than uniformly washing out the printed sleeve.
        flare = math.exp(-((position - finish.center - .08) / .07) ** 2 * 2)
        tint = .35 * (1 - .7 * flare)
        color = QColor(*(round(244 * (1 - tint) + channel * tint)
                         for channel in (ambient.red(), ambient.green(), ambient.blue())))
        color.setAlpha(round(3 + finish.strength * (.65 * glow + .35 * flare)))
        gradient.setColorAt(position, color)
    return gradient


@lru_cache(maxsize=32)
def lighting_for_view(x, y, width, height, background='#393939'):
    rect = QRectF(x, y, width, height)
    shade = QLinearGradient(rect.topLeft(), rect.bottomRight())
    for position, alpha in ((0, 38), (.3, 12), (.58, 0), (1, 32)):
        color = QColor(background)
        color.setAlpha(alpha)
        shade.setColorAt(position, color)
    return reflection_gradient(rect, SHARED_LIGHT, background), shade


@lru_cache(maxsize=32)
def scratch_overlay(key):
    pixmap = QPixmap(432, 432)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    for scratch in finish_for_album(key).scratches:
        points = tuple(QPointF(x * 432, y * 432) for x, y in scratch.points)
        for step, alpha in enumerate(scratch.alphas):
            taper = .35 + .65 * math.sin(math.pi * (step + .5) / len(scratch.alphas)) ** .5
            painter.setPen(QPen(QColor(238, 242, 241, alpha), scratch.width * 3 * taper, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(points[step], points[step + 1])
    painter.end()
    return pixmap


def paint_case_finish(painter, rect, angle, key, lighting_rect=None):
    if not key or rect.isEmpty():
        return
    finish = finish_for_album(key)
    if lighting_rect is None:
        device = painter.device()
        ratio = device.devicePixelRatioF()
        lighting_rect = QRectF(0, 0, device.width() / ratio, device.height() / ratio)
    sleeve = sleeve_rect(rect)
    rotation = QTransform().translate(rect.center().x(), rect.center().y()).rotate(angle).translate(-rect.center().x(), -rect.center().y())
    edge = QPainterPath()
    edge.addRect(sleeve)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setClipPath(rotation.map(edge), Qt.IntersectClip)
    # Scrolling/tilting moves only the case mask through the shared light field.
    app = QApplication.instance()
    background = QColor(app.property('themeBackground') or '#393939').name()
    reflection, shade = lighting_for_view(*lighting_rect.getRect(), background)
    painter.fillRect(rotation.mapRect(sleeve), reflection)
    # A faint shaded side of the reflection also reveals plastic on white art.
    painter.fillRect(rotation.mapRect(sleeve), shade)
    # Tiny marks belong to the physical plastic and follow its rotation.
    if finish.scratches:
        painter.setWorldTransform(rotation, True)
        overlay = scratch_overlay(str(key))
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(sleeve, overlay, QRectF(overlay.rect()))
    painter.restore()
