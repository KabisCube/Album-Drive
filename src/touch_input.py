"""Android touch handling: one place that decides what each finger movement means."""
from math import hypot

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QAbstractItemView, QAbstractSlider, QApplication, QScroller, QScrollerProperties

TOUCH_SLOP = 12
LONG_PRESS_MS = 450
MINIMUM_TOUCH_TARGET = 48


def send_mouse(target, kind, position, global_position, buttons=Qt.LeftButton):
    button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
    event = QMouseEvent(kind, QPointF(position), QPointF(global_position), button, buttons, Qt.NoModifier)
    QApplication.sendEvent(target, event)


def tune_scroller(scroller):
    properties = scroller.scrollerProperties()
    off = QScrollerProperties.OvershootPolicy.OvershootAlwaysOff
    properties.setScrollMetric(QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy, off)
    properties.setScrollMetric(QScrollerProperties.ScrollMetric.VerticalOvershootPolicy, off)
    scroller.setScrollerProperties(properties)


class TouchGestures(QObject):
    """Sort touches on a widget into a tap, scroll, drag, long press or pinch.

    Accepting the touch stops Qt turning it into mouse events, so a swipe can
    never select or click. A mouse click is sent only once a touch proves to be a tap.
    """

    def __init__(self, widget, scrolls=False, on_drag=None, on_drag_end=None, on_pinch=None, on_pinch_end=None):
        super().__init__(widget)
        self.widget = widget
        self.scroller = QScroller.scroller(widget) if scrolls else None
        self.on_drag, self.on_drag_end = on_drag, on_drag_end
        self.on_pinch, self.on_pinch_end = on_pinch, on_pinch_end
        self.state = None
        self.target = None
        self.start = QPointF()
        self.start_global = QPointF()
        self.last_global = QPointF()
        self.pinch_distance = 0.0
        self.velocity = 0.0
        self.clock = QElapsedTimer()
        self.long_press = QTimer(self)
        self.long_press.setSingleShot(True)
        self.long_press.setInterval(LONG_PRESS_MS)
        self.long_press.timeout.connect(self.open_context_menu)
        if self.scroller is not None:
            tune_scroller(self.scroller)
        if isinstance(widget.parentWidget(), QAbstractItemView):
            widget.parentWidget().setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            widget.parentWidget().setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        widget.setAttribute(Qt.WA_AcceptTouchEvents)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.TouchBegin:
            self.begin(event)
        elif kind == QEvent.TouchUpdate:
            self.update_touch(event)
        elif kind == QEvent.TouchEnd:
            self.finish(event)
        elif kind == QEvent.TouchCancel:
            self.cancel()
        else:
            return False
        event.accept()
        return True

    def scroll_input(self, phase, position, event):
        if self.scroller is not None:
            # Qt refuses to start a scroll on a slider, so use the slider-free edge of the page.
            x = 0 if isinstance(self.target, QAbstractSlider) else position.x()
            self.scroller.handleInput(phase, QPointF(x, position.y()), event.timestamp())

    def begin(self, event):
        point = event.points()[0]
        self.start, self.start_global = point.position(), point.globalPosition()
        self.last_global = self.start_global
        self.velocity = 0.0
        self.clock.start()
        flinging = self.scroller is not None and self.scroller.state() == QScroller.Scrolling
        self.state = 'stopped' if flinging else 'pending'
        self.target = self.widget.childAt(self.start.toPoint()) or self.widget
        self.scroll_input(QScroller.InputPress, self.start, event)
        if not flinging:
            self.long_press.start()

    def update_touch(self, event):
        points = event.points()
        if self.on_pinch is not None and len(points) >= 2:
            self.update_pinch(points)
            return
        if self.state == 'pinching' or not points:
            return
        point = points[0]
        offset = point.globalPosition() - self.start_global
        if self.state in ('pending', 'stopped') and hypot(offset.x(), offset.y()) >= TOUCH_SLOP:
            self.long_press.stop()
            if isinstance(self.target, QAbstractSlider) and abs(offset.x()) > abs(offset.y()):
                self.state = 'slider'
                self.mouse_on_target(QEvent.MouseButtonPress, self.start_global)
            else:
                self.state = 'moving'
        if self.state == 'slider':
            self.mouse_on_target(QEvent.MouseMove, point.globalPosition())
        elif self.state == 'moving':
            self.scroll_input(QScroller.InputMove, point.position(), event)
            if self.on_drag is not None:
                elapsed = max(1, self.clock.restart())
                delta = point.globalPosition().y() - self.last_global.y()
                self.velocity = delta * 1000 / elapsed
                self.on_drag(delta)
        self.last_global = point.globalPosition()

    def update_pinch(self, points):
        distance = hypot(*(lambda gap: (gap.x(), gap.y()))(points[0].globalPosition() - points[1].globalPosition()))
        if self.state != 'pinching':
            self.long_press.stop()
            if self.scroller is not None:
                self.scroller.stop()
            self.state = 'pinching'
            self.pinch_distance = distance
            self.on_pinch(1.0, True)
        elif self.pinch_distance > 0:
            self.on_pinch(distance / self.pinch_distance, False)

    def finish(self, event):
        self.long_press.stop()
        state, self.state = self.state, None
        point = event.points()[0] if event.points() else None
        position = point.position() if point is not None else self.start
        if state == 'pinching':
            if self.on_pinch_end is not None:
                self.on_pinch_end()
            return
        self.scroll_input(QScroller.InputRelease, position, event)
        if state == 'pending':
            self.tap()
        elif state == 'slider':
            self.mouse_on_target(QEvent.MouseButtonRelease, self.last_global, Qt.NoButton)
        elif state == 'moving' and self.on_drag_end is not None:
            self.on_drag_end(self.velocity)

    def cancel(self):
        self.long_press.stop()
        if self.state == 'pinching' and self.on_pinch_end is not None:
            self.on_pinch_end()
        elif self.state == 'slider':
            self.mouse_on_target(QEvent.MouseButtonRelease, self.last_global, Qt.NoButton)
        if self.scroller is not None:
            self.scroller.stop()
        self.state = None

    def mouse_on_target(self, kind, global_position, buttons=Qt.LeftButton):
        local = self.target.mapFromGlobal(global_position)
        send_mouse(self.target, kind, local, global_position, buttons)

    def tap(self):
        target = self.target
        if target.focusPolicy() & Qt.ClickFocus:
            target.setFocus(Qt.MouseFocusReason)
        self.mouse_on_target(QEvent.MouseButtonPress, self.start_global)
        if self.target is target:
            self.mouse_on_target(QEvent.MouseButtonRelease, self.start_global, Qt.NoButton)

    def open_context_menu(self):
        self.state = 'held'
        if self.scroller is not None:
            self.scroller.stop()
        position = self.start_global.toPoint()
        target = self.target
        while target is not None and target is not self.widget and target.contextMenuPolicy() == Qt.DefaultContextMenu:
            target = target.parentWidget()
        target = target or self.widget
        event = QContextMenuEvent(QContextMenuEvent.Mouse, target.mapFromGlobal(position), position)
        QApplication.sendEvent(target, event)


def add_touch(widget, **options):
    """Attach gestures to a widget once; later calls keep the first configuration."""
    if getattr(widget, 'touch_gestures', None) is None:
        widget.touch_gestures = TouchGestures(widget, **options)
    return widget.touch_gestures
