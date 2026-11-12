"""Settle scroll areas so the top row (an item, or a settings row) lines up with the top edge, like the album list."""

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QObject, QPoint, QTimer, Qt, QVariantAnimation
from PySide6.QtWidgets import QAbstractItemView, QApplication, QFormLayout, QScrollArea, QScroller

from themes import BUTTON_SHADOW

SNAP_SETTLE_MS = 180


def layout_bands(layout):
    """Top and bottom of each row's visible part; controls keep empty shadow room above and below their faces."""
    bands = []
    if layout is None:
        return bands
    if isinstance(layout, QFormLayout):
        rows = [[layout.itemAt(row, role) for role in (QFormLayout.LabelRole, QFormLayout.FieldRole, QFormLayout.SpanningRole)]
                for row in range(layout.rowCount())]
    else:
        rows = [[layout.itemAt(index)] for index in range(layout.count())]
    for items in rows:
        geometries = [item.geometry() for item in items if item is not None and not item.geometry().isEmpty()
                      and (item.widget() is None or item.widget().isVisible())]
        if geometries:
            top = min(geometry.top() for geometry in geometries)
            bottom = max(geometry.bottom() + 1 for geometry in geometries)
            bands.append((top, bottom, max(top, min(top + BUTTON_SHADOW, bottom)), max(top, bottom - 2)))
    return bands


class TopSnap(QObject):
    def __init__(self, area):
        super().__init__(area)
        self.area = area
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SNAP_SETTLE_MS)
        self.timer.timeout.connect(self.snap)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.glide)
        self.gliding = False
        self.wheel_remainder = 0
        area.verticalScrollBar().valueChanged.connect(self.schedule)
        if getattr(area, 'scroll_animation', None) is None:
            area.viewport().installEventFilter(self)

    def glide(self, value):
        self.gliding = True
        try:
            self.area.verticalScrollBar().setValue(round(value))
        finally:
            self.gliding = False

    def schedule(self, *args):
        if self.gliding:
            return
        # Anything else moving the view wins over a settle that is still gliding.
        self.animation.stop()
        self.timer.start()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel and watched is self.area.viewport() and self.wheel(event):
            return True
        return False

    def stops(self):
        area = self.area
        bar = area.verticalScrollBar()
        if isinstance(area, QAbstractItemView):
            if area.verticalScrollMode() != QAbstractItemView.ScrollPerPixel:
                return None
            height = area.sizeHintForRow(0) if hasattr(area, 'sizeHintForRow') else 0
            if height <= 0:
                return None
            return [*range(bar.minimum(), bar.maximum(), height), bar.maximum()], QApplication.wheelScrollLines()
        options = self.candidates(bar.value())
        if not options:
            return None
        clamped = sorted({min(bar.maximum(), max(bar.minimum(), option)) for option in options} | {bar.minimum(), bar.maximum()})
        return clamped, 2

    def wheel(self, event):
        # Touchpads scroll by pixels and settle afterwards; mouse wheels step from stop to stop.
        if event.pixelDelta().y() or not event.angleDelta().y() or event.modifiers() != Qt.NoModifier:
            return False
        found = self.stops()
        if found is None:
            return False
        stops, per_notch = found
        self.wheel_remainder += event.angleDelta().y()
        steps = int(self.wheel_remainder / 120)
        self.wheel_remainder -= steps * 120
        if not steps:
            event.accept()
            return True
        bar = self.area.verticalScrollBar()
        base = self.animation.endValue() if self.animation.state() == QAbstractAnimation.Running else bar.value()
        index = min(range(len(stops)), key=lambda position: abs(stops[position] - base))
        target = stops[max(0, min(len(stops) - 1, index - steps * per_notch))]
        self.timer.stop()
        self.animation.stop()
        self.animation.setStartValue(float(bar.value()))
        self.animation.setEndValue(float(target))
        self.animation.start()
        event.accept()
        return True

    def busy(self):
        bars = [self.area.verticalScrollBar()]
        side = getattr(self.area, 'side_bar', None)
        if side is not None:
            bars.append(side)
        own = getattr(self.area, 'scroll_animation', None)
        return (any(bar.isSliderDown() for bar in bars)
                or QApplication.mouseButtons() != Qt.NoButton
                or (own is not None and own.state() == QAbstractAnimation.Running)
                or (QScroller.hasScroller(self.area.viewport())
                    and QScroller.scroller(self.area.viewport()).state() != QScroller.Inactive))

    def candidates(self, value):
        area = self.area
        if isinstance(area, QAbstractItemView):
            if area.verticalScrollMode() != QAbstractItemView.ScrollPerPixel:
                return []
            for y in range(0, min(8, area.viewport().height())):
                index = area.indexAt(QPoint(1, y))
                if index.isValid():
                    rect = area.visualRect(index)
                    top = value + rect.top()
                    return [top, top + rect.height()]
            return []
        if isinstance(area, QScrollArea) and area.widget() is not None:
            bands = layout_bands(area.widget().layout())
            if not bands:
                return []
            gap = min(band[0] for band in bands)
            options = {band[0] - gap for band in bands} | {band[3] for band in bands}
            # A stop is only good if no row's visible part straddles the top edge.
            return [option for option in options
                    if not any(visible_top < option < visible_bottom for _, _, visible_top, visible_bottom in bands)]
        return []

    def snap(self):
        if not self.area.isVisible():
            return
        if self.busy():
            self.timer.start()
            return
        bar = self.area.verticalScrollBar()
        value = bar.value()
        if value <= bar.minimum() or value >= bar.maximum():
            return
        options = [min(bar.maximum(), max(bar.minimum(), top)) for top in self.candidates(value)]
        if not options:
            return
        target = min(options, key=lambda top: abs(top - value))
        if target != value:
            self.animation.stop()
            self.animation.setStartValue(float(value))
            self.animation.setEndValue(float(target))
            self.animation.start()


def install_top_snap(area):
    ancestor = area
    while ancestor is not None:
        if ancestor.objectName() == 'albumGrid':
            return None
        ancestor = ancestor.parentWidget()
    if not isinstance(area, (QAbstractItemView, QScrollArea)) or hasattr(area, 'top_snap'):
        return getattr(area, 'top_snap', None)
    area.top_snap = TopSnap(area)
    return area.top_snap
