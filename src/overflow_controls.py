from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLayout, QSizePolicy, QWidget
from scale_ghost import ScaleGhost, grow_widget, snapshot
from snap_scroll import SnapPager
from themes import CONTROL_HEADROOM, TabScrollButton, button_scale

FLEXIBLE_MINIMUM_WIDTH = 96


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
        self.flexible = None
        self.pager = SnapPager(self)
        self.pager.moved.connect(self.place_content)
        self.pinned = False
        self.unpinned_start = 0
        self.fill = False
        self.scroll_left = TabScrollButton(-1, self, lift=0)
        self.scroll_right = TabScrollButton(1, self, lift=0)
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

    @property
    def scroll_offset(self):
        return self.pager.target

    @scroll_offset.setter
    def scroll_offset(self, value):
        if value == 0:
            self.pager.reset()

    @property
    def maximum_scroll(self):
        return self.pager.maximum

    def set_pinned(self, pinned):
        if pinned == self.pinned:
            return
        self.pinned = pinned
        if pinned:
            self.unpinned_start = self.pager.start
            self.pager.start = len(self.pager.extents)
        else:
            self.pager.start = self.unpinned_start
        self.refresh(animate=True)

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

    def fit_flexible(self):
        widget = self.flexible
        if widget is None:
            return
        item = self.controls.itemAt(self.controls.indexOf(widget))
        others = self.controls.sizeHint().width() - item.sizeHint().width()
        room = self.width() - others
        if room < FLEXIBLE_MINIMUM_WIDTH:
            room = self.width() - 2 * self.arrow_width()
        width = max(FLEXIBLE_MINIMUM_WIDTH, min(widget.sizeHint().width(), room))
        if width != widget.minimumWidth() or width != widget.maximumWidth():
            widget.setFixedWidth(width)
            self.controls.invalidate()

    def items(self):
        widgets = (self.controls.itemAt(index).widget() for index in range(self.controls.count()))
        return [widget for widget in widgets if widget is not None and not widget.isHidden()]

    def refresh(self, animate=False):
        self.fit_flexible()
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
        before = self.on_screen() if self.isVisible() else {}
        fits = size.width() <= available
        self.content.resize(available if self.fill and fits else size.width(), self.height())
        self.controls.activate()
        extents = [(widget.x(), widget.x() + widget.width()) for widget in self.items()]
        if self.pinned:
            self.pager.start = len(extents)
        self.pager.update(extents, available, arrow, animate)
        shown = self.shown_items()
        leaving = [(widget, rect, source, pixmap) for widget, (rect, source, pixmap) in before.items()
                   if widget not in shown and not widget.isHidden()]
        self.scroll_left.set_shown(bool(self.pager.left_arrow) and not self.pinned)
        self.scroll_right.set_shown(bool(self.pager.right_arrow) and not self.pinned)
        self.scroll_left.setGeometry(left, 0, arrow, self.height())
        self.scroll_right.setGeometry(self.width() - arrow, 0, arrow, self.height())
        if self.pinned and (self.pager.right_arrow or self.pager.left_arrow):
            width = max(1, self.pager.page_width)
            self.viewport.setGeometry(self.width() - width, 0, width, self.height())
        elif self.pager.right_arrow or self.pager.left_arrow:
            self.viewport.setGeometry(left + self.pager.left_arrow, 0, max(1, self.pager.page_width), self.height())
        else:
            self.viewport.setGeometry(left, 0, available, self.height())
        self.place_content()
        for widget, rect, source, pixmap in leaving:
            ScaleGhost(self, pixmap, rect, source)
        if before and not animate and not self.pager.spring.moving:
            for widget in shown:
                if widget not in before and not widget.isHidden():
                    rect = widget.geometry().translated(self.content.pos() + self.viewport.pos())
                    grow_widget(widget, self, rect)

    def on_screen(self):
        window = self.viewport.geometry()
        found = {}
        for widget in self.items():
            rect = widget.geometry().translated(self.content.pos() + self.viewport.pos())
            visible = rect.intersected(window)
            if visible.width() > 0 and visible.height() > 0:
                found[widget] = (visible, visible.translated(-rect.topLeft()), snapshot(widget))
        return found

    def shown_items(self):
        items = self.items()
        return items[self.pager.start:self.pager.end] if self.pager.extents else items

    def place_content(self):
        if self.pager.right_arrow or self.pager.left_arrow:
            first = self.pager.extents[0][0] if self.pager.extents else 0
            x = -round(self.pager.offset) - first
        else:
            x = self.viewport.width() - self.content.width()
        self.content.move(x, 0)

    def scroll(self, direction):
        if self.pinned:
            return
        self.pager.scroll(direction)
        self.refresh(animate=True)

    def reveal_focus(self, previous, current):
        if self.pinned or current is None or not self.content.isAncestorOf(current):
            return
        self.refresh()
        items = self.items()
        owner = next((widget for widget in items if widget is current or widget.isAncestorOf(current)), None)
        if owner is not None:
            self.pager.reveal(items.index(owner))
            self.refresh(animate=True)
