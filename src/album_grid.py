"""Animated CD case browsing, without painted tile backgrounds."""

import random
import math
from collections import OrderedDict, deque

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QMimeData, QPoint, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QCursor, QDrag, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QAbstractItemView, QApplication, QListWidget, QStyledItemDelegate
from themes import CLEANING_DEFAULT, NUMERIC_DEFAULTS, control_offset, control_shadow
from case_shell import CASE_DEPTH, CASE_SHADOW_DEPTH, case_frame_color, paint_cd_case
from responsive import running_on_android
from case_geometry import CASE_WIDTH, CASE_HEIGHT
from scroll_shadows import ScrollEdgeFade as AlbumEdgeFade


BAKED_CASE_LIMIT = 16


class CaseDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        available = max(1, self.parent().viewport().width() - 4)
        if size.width() > available:
            size = size.scaled(available, size.height(), Qt.KeepAspectRatio)
        return size

    def paint(self, painter, option, index):
        grid = self.parent()
        if index.row() in grid.lifts or index.row() in grid.tilts:
            return  # Moving cases are drawn over the grid, without item clipping.
        grid.paint_case(painter, option.rect, index)


class AlbumGrid(QListWidget):
    tidyStateChanged = Signal(bool)
    orderChanged = Signal()

    def case_geometry(self, cell, row):
        lift = self.lifts.get(row, 0.0)
        size = self.display_icon_size()
        scale = 1 + self.hover_growth / 100 * lift
        rect = QRectF(0, 0, size.width() * scale, size.height() * scale)
        rect.moveCenter(QRectF(cell).center())
        rect.translate(0, -self.hover_lift * lift)
        angle = self.tilts.get(row, 0.0)
        bounds = QTransform().rotate(angle).mapRect(QRectF(
            -rect.width() / 2, -rect.height() / 2, rect.width(), rect.height()))
        bounds.translate(rect.center())
        depth_offset = QTransform().rotate(angle).map(-control_offset(self.viewport(), rect, CASE_DEPTH))
        bounds = bounds.united(bounds.translated(depth_offset))
        bounds = bounds.united(bounds.translated(control_shadow(CASE_SHADOW_DEPTH)))
        # Protect the edges of the whole album grid, not the moving viewport.
        # All cases must translate by exactly the scroll distance, even when
        # their tilt would otherwise extend past the visible bottom edge.
        offset = self.verticalOffset()
        content_height = self.verticalScrollBar().maximum() + self.viewport().height()
        viewport = QRectF(0, -offset, self.viewport().width(), content_height).adjusted(2, 2, -2, -8)
        base = QRectF(0, 0, size.width(), size.height())
        base.moveCenter(QRectF(cell).center())
        fits_x = base.left() >= 0 and base.right() <= self.viewport().width()
        fits_y = base.top() >= -offset and base.bottom() <= content_height - offset
        factor = min(1.0,
                     viewport.width() / bounds.width() if fits_x else 1.0,
                     viewport.height() / bounds.height() if fits_y else 1.0)
        if factor < 1:
            center = rect.center()
            rect.setSize(rect.size() * factor)
            rect.moveCenter(center)
            bounds = QTransform().rotate(angle).mapRect(QRectF(
                -rect.width() / 2, -rect.height() / 2, rect.width(), rect.height()))
            bounds.translate(center)
            depth_offset = QTransform().rotate(angle).map(-control_offset(self.viewport(), rect, CASE_DEPTH))
            bounds = bounds.united(bounds.translated(depth_offset))
            bounds = bounds.united(bounds.translated(control_shadow(CASE_SHADOW_DEPTH)))
        dx = dy = 0
        if fits_x:
            dx = max(0, viewport.left() - bounds.left()) - max(0, bounds.right() - viewport.right())
        if fits_y:
            dy = max(0, viewport.top() - bounds.top()) - max(0, bounds.bottom() - viewport.bottom())
        rect.translate(dx, dy)
        return rect, angle

    def paint_case(self, painter, cell, index):
        if self.suppressed_album is not None and index.data(Qt.UserRole) == self.suppressed_album:
            return
        icon = self.icon_provider(index.row()) if self.icon_provider is not None else index.data(Qt.DecorationRole)
        if icon is None:
            return
        rect, angle = self.case_geometry(cell, index.row())
        source = icon if isinstance(icon, QPixmap) else icon.pixmap(self.iconSize() * 2)
        key = self.sheen_key_provider(index.row()) if self.sheen_key_provider is not None else ''
        if (self.baked_cases is not None and not angle and index.row() not in self.lifts
                and self.reflow_animation.state() != QAbstractAnimation.Running):
            self.paint_baked_case(painter, rect, source, key)
        else:
            paint_cd_case(painter, self.viewport(), rect, source, key, angle, QRectF(self.viewport().rect()))

    def paint_baked_case(self, painter, rect, source, key):
        """Copy a finished case bitmap; phones cannot repaint every case each frame."""
        view = self.viewport().rect()
        ratio = self.devicePixelRatioF()
        theme = self.frozen_theme or (QApplication.instance().property('themeBackground'), case_frame_color().name())
        tag = (key, source.cacheKey(), round(rect.width(), 2), round(rect.height(), 2), round(rect.x(), 2), view.height(),
               ratio, theme)
        margin = 2 * (CASE_DEPTH + CASE_SHADOW_DEPTH) + 4
        baked = self.baked_cases.get(tag)
        if baked is None:
            # Perspective and glare are fixed at mid-screen so one bitmap fits every scroll position.
            home = QRectF(rect)
            home.moveTop((view.height() - rect.height()) / 2)
            baked = QPixmap(math.ceil((rect.width() + 2 * margin) * ratio), math.ceil((rect.height() + 2 * margin) * ratio))
            baked.setDevicePixelRatio(ratio)
            baked.fill(Qt.transparent)
            layer = QPainter(baked)
            layer.translate(margin - home.x(), margin - home.y())
            paint_cd_case(layer, self.viewport(), home, source, key, 0, QRectF(view))
            layer.end()
            self.baked_cases[tag] = baked
            while len(self.baked_cases) > BAKED_CASE_LIMIT:
                self.baked_cases.popitem(last=False)
        self.baked_cases.move_to_end(tag)
        painter.drawPixmap(QPointF(round((rect.x() - margin) * ratio) / ratio, round((rect.y() - margin) * ratio) / ratio), baked)
    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        origin = self.viewport().geometry().topLeft()
        for fade in self.edge_fades:
            if not fade.isHidden():
                fade.paint_background(painter, fade.geometry().translated(-origin))
        painter.end()
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        rows = set(self.lifts) | set(self.tilts)
        for row in sorted(rows, key=lambda row: (row == self.hover_row, row)):
            index = self.model().index(row, 0)
            cell = self.visualRect(index)
            if cell.intersects(self.viewport().rect()):
                self.paint_case(painter, cell, index)
        painter.end()

    def __init__(self):
        super().__init__()
        self._positioning = False
        self._positions = {}
        self._content_height = 0
        self.layout_columns = 1
        self._row_pitch = 1
        self._last_item_size = QSize()
        self._reflow_icon_start = self.iconSize()
        self._pending_icon_start = None
        self._reflow_progress = 1.0
        self._reflow_starts = {}
        self._reflow_targets = {}
        self._layout_model_changed = True
        self.reflow_animation = QVariantAnimation(self)
        self.reflow_animation.setDuration(260)
        self.reflow_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.reflow_animation.valueChanged.connect(self.advance_reflow)
        self.reflow_animation.finished.connect(self.finish_reflow)
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self.doItemsLayout)
        self.model().rowsInserted.connect(self.model_layout_changed)
        self.model().rowsRemoved.connect(self.model_layout_changed)
        self.model().modelReset.connect(self.model_layout_changed)
        self.lifts = {}
        self.baked_cases = OrderedDict() if running_on_android() else None
        self.frozen_theme = None
        self.icon_provider = None
        self.sheen_key_provider = None
        self.suppressed_album = None
        self.animations = {}
        self.tilts = {}
        self.tilt_animations = {}
        self.tidying = False
        self.cleaning_enabled = CLEANING_DEFAULT
        self.tidy_queue = deque()
        self.tidy_timer = QTimer(self)
        self.tidy_timer.setInterval(110)
        self.tidy_timer.timeout.connect(self.tidy_next)
        self.hover_row = -1
        self.custom_order = False
        self.scroll_target = 0
        self.scroll_animation = QVariantAnimation(self)
        self.scroll_animation.setDuration(240)
        self.scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.scroll_animation.valueChanged.connect(lambda value: self.verticalScrollBar().setValue(round(value)))
        self.verticalScrollBar().sliderPressed.connect(self.scroll_animation.stop)
        self.verticalScrollBar().actionTriggered.connect(self.scroll_animation.stop)
        self.wheel_remainder = 0
        self.pixel_remainder = 0
        self.hover_rotation = NUMERIC_DEFAULTS['hover_rotation']
        self.hover_growth = NUMERIC_DEFAULTS['hover_growth']
        self.hover_lift = NUMERIC_DEFAULTS['hover_lift']
        self.horizontal_spacing = NUMERIC_DEFAULTS['album_horizontal_spacing']
        self.vertical_spacing = NUMERIC_DEFAULTS['album_vertical_spacing']
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setItemDelegate(CaseDelegate(self))
        self.verticalScrollBar().valueChanged.connect(self.refresh_hover)
        self.horizontalScrollBar().valueChanged.connect(self.refresh_hover)
        self.edge_fades = (AlbumEdgeFade(self, background_only=True), AlbumEdgeFade(self, bottom=True, background_only=True))
        self.verticalScrollBar().valueChanged.connect(self.update_edge_fades)
        self.verticalScrollBar().rangeChanged.connect(self.update_edge_fades)
        self.update_edge_fades()

    def update_edge_fades(self, *args):
        if not hasattr(self, 'edge_fades'):
            return
        rect = self.viewport().geometry()
        height = min(24, rect.height() // 4)
        bar = self.verticalScrollBar()
        for index, fade in enumerate(self.edge_fades):
            fade.setGeometry(rect.x(), rect.y() if index == 0 else rect.bottom() - height + 1,
                             rect.width(), height)
            fade.reveal(height > 0 and (bar.value() > bar.minimum() if index == 0 else bar.value() < bar.maximum()))
            fade.raise_()
        self.viewport().update()

    def model_layout_changed(self, *args):
        self._layout_model_changed = True
        self.reflow_animation.stop()
        self._reflow_timer.start(0)

    def display_icon_size(self):
        target = self.iconSize()
        available = max(1, self.viewport().width() - 12)
        if target.width() > available:
            target = target.scaled(available, target.height(), Qt.KeepAspectRatio)
        if self._reflow_targets and self._reflow_progress < 1:
            amount = self._reflow_progress
            size = QSize(round(self._reflow_icon_start.width() + (target.width() - self._reflow_icon_start.width()) * amount),
                         round(self._reflow_icon_start.height() + (target.height() - self._reflow_icon_start.height()) * amount))
            return size.scaled(available, size.height(), Qt.KeepAspectRatio) if size.width() > available else size
        return target

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_edge_fades()
        if hasattr(self, '_reflow_timer') and not self._positioning:
            self._reflow_timer.start(0)

    def updateGeometries(self):
        super().updateGeometries()
        # Old positions can briefly extend outside the new width during reflow.
        # They must never pan the album canvas or create a horizontal scrollbar.
        self.horizontalScrollBar().setRange(0, 0)
        if hasattr(self, '_content_height'):
            bar = self.verticalScrollBar()
            bar.setRange(0, max(0, self._content_height - self.viewport().height()))
            self.scroll_target = min(self.scroll_target, bar.maximum())
        self.update_edge_fades()

    def doItemsLayout(self):
        if not hasattr(self, 'reflow_animation') or self._positioning:
            super().doItemsLayout()
            return
        previous = dict(self._positions)
        previous_size = QSize(self._last_item_size)
        previous_icon = self._pending_icon_start or self.display_icon_size()
        self._pending_icon_start = None
        self.reflow_animation.stop()
        self._positioning = True
        try:
            super().doItemsLayout()
            self.center_items(previous, previous_size, previous_icon)
        finally:
            self._positioning = False

    def center_items(self, previous, previous_size, previous_icon):
        self._reflow_starts = {}
        self._reflow_targets = {}
        count = self.count()
        if not count or self.movement() != QListWidget.Free:
            self._positions = {}
            self._content_height = 0
            self.updateGeometries()
            return
        width = self.viewport().width()
        model = self.model()
        item_size = super().visualRect(model.index(0, 0)).size()
        grid_width = min(width, max(self.gridSize().width(), item_size.width(), 1))
        grid_height = max(self.gridSize().height(), item_size.height(), 1)
        columns = max(1, min(count, width // grid_width))
        self.layout_columns = columns
        self._row_pitch = grid_height
        self._content_height = ((count - 1) // columns) * grid_height + item_size.height() + 4
        animate = (not self._layout_model_changed and len(previous) == count
                   and previous_size.isValid() and self.isVisible())
        scroll = self.verticalOffset()
        nearby = QRectF(0, scroll - self.viewport().height(), width, self.viewport().height() * 3)
        self._positions = {}
        for row in range(count):
            row_count = min(columns, count - row // columns * columns)
            x = (width - row_count * grid_width) / 2 + row % columns * grid_width + (grid_width - item_size.width()) / 2
            y = row // columns * grid_height
            target = QPoint(round(x), round(y))
            start = target
            if animate:
                old = previous[row]
                start = QPoint(round(old.x() + (previous_size.width() - item_size.width()) / 2),
                               round(old.y() + (previous_size.height() - item_size.height()) / 2))
                if ((start != target or previous_icon != self.iconSize())
                        and (nearby.intersects(QRectF(start, item_size)) or nearby.intersects(QRectF(target, item_size)))):
                    self._reflow_starts[row] = start
                    self._reflow_targets[row] = target
                else:
                    start = target
            self.setPositionForIndex(start, model.index(row, 0))
            self._positions[row] = start
        self._last_item_size = item_size
        self._layout_model_changed = False
        self._reflow_icon_start = previous_icon
        self._reflow_progress = 0.0 if self._reflow_targets else 1.0
        self.updateGeometries()
        if self._reflow_targets:
            self.reflow_animation.setStartValue(0.0)
            self.reflow_animation.setEndValue(1.0)
            self.reflow_animation.start()
        if self.viewport().width() != width:
            self._reflow_timer.start(0)
        self.viewport().update()

    def advance_reflow(self, amount):
        self._reflow_progress = float(amount)
        model = self.model()
        for row, target in self._reflow_targets.items():
            if row >= self.count():
                continue
            start = self._reflow_starts[row]
            point = QPoint(round(start.x() + (target.x() - start.x()) * amount),
                           round(start.y() + (target.y() - start.y()) * amount))
            self.setPositionForIndex(point, model.index(row, 0))
            self._positions[row] = point
        self.viewport().update()

    def finish_reflow(self):
        self.advance_reflow(1.0)
        self._reflow_starts = {}
        self._reflow_targets = {}
        self.updateGeometries()

    def set_cleaning(self, enabled):
        self.cleaning_enabled = bool(enabled)
        if not self.cleaning_enabled:
            self.tidy_timer.stop()
            self.tidy_queue.clear()
            if self.tidying:
                self.tidying = False
                self.tidyStateChanged.emit(False)
            for animation in self.tilt_animations.values():
                animation.stop()
                animation.deleteLater()
            self.tilt_animations.clear()
            self.tilts.clear()
            self.viewport().update()

    def set_hover_options(self, rotation, growth,
                          horizontal_spacing=NUMERIC_DEFAULTS['album_horizontal_spacing'],
                          vertical_spacing=NUMERIC_DEFAULTS['album_vertical_spacing'],
                          hover_lift=NUMERIC_DEFAULTS['hover_lift']):
        old_rotation = self.hover_rotation
        self.hover_rotation = max(0.0, min(45.0, rotation))
        if old_rotation != self.hover_rotation:
            for animation in self.tilt_animations.values():
                animation.stop()
                animation.deleteLater()
            self.tilt_animations.clear()
            ratio = self.hover_rotation / old_rotation if old_rotation else 0
            self.tilts = {row: angle * ratio for row, angle in self.tilts.items()}
            self.finish_tidy_if_done()
        self.hover_growth = max(0.0, min(20.0, growth))
        self.hover_lift = max(0, min(40, int(hover_lift)))
        self.horizontal_spacing = max(0, min(160, int(horizontal_spacing)))
        self.vertical_spacing = max(0, min(160, int(vertical_spacing)))
        self.update_grid_size()

    def set_album_scale(self, percent):
        percent = max(50, min(150, percent))
        size = QSize(round(328 * percent / 100), round(328 * CASE_HEIGHT / CASE_WIDTH * percent / 100))
        if size == self.iconSize():
            return
        self.scroll_animation.stop()
        self.set_hover(-1)
        anchor = self.top_visible_anchor()
        self._pending_icon_start = self.display_icon_size()
        self.setIconSize(size)
        self.update_grid_size()
        self.doItemsLayout()
        if anchor is not None:
            self.restore_anchor(*anchor)

    def top_visible_anchor(self):
        for row in range(self.count()):
            rect = self.visualItemRect(self.item(row))
            if rect.bottom() >= 0:
                return row, -rect.top() / max(1, rect.height())
        return None

    def restore_anchor(self, row, passed):
        if not 0 <= row < self.count():
            return
        rect = self.visualItemRect(self.item(row))
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() + rect.top() + round(passed * rect.height()))

    def update_grid_size(self):
        # Only size and spacing control the grid; hover never reflows its rows.
        size = self.iconSize()
        grid_size = QSize(size.width() + 12 + self.horizontal_spacing,
                          size.height() + 16 + self.vertical_spacing)
        if grid_size != self.gridSize():
            self.setGridSize(grid_size)
        self.viewport().update()

    def animate(self, row, target):
        if row < 0:
            return
        previous = self.animations.pop(row, None)
        if previous is not None:
            previous.stop()
            previous.deleteLater()
        animation = QVariantAnimation(self)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(self.lifts.get(row, 0.0))
        animation.setEndValue(target)
        animation.valueChanged.connect(lambda value: self.set_lift(row, value))

        def finished():
            self.animations.pop(row, None)
            if target == 0:
                self.lifts.pop(row, None)
            animation.deleteLater()

        animation.finished.connect(finished)
        self.animations[row] = animation
        animation.start()

    def set_lift(self, row, value):
        self.lifts[row] = float(value)
        self.viewport().update()

    def set_hover(self, row):
        if self.tidying and row >= 0:
            return
        if row != self.hover_row:
            self.animate(self.hover_row, 0.0)
            if not self.cleaning_enabled and self.hover_row >= 0:
                self.animate_tilt(self.hover_row, 0.0)
            self.hover_row = row
            self.animate(row, 1.0)
            if row >= 0:
                rotation = self.hover_rotation * (2 if self.cleaning_enabled else 1)
                target = random.uniform(-rotation, rotation)
                self.animate_tilt(row, target)

    def animate_tilt(self, row, target, duration=180):
        previous = self.tilt_animations.pop(row, None)
        if previous is not None:
            previous.stop()
            previous.deleteLater()
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        animation.setStartValue(self.tilts.get(row, 0.0))
        animation.setEndValue(float(target))

        def update(value):
            self.tilts[row] = float(value)
            self.viewport().update()

        def finished():
            self.tilt_animations.pop(row, None)
            if target == 0:
                self.tilts.pop(row, None)
            animation.deleteLater()
            self.finish_tidy_if_done()

        animation.valueChanged.connect(update)
        animation.finished.connect(finished)
        self.tilt_animations[row] = animation
        animation.start()

    def tidy_up(self):
        if self.tidying or not self.cleaning_enabled:
            return
        self.set_hover(-1)
        rows = sorted(set(self.tilts) | set(self.tilt_animations))
        if not rows:
            return
        self.tidying = True
        self.tidyStateChanged.emit(True)
        self.tidy_queue = deque(rows)
        self.tidy_timer.start()
        self.tidy_next()

    def tidy_next(self):
        if self.tidy_queue:
            self.animate_tilt(self.tidy_queue.popleft(), 0.0, 260)
        if not self.tidy_queue:
            self.tidy_timer.stop()
            self.finish_tidy_if_done()

    def finish_tidy_if_done(self):
        if self.tidying and not self.tidy_queue and not self.tilt_animations:
            self.tidying = False
            self.tidyStateChanged.emit(False)

    def refresh_hover(self, *args):
        point = self.viewport().mapFromGlobal(QCursor.pos())
        row = self.indexAt(point).row() if self.viewport().underMouse() else -1
        if row != self.hover_row:
            self.set_hover(-1)  # Layout/settings updates must not create new tilts.

    def mouseMoveEvent(self, event):
        self.set_hover(self.indexAt(event.position().toPoint()).row())
        super().mouseMoveEvent(event)

    def row_pitch(self):
        return max(1, self._row_pitch)

    def wheelEvent(self, event):
        if event.pixelDelta().y():
            self.pixel_remainder += event.pixelDelta().y()
            steps = math.trunc(self.pixel_remainder / 80)
            self.pixel_remainder -= steps * 80
        elif event.angleDelta().y():
            self.wheel_remainder += event.angleDelta().y()
            steps = math.trunc(self.wheel_remainder / 120)
            self.wheel_remainder -= steps * 120
        else:
            super().wheelEvent(event)
            return
        if steps:
            bar = self.verticalScrollBar()
            base = self.scroll_target if self.scroll_animation.state() == QVariantAnimation.Running else bar.value()
            self.scroll_target = max(bar.minimum(), min(bar.maximum(), base - steps * self.row_pitch()))
            self.scroll_animation.stop()
            self.scroll_animation.setStartValue(float(bar.value()))
            self.scroll_animation.setEndValue(float(self.scroll_target))
            self.scroll_animation.start()
        event.accept()

    def set_custom_order(self, enabled):
        self.custom_order = bool(enabled)
        self.setDragEnabled(enabled)
        self.setAcceptDrops(enabled)
        self.setDragDropMode(QAbstractItemView.DragDrop if enabled else QAbstractItemView.NoDragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def startDrag(self, actions):
        if not self.custom_order or self.currentRow() < 0:
            return
        self.set_hover(-1)
        mime = QMimeData()
        mime.setData('application/x-album-drive-album', str(self.currentRow()).encode('ascii'))
        drag = QDrag(self)
        drag.setMimeData(mime)
        icon = self.icon_provider(self.currentRow()) if self.icon_provider else self.currentItem().icon()
        source = icon if isinstance(icon, QPixmap) else icon.pixmap(self.iconSize() * 2)
        rect, angle = self.case_geometry(self.visualItemRect(self.currentItem()), self.currentRow())
        bounds = QTransform().rotate(angle).mapRect(QRectF(-rect.width()/2, -rect.height()/2, rect.width(), rect.height()))
        depth_offset = QTransform().rotate(angle).map(-control_offset(self.viewport(), rect, CASE_DEPTH))
        bounds = bounds.united(bounds.translated(depth_offset))
        bounds = bounds.united(bounds.translated(control_shadow(CASE_SHADOW_DEPTH)))
        bounds = bounds.adjusted(-2, -2, 2, 2)
        ratio = self.devicePixelRatioF()
        preview = QPixmap(math.ceil(bounds.width() * ratio), math.ceil(bounds.height() * ratio))
        preview.setDevicePixelRatio(ratio)
        preview.fill(Qt.transparent)
        painter = QPainter(preview)
        try:
            painter.translate(-bounds.left() - rect.center().x(), -bounds.top() - rect.center().y())
            key = self.sheen_key_provider(self.currentRow()) if self.sheen_key_provider is not None else ''
            paint_cd_case(painter, self.viewport(), rect, source, key, angle)
        finally:
            painter.end()
        drag.setPixmap(preview)
        point = self.viewport().mapFromGlobal(QCursor.pos())
        self._drag_cell_offset = point - self.visualItemRect(self.currentItem()).topLeft()
        drag.setHotSpot(QPoint(round(point.x() - rect.center().x() - bounds.left()),
                              round(point.y() - rect.center().y() - bounds.top())))
        drag.exec(Qt.MoveAction)
        self._drag_cell_offset = None

    def dragEnterEvent(self, event):
        if self.custom_order and event.source() is self and event.mimeData().hasFormat('application/x-album-drive-album'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def move_album(self, source, target):
        if not self.custom_order or source == target or not (0 <= source < self.count() and 0 <= target < self.count()):
            return
        # Row-based hover animations must not transfer to a different album.
        cleaning = self.cleaning_enabled
        self.set_cleaning(False)
        self.cleaning_enabled = cleaning
        for animation in self.animations.values():
            animation.stop()
            animation.deleteLater()
        self.animations.clear()
        self.lifts.clear()
        self.hover_row = -1
        positions = {id(self.item(row)): QPoint(position) for row, position in self._positions.items()}
        item = self.takeItem(source)
        self.insertItem(target, item)
        self.setCurrentItem(item)
        self._reflow_timer.stop()
        self._positions = {row: positions.get(id(self.item(row)), QPoint()) for row in range(self.count())}
        self._layout_model_changed = False
        self.doItemsLayout()
        self.orderChanged.emit()
        self.viewport().update()

    def dropEvent(self, event):
        if not (self.custom_order and event.source() is self and event.mimeData().hasFormat('application/x-album-drive-album')):
            event.ignore()
            return
        source = int(bytes(event.mimeData().data('application/x-album-drive-album')))
        target = self.indexAt(event.position().toPoint()).row()
        target = target if target >= 0 else self.count() - 1
        if source != target and source in self._positions:
            position = event.position() + QPointF(0, self.verticalOffset())
            cell = self.visualItemRect(self.item(source))
            offset = getattr(self, '_drag_cell_offset', None) or QPointF(cell.width() / 2, cell.height() / 2)
            self._positions[source] = QPoint(round(position.x() - offset.x()),
                                            round(position.y() - offset.y()))
        self.move_album(source, target)
        event.setDropAction(Qt.MoveAction)
        event.accept()

    def leaveEvent(self, event):
        self.set_hover(-1)
        super().leaveEvent(event)

    def hideEvent(self, event):
        self.set_hover(-1)
        super().hideEvent(event)

    def clear(self):
        self.reflow_animation.stop()
        self._reflow_timer.stop()
        self._positions.clear()
        self._reflow_starts.clear()
        self._reflow_targets.clear()
        self.suppressed_album = None
        self.scroll_animation.stop()
        self.scroll_target = 0
        self.tidy_timer.stop()
        self.tidy_queue.clear()
        for animation in self.tilt_animations.values():
            animation.stop()
            animation.deleteLater()
        self.tilt_animations.clear()
        self.tilts.clear()
        self.finish_tidy_if_done()
        for animation in self.animations.values():
            animation.stop()
            animation.deleteLater()
        self.animations.clear()
        self.lifts.clear()
        self.hover_row = -1
        self.wheel_remainder = 0
        self.pixel_remainder = 0
        super().clear()
