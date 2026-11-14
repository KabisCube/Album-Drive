from functools import lru_cache
from math import ceil, sqrt

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPointF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QHeaderView, QScrollArea, QWidget

from responsive import running_on_android
from touch_input import add_touch
from scroll_snap import install_top_snap
from themes import HALFTONE_SHADE, PANEL_SHADE, WELL_HALFTONE_SHADE, WELL_SHADE


@lru_cache(maxsize=32)
def halftone_mask(width, height, bottom, ratio):
    image = QImage(ceil(width * ratio), ceil(height * ratio), QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(Qt.white)
    spacing = 6
    for row, distance in enumerate(range(0, height, spacing)):
        y = height - 1 - distance if bottom else distance
        origin = (width // 2) % spacing + (spacing / 2 if row % 2 else 0)
        for column in range(-1, ceil(width / spacing) + 1):
            x = origin + column * spacing
            side = max(0, min(1, (x / max(1, width) - .02) / .1, (.98 - x / max(1, width)) / .1))
            radius = spacing / 2 * sqrt((1 - distance / max(1, height)) * side)
            if radius > 0:
                painter.drawEllipse(QPointF(x, y), radius, radius)
    painter.end()
    return image


class ScrollEdgeFade(QWidget):
    def __init__(self, parent, bottom=False, background_only=False):
        super().__init__(parent)
        self.bottom = bottom
        self.background_only = background_only
        self.opacity = 0.0
        self.requested_visible = False
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self.set_opacity)
        self.animation.finished.connect(self.finish_fade)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet('background: transparent;')
        self.hide()

    def reveal(self, visible):
        if visible == self.requested_visible and not (visible and self.isHidden()):
            return
        self.requested_visible = visible
        if self.isHidden():
            if visible:
                self.show()
            return
        self.animate_visibility()

    def animate_visibility(self):
        self.animation.stop()
        self.animation.setStartValue(self.opacity)
        self.animation.setEndValue(1.0 if self.requested_visible else 0.0)
        self.animation.start()

    def finish_fade(self):
        if not self.requested_visible:
            self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if self.requested_visible:
            self.animate_visibility()

    def hideEvent(self, event):
        self.animation.stop()
        self.set_opacity(0.0)
        super().hideEvent(event)

    def set_opacity(self, value):
        self.opacity = float(value)
        self.update()
        area = self.parentWidget()
        if self.background_only and isinstance(area, QAbstractScrollArea):
            viewport = area.viewport()
            if viewport is not None:
                viewport.update()
            if isinstance(area, QScrollArea) and area.widget() is not None:
                area.widget().update()

    def paintEvent(self, event):
        if not self.background_only:
            painter = QPainter(self)
            self.paint_background(painter, self.rect())

    def paint_background(self, painter, rect):
        area = self.parentWidget()
        background = area.property('paperBackgroundColor')
        if not background:
            background = QApplication.instance().property('themeBackground') or '#393939'
            if area.objectName() in ('albumDriveDropdownView', 'opticalDiscs'):
                background = QColor(background).darker(PANEL_SHADE)
            elif area.objectName() == 'fileBrowser':
                background = QColor(background).darker(WELL_SHADE)
        well = area.objectName() == 'fileBrowser' and not area.property('paperBackgroundColor')
        color = QColor(background).darker(WELL_HALFTONE_SHADE if well else HALFTONE_SHADE)
        color.setAlpha(170 if area.objectName() == 'fileBrowser' else 105)
        ratio = self.devicePixelRatioF()
        signature = (self.width(), self.height(), color.rgba(), self.bottom, ratio)
        if signature != getattr(self, '_signature', None):
            self._signature = signature
            self._image = QImage(halftone_mask(self.width(), self.height(), self.bottom, ratio))
            layer = QPainter(self._image)
            layer.setCompositionMode(QPainter.CompositionMode_SourceIn)
            layer.fillRect(self.rect(), color)
            layer.end()
        painter.save()
        painter.setOpacity(painter.opacity() * self.opacity)
        painter.drawImage(rect.topLeft(), self._image)
        painter.restore()


class ScrollEdgeShadows(QObject):
    def __init__(self, area):
        super().__init__(area)
        self.area = area
        self.fades = (ScrollEdgeFade(area, background_only=True), ScrollEdgeFade(area, bottom=True, background_only=True))
        self.content = None
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        area.verticalScrollBar().valueChanged.connect(self.update)
        area.verticalScrollBar().rangeChanged.connect(self.update)
        self.update()

    def update(self, *args):
        content = self.area.widget() if isinstance(self.area, QScrollArea) else None
        if content is not self.content:
            if self.content is not None:
                self.content.removeEventFilter(self)
            self.content = content
            if type(content) is QWidget:
                content.installEventFilter(self)
        rect = self.area.viewport().geometry()
        height = min(24, rect.height() // 4)
        bar = self.area.verticalScrollBar()
        for fade in self.fades:
            fade.setGeometry(rect.x(), rect.bottom() - height + 1 if fade.bottom else rect.y(),
                             rect.width(), height)
            fade.reveal(height > 0 and (bar.value() < bar.maximum() if fade.bottom else bar.value() > bar.minimum()))
            fade.update()
        self.area.viewport().update()
        if content is not None:
            content.update()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Paint and (watched is self.area.viewport() or watched is self.content):
            painter = QPainter(watched)
            paint_scroll_background(painter, watched)
            painter.end()
        if kind in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest, QEvent.StyleChange, QEvent.PaletteChange):
            self.update()
        return False


def paint_scroll_background(painter, widget):
    area = widget.parentWidget()
    while area is not None and not isinstance(area, QAbstractScrollArea):
        area = area.parentWidget()
    shadows = getattr(area, 'scroll_edge_shadows', None)
    if shadows is None:
        return
    for fade in shadows.fades:
        if not fade.isHidden():
            rect = fade.rect().translated(widget.mapFrom(area, fade.pos()))
            fade.paint_background(painter, rect)


class ScrollShadowInstaller(QObject):
    def eventFilter(self, widget, event):
        if event.type() != QEvent.Show or not isinstance(widget, QAbstractScrollArea):
            return False
        if running_on_android():
            add_touch(widget.viewport(), scrolls=True)
            widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        if not isinstance(widget, QHeaderView) and not hasattr(widget, 'edge_fades'):
            ancestor = widget
            while ancestor is not None:
                if ancestor.objectName() == 'albumGrid':
                    return False
                ancestor = ancestor.parentWidget()
            if not hasattr(widget, 'scroll_edge_shadows'):
                widget.scroll_edge_shadows = ScrollEdgeShadows(widget)
            install_top_snap(widget)
        return False


def install_scroll_shadows(app):
    if not hasattr(app, '_scroll_shadow_installer'):
        app._scroll_shadow_installer = ScrollShadowInstaller(app)
        app.installEventFilter(app._scroll_shadow_installer)

