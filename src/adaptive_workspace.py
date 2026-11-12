from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QRectF, QSignalBlocker, QSize, Qt, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLayout, QSizePolicy, QWidget
from open_case import lerp_rect
from themes import CONTROL_HEADROOM, button_scale

DESKTOP_TRANSPORT_GAP = 12
# Empty shadow room above and below the button faces that the transport row does not need to keep.
TRANSPORT_TRIM_TOP = 9
TRANSPORT_TRIM_BOTTOM = 10


class WorkspaceHandle(QWidget):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.setCursor(Qt.SplitHCursor)
        self.setStyleSheet('background: transparent;')
        self.dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            workspace = self.parentWidget()
            workspace.sidebar_width = max(180, min(workspace.width() - 220,
                                                   self.mapToParent(event.position().toPoint()).x()))
            workspace.arrange()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        event.accept()


class AdaptiveWorkspace(QWidget):
    def __init__(self):
        super().__init__()
        self.panes = []
        self.sidebar_width = 285
        self.compact = False
        self.page = 'browser'
        self.mode_mix = 0.0
        self.page_mix = 0.0
        self.handle = WorkspaceHandle(self)
        self.mode_animation = self.make_animation('mode_mix')
        self.page_animation = self.make_animation('page_mix')
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

    def make_animation(self, attribute):
        animation = QVariantAnimation(self)
        animation.setDuration(350)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        animation.valueChanged.connect(lambda value: self.advance(attribute, value))
        animation.finished.connect(self.arrange)
        return animation

    def advance(self, attribute, value):
        setattr(self, attribute, float(value))
        self.arrange()

    def animate(self, animation, current, target, enabled):
        animation.stop()
        if enabled and self.isVisible() and current != target:
            with QSignalBlocker(animation):
                animation.setStartValue(current)
                animation.setEndValue(target)
                animation.setCurrentTime(0)
            animation.start()
        else:
            attribute = 'mode_mix' if animation is self.mode_animation else 'page_mix'
            setattr(self, attribute, target)
        self.arrange()

    def addWidget(self, widget):
        widget.setParent(self)
        widget.layout().setSizeConstraint(QLayout.SetNoConstraint)
        widget.setMinimumWidth(0)
        self.panes.append(widget)

    def set_compact(self, compact, animate=True):
        if compact == self.compact:
            return
        self.compact = compact
        self.animate(self.mode_animation, self.mode_mix, float(compact), animate)

    def set_page(self, page, animate=True):
        if page == self.page:
            return
        self.page = page
        self.animate(self.page_animation, self.page_mix, float(page == 'library'), animate and self.compact)

    def sizeHint(self):
        return QSize(1000, 600)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def arrange(self):
        if len(self.panes) != 2:
            return
        width, height = self.width(), self.height()
        sidebar = min(self.sidebar_width, width * .45)
        desktop = (QRectF(0, 0, sidebar, height), QRectF(sidebar + 6, 0, max(1, width - sidebar - 6), height))
        offset = self.page_mix * (width + 16)
        narrow = (QRectF(-offset, 0, width, height), QRectF(width + 16 - offset, 0, width, height))
        moving = any(animation.state() == QAbstractAnimation.Running for animation in
                     (self.mode_animation, self.page_animation))
        for index, widget in enumerate(self.panes):
            widget.setGeometry(lerp_rect(desktop[index], narrow[index], self.mode_mix).toRect())
            widget.setVisible(not self.compact or moving or index == (1 if self.page == 'library' else 0))
        self.handle.setGeometry(round(sidebar) - 3, 0, 6, height)
        self.handle.setVisible(not self.compact and not moving)
        self.handle.raise_()


BACK_GAP = 24
MINIMUM_GAP_SHARE = .2


