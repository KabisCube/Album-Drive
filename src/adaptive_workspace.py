from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QRectF, QSignalBlocker, QSize, Qt, QVariantAnimation
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidget
from open_case import lerp_rect
from themes import CONTROL_HEADROOM, button_scale

DESKTOP_TRANSPORT_GAP = 12


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


class ResponsiveTransport(QWidget):
    def __init__(self, play, previous, next_button, seek, volume):
        super().__init__()
        self.play, self.previous, self.next = play, previous, next_button
        self.seek, self.volume = seek, volume
        self.mix = 0.0
        self.compact_row_gap = -6
        self.arranging = False
        self.back = None
        self.compact_volume = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for widget in (play, previous, next_button, seek, volume):
            widget.setParent(self)
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
            widgets = (self.play, self.volume, self.previous, self.seek, self.next)
            heights = [min(widget.maximumHeight(), max(widget.minimumHeight(), widget.sizeHint().height()))
                       for widget in widgets]
            desktop_height = max(heights)
            back = self.back if self.back is not None and not self.back.isHidden() else None
            back_size = back.sizeHint() if back is not None else QSize()
            row_height = max(heights[0], heights[2], heights[4], back_size.height())
            mobile_height = heights[3] + self.compact_row_gap + row_height
            self.setFixedHeight(round(desktop_height + (mobile_height - desktop_height) * self.mix))
            widths = [widget.sizeHint().width() for widget in widgets]
            widths[1] = self.volume.width()
            widths[3] = max(1, self.width() - sum(widths[index] for index in (0, 1, 2, 4)) - 4 * DESKTOP_TRANSPORT_GAP)
            desktop = []
            x = 0
            for width, height in zip(widths, heights):
                desktop.append(QRectF(x, (desktop_height - height) / 2, width, height))
                x += width + DESKTOP_TRANSPORT_GAP
            sizes = [round(width * button_scale()) + 2 * CONTROL_HEADROOM for width in (44, 64, 44)]
            x = (self.width() - sum(sizes) - 16) / 2
            if back is not None:
                x = max(x, back_size.width() + BACK_GAP)
                back.setGeometry(QRectF(0, heights[3] + self.compact_row_gap + (row_height - back_size.height()) / 2,
                                        back_size.width(), back_size.height()).toRect())
            mobile = {self.seek: QRectF(0, 0, self.width(), heights[3]),
                      self.volume: QRectF((self.width() - widths[1]) / 2, 0, widths[1], heights[1])}
            for widget, width, index in zip((self.previous, self.play, self.next), sizes, (2, 0, 4)):
                mobile[widget] = QRectF(x, heights[3] + self.compact_row_gap + (row_height - heights[index]) / 2, width, heights[index])
                x += width + 8
            volume_fits = self.compact_volume and x - 8 + BACK_GAP + widths[1] <= self.width()
            if volume_fits:
                mobile[self.volume] = QRectF(self.width() - widths[1],
                                             heights[3] + self.compact_row_gap + (row_height - heights[1]) / 2,
                                             widths[1], heights[1])
            for widget, rect in zip(widgets, desktop):
                widget.setGeometry(lerp_rect(rect, mobile[widget], self.mix).toRect())
            self.volume.setVisible(volume_fits or self.mix < 1)
            self.volume.set_paint_opacity(1 if volume_fits else 1 - self.mix)
        finally:
            self.arranging = False
