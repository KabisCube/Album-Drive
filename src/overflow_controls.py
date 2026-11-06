from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLayout, QSizePolicy, QWidget
from themes import CONTROL_HEADROOM, TabScrollButton, button_scale


class OverflowControls(QWidget):
    def __init__(self, count, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.count = count
        count.setParent(self)
        self.viewport = QWidget(self)
        self.content = QWidget(self.viewport)
        self.viewport.setStyleSheet('background: transparent;')
        self.content.setStyleSheet('background: transparent;')
        self.controls = QHBoxLayout(self.content)
        self.controls.setContentsMargins(0, 0, 0, 0)
        self.controls.setSizeConstraint(QLayout.SetNoConstraint)
        self.scroll_offset = 0
        self.maximum_scroll = 0
        self.scroll_left = TabScrollButton(-1, self)
        self.scroll_right = TabScrollButton(1, self)
        for direction, button in ((-1, self.scroll_left), (1, self.scroll_right)):
            button.setAccessibleName('Scroll controls left' if direction < 0 else 'Scroll controls right')
            button.setToolTip(button.accessibleName())
            button.setFocusPolicy(Qt.NoFocus)
            button.hide()
        self.scroll_left.clicked.connect(lambda: self.scroll(-1))
        self.scroll_right.clicked.connect(lambda: self.scroll(1))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.refresh)
        self.content.installEventFilter(self)
        QApplication.instance().focusChanged.connect(self.reveal_focus)

    def sizeHint(self):
        size = self.controls.sizeHint().expandedTo(self.controls.minimumSize())
        return QSize(size.width() + self.count.sizeHint().width() + max(0, self.controls.spacing()), size.height())

    def minimumSizeHint(self):
        return QSize(2 * self.arrow_width() + 64, self.sizeHint().height())

    def arrow_width(self):
        return round(32 * button_scale()) + 2 * CONTROL_HEADROOM

    def event(self, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest, QEvent.StyleChange, QEvent.FontChange):
            if hasattr(self, 'timer'):
                self.timer.start(0)
        return super().event(event)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.LayoutRequest:
            self.timer.start(0)
        return super().eventFilter(watched, event)

    def refresh(self):
        size = self.controls.sizeHint().expandedTo(self.controls.minimumSize())
        if self.minimumHeight() != size.height():
            self.setMinimumHeight(size.height())
            self.updateGeometry()
        gap = max(0, self.controls.spacing())
        count_width = self.count.sizeHint().width()
        show_count = self.width() >= size.width() + count_width + gap
        self.count.setVisible(show_count)
        left = count_width + gap if show_count else 0
        self.count.setGeometry(0, 0, count_width, self.height())
        available = max(1, self.width() - left)
        arrow = self.arrow_width()
        self.maximum_scroll = max(0, size.width() - max(1, available - arrow)) if size.width() > available else 0
        self.scroll_offset = max(0, min(self.scroll_offset, self.maximum_scroll))
        show_left = self.scroll_offset > 0
        show_right = self.scroll_offset < self.maximum_scroll
        self.scroll_left.setVisible(show_left)
        self.scroll_right.setVisible(show_right)
        self.scroll_left.setGeometry(left, 0, arrow, self.height())
        self.scroll_right.setGeometry(self.width() - arrow, 0, arrow, self.height())
        viewport_left = left + (arrow if show_left else 0)
        viewport_width = max(1, available - arrow * (show_left + show_right))
        self.viewport.setGeometry(viewport_left, 0, viewport_width, self.height())
        x = -self.scroll_offset if self.maximum_scroll else viewport_width - size.width()
        self.content.setGeometry(x, 0, size.width(), self.height())
        self.controls.activate()

    def scroll(self, direction):
        self.scroll_offset += direction * max(1, round(self.viewport.width() * .75))
        self.refresh()

    def reveal_focus(self, previous, current):
        if current is None or not self.content.isAncestorOf(current):
            return
        self.refresh()
        for _ in range(2):
            left = current.mapTo(self.viewport, QPoint()).x()
            right = left + current.width()
            if left < 0:
                self.scroll_offset += left
            elif right > self.viewport.width():
                self.scroll_offset += right - self.viewport.width()
            self.refresh()
