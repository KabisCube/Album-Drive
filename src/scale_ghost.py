"""A snapshot of a control that springs down to nothing where the control used to be."""

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QWidget

from snap_scroll import SpringScroll

POP_FREQUENCY = 16.0
POP_DAMPING = .6
SLIDE_DAMPING = .8


def pop_spring(parent, damping=POP_DAMPING):
    return SpringScroll(parent, frequency=POP_FREQUENCY, damping=damping, settle_distance=.004, settle_speed=.05)


class ScaleGhost(QWidget):
    def __init__(self, parent, pixmap, rect, source=None, grow=False, finished=None, follow=None):
        super().__init__(parent)
        self.finished = finished
        self.follow = follow
        self.pixmap = pixmap
        ratio = pixmap.devicePixelRatio()
        area = QRectF(source) if source is not None else QRectF(0, 0, rect.width(), rect.height())
        self.source = QRectF(area.x() * ratio, area.y() * ratio, area.width() * ratio, area.height() * ratio)
        self.setGeometry(rect)
        self.spring = pop_spring(self)
        self.spring.jump(0 if grow else 1)
        self.spring.moved.connect(self.step)
        self.spring.glide(1 if grow else 0)
        self.show()
        self.raise_()

    def follow_target(self):
        try:
            if self.follow is not None and self.follow.isVisible():
                self.setGeometry(QRect(self.follow.mapTo(self.parentWidget(), QPoint()), self.follow.size()))
        except RuntimeError:
            self.follow = None

    def step(self):
        self.follow_target()
        if not self.spring.moving:
            if self.finished is not None:
                finished, self.finished = self.finished, None
                finished()
            self.deleteLater()
        self.update()

    def paintEvent(self, event):
        scale = max(0.0, self.spring.value)
        if scale <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        center = QPointF(self.width() / 2, self.height() / 2)
        size = QPointF(self.width() * scale / 2, self.height() * scale / 2)
        painter.drawPixmap(QRectF(center - size, center + size), self.pixmap, self.source)


def snapshot(widget):
    """The control alone on a transparent background, so it never drags a box of window colour over its neighbours."""
    ratio = widget.devicePixelRatioF()
    pixmap = QPixmap(max(1, round(widget.width() * ratio)), max(1, round(widget.height() * ratio)))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    widget.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return pixmap


def ghost_on_hide(widget):
    """When the layout hides a control, or the small row holding it, shrink a snapshot where it was."""
    window = widget.window()
    if widget is window or not window.isVisible() or isinstance(widget, ScaleGhost):
        return
    hidden = widget
    while hidden is not None and hidden is not window and not hidden.isHidden():
        hidden = hidden.parentWidget()
    if hidden is None or hidden is window:
        return
    parent = hidden.parentWidget()
    if parent is None or not parent.isVisible() or isinstance(parent, QStackedWidget):
        return
    if hidden is not widget and hidden.height() > max(160, 3 * widget.height()):
        return
    now = time.monotonic()
    if now - getattr(hidden, '_ghost_at', 0) < .1:
        return
    hidden._ghost_at = now
    if hidden.width() <= 0 or hidden.height() <= 0:
        return
    if not getattr(hidden, 'own_appear_animation', False):
        hidden._hidden_by_layout = True
    ScaleGhost(window, snapshot(hidden), QRect(hidden.mapTo(window, QPoint()), hidden.size()))


def grow_on_show(widget):
    """A control the layout hid earlier springs back in from nothing when it reappears."""
    window = widget.window()
    shown = widget
    while shown is not None and shown is not window and not getattr(shown, '_hidden_by_layout', False):
        shown = shown.parentWidget()
    if shown is None or shown is window or not window.isVisible():
        return
    shown._hidden_by_layout = False
    veil(shown)
    QTimer.singleShot(0, lambda: grow_widget(shown))


def veil(widget):
    """Hide a control's paint at once, keeping any opacity effect it already uses, until its snapshot has grown."""
    if getattr(widget, '_veil', None) is not None:
        return widget._veil
    effect = widget.graphicsEffect()
    if effect is not None and not isinstance(effect, QGraphicsOpacityEffect):
        return None
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        restore = None
    else:
        restore = effect.opacity()
    effect.setOpacity(0)
    widget._veil = (effect, restore)
    return widget._veil


def lift_veil(widget):
    try:
        effect, restore = widget._veil
        widget._veil = None
        if widget.graphicsEffect() is effect:
            if restore is None:
                widget.setGraphicsEffect(None)
            else:
                effect.setOpacity(restore)
    except (RuntimeError, AttributeError, TypeError):
        pass


def grow_widget(widget, parent=None, rect=None):
    try:
        if not widget.isVisible() or widget.width() <= 0 or getattr(widget, '_growing', False):
            lift_veil(widget)
            return
    except RuntimeError:
        return
    veiled = veil(widget)
    if veiled is None:
        return
    effect, restore = veiled
    parent = parent or widget.window()
    rect = rect or QRect(widget.mapTo(parent, QPoint()), widget.size())
    effect.setOpacity(1 if restore is None else restore)
    pixmap = snapshot(widget)
    effect.setOpacity(0)
    widget._growing = True

    def reveal():
        widget._growing = False
        lift_veil(widget)
    ScaleGhost(parent, pixmap, rect, grow=True, finished=reveal, follow=widget)


def show_with_grow(widget):
    if not widget.isHidden():
        return
    window = widget.window()
    if window.isVisible():
        veil(widget)
        widget.show()
        QTimer.singleShot(0, lambda: grow_widget(widget))
    else:
        widget.show()


def hide_with_shrink(widget):
    if widget.isHidden():
        return
    window = widget.window()
    if window.isVisible() and widget.isVisible() and widget.width() > 0:
        ScaleGhost(window, snapshot(widget), QRect(widget.mapTo(window, QPoint()), widget.size()))
    widget.hide()