class ResponsiveTransport(QWidget):
    def __init__(self, play, previous, next_button, seek, volume, album=None):
        super().__init__()
        self.play, self.previous, self.next = play, previous, next_button
        self.seek, self.volume, self.album = seek, volume, album
        self.mix = 0.0
        self.compact_row_gap = -6
        self.arranging = False
        self.back = None
        self.compact_volume = False
        self.album_opacity = None
        self.last_volume_rect = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for widget in (play, previous, next_button, seek, volume, album):
            if widget is not None:
                widget.setParent(self)
        if album is not None:
            self.album_opacity = QGraphicsOpacityEffect(album)
            album.setGraphicsEffect(self.album_opacity)
        seek.lower()  # Its transparent edge may sit under the buttons.
        self.arrange()

    def set_back(self, button):
        self.back = button
        button.setParent(self)
        button.hide()
        self.arrange()

    def set_mix(self, amount):
        self.mix = float(amount)
        self.arrange()

    def sizeHint(self):
        return QSize(400, self.height())

    def minimumSizeHint(self):
        return QSize(0, self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def event(self, event):
        if event.type() == QEvent.LayoutRequest and hasattr(self, 'arranging'):
            self.arrange()
        return super().event(event)

    def arrange(self):
        if self.arranging:
            return
        self.arranging = True
        try:
            widgets = (self.play, self.previous, self.seek, self.next, self.volume)
            heights = [min(widget.maximumHeight(), max(widget.minimumHeight(), widget.sizeHint().height()))
                       for widget in widgets]
            desktop_height = max(heights)
            back = self.back if self.back is not None and not self.back.isHidden() else None
            back_size = (QSize(back.sizeHint().width(), min(back.maximumHeight(), max(back.minimumHeight(), back.sizeHint().height())))
                         if back is not None else QSize())
            row_height = max(heights[0], heights[1], heights[3], back_size.height())
            mobile_height = heights[2] + self.compact_row_gap + row_height
            trim = TRANSPORT_TRIM_TOP * (1 - self.mix)
            self.setFixedHeight(round(desktop_height + (mobile_height - desktop_height) * self.mix - trim - TRANSPORT_TRIM_BOTTOM))
            widths = [widget.sizeHint().width() for widget in widgets]
            widths[4] = self.volume.width()
            widths[2] = max(1, self.width() - sum(widths[index] for index in (0, 1, 3, 4)) - 4 * DESKTOP_TRANSPORT_GAP)
            desktop = []
            x = 0
            for width, height in zip(widths, heights):
                desktop.append(QRectF(x, (desktop_height - height) / 2, width, height))
                x += width + DESKTOP_TRANSPORT_GAP
            gap = 8
            size = lambda width: round(width * button_scale()) + 2 * CONTROL_HEADROOM
            play_width, skip_width = size(64), size(44)
            album_height = 0
            if self.album is not None:
                album_height = min(self.album.maximumHeight(), max(self.album.minimumHeight(), self.album.sizeHint().height()))
            start = back_size.width() + BACK_GAP if back is not None else 0
            # Play sits on the window's center line; the rest of the row hangs off either side of it.
            play_x = (self.width() - play_width) / 2
            # Tighten the gaps (measured between visible faces) before dropping the volume or moving the row off-center.
            smallest = (gap + 2 * CONTROL_HEADROOM) * MINIMUM_GAP_SHARE - 2 * CONTROL_HEADROOM
            left_buttons = 2 if self.album is not None else 1
            left_room = (play_x - start - left_buttons * skip_width) / left_buttons
            right_room = (self.width() - play_x - play_width - skip_width - widths[4]) / 2
            if self.compact_volume and min(gap, left_room, right_room) >= smallest:
                gap = min(gap, left_room, right_room)
            else:
                gap = max(smallest, min(gap, left_room))
            previous_x = play_x - gap - skip_width
            next_x = play_x + play_width + gap
            album_x = previous_x - gap - skip_width
            leftmost = album_x if self.album is not None else previous_x
            # The gap after Back tightens to the same minimum; only then does the row move off-center.
            tight_start = back_size.width() + smallest if back is not None else 0
            shift = max(0.0, tight_start - leftmost) if leftmost < start else 0.0
            album_fits = self.album is not None and next_x + skip_width + shift <= self.width()
            if not album_fits:
                gap = max(smallest, min(8, play_x - start - skip_width))
                previous_x, next_x = play_x - gap - skip_width, play_x + play_width + gap
                shift = max(0.0, tight_start - previous_x) if previous_x < start else 0.0
            play_x, previous_x, next_x, album_x = play_x + shift, previous_x + shift, next_x + shift, album_x + shift
            if back is not None:
                back.setGeometry(QRectF(0, heights[2] + self.compact_row_gap + (row_height - back_size.height()) / 2 - trim,
                                        back_size.width(), back_size.height()).toRect())
            mobile = {self.seek: QRectF(0, 0, self.width(), heights[2]),
                      self.volume: QRectF((self.width() - widths[4]) / 2, 0, widths[4], heights[4])}
            row = [(self.previous, previous_x, skip_width, heights[1]), (self.play, play_x, play_width, heights[0]),
                   (self.next, next_x, skip_width, heights[3])]
            if album_fits:
                row.append((self.album, album_x, skip_width, album_height))
            for widget, x, width, height in row:
                mobile[widget] = QRectF(x, heights[2] + self.compact_row_gap + (row_height - height) / 2, width, height)
            volume_x = next_x + skip_width + gap
            volume_fits = self.compact_volume and volume_x + widths[4] <= self.width()
            if self.compact_volume:
                row_rect = QRectF(volume_x, heights[2] + self.compact_row_gap + (row_height - heights[4]) / 2,
                                  widths[4], heights[4])
                if volume_fits:
                    self.last_volume_rect = row_rect
                # Once it no longer fits, it shrinks away exactly where it was last shown.
                mobile[self.volume] = row_rect if volume_fits or self.last_volume_rect is None else self.last_volume_rect
            for widget, rect in zip(widgets, desktop):
                widget.setGeometry(lerp_rect(rect, mobile[widget], self.mix).translated(0, -trim).toRect())
            if self.album is not None:
                self.album.setGeometry(lerp_rect(desktop[1], mobile.get(self.album, desktop[1]), self.mix).translated(0, -trim).toRect())
                self.album.setVisible(album_fits and self.mix > 0)
                self.album_opacity.setOpacity(self.mix)
                if self.mix > 0:
                    self.album.raise_()
            self.volume.setVisible(volume_fits or self.mix < 1)
            self.volume.set_paint_opacity(1 if volume_fits else 1 - self.mix)
        finally:
            self.arranging = False
