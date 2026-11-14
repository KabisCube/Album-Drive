"""Tooltips drawn on the dropdown list's raised panel. Qt's own tooltip window cannot take a custom paint,
so tooltip requests for widgets with a tooltip are answered with this label instead."""

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from themes import RaisedLabel

TOOLTIP_OFFSET = QPoint(10, 18)
TOOLTIP_SECONDS = 10
TOOLTIP_MAX_WIDTH = 360


class RaisedToolTips(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.label = None
        self.owner = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def ensure_label(self):
        if self.label is None:
            self.label = RaisedLabel()
            self.label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            self.label.setAttribute(Qt.WA_ShowWithoutActivating)
            self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.label.setWordWrap(True)
        return self.label

    def show(self, widget, text, position):
        label = self.ensure_label()
        color = QApplication.instance().property('textColor') or '#ffffff'
        label.setStyleSheet(f'background: transparent; border: none; padding: 0; color: {color};')
        label.setFont(widget.font())
        label.setText(text)
        label.fit_face()
        margins = label.contentsMargins()
        text_width = label.fontMetrics().boundingRect(0, 0, TOOLTIP_MAX_WIDTH, 2000, Qt.TextWordWrap, text).width()
        label.setFixedWidth(text_width + margins.left() + margins.right() + 4)
        label.adjustSize()
        screen = (widget.screen() or QApplication.primaryScreen()).availableGeometry()
        spot = position + TOOLTIP_OFFSET
        spot.setX(max(screen.left(), min(spot.x(), screen.right() - label.width())))
        if spot.y() + label.height() > screen.bottom():
            spot.setY(position.y() - label.height() - 4)
        label.move(spot)
        label.show()
        label.raise_()
        self.owner = widget
        self.timer.start(TOOLTIP_SECONDS * 1000)

    def hide(self):
        self.timer.stop()
        self.owner = None
        if self.label is not None:
            self.label.hide()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.ToolTip and isinstance(watched, QWidget) and watched.toolTip():
            self.show(watched, watched.toolTip(), event.globalPos())
            return True
        if self.owner is not None and kind in (QEvent.Leave, QEvent.MouseButtonPress, QEvent.Wheel,
                                               QEvent.KeyPress, QEvent.Hide, QEvent.WindowDeactivate):
            self.hide()
        return False


def install_raised_tooltips(app):
    if not hasattr(app, '_raised_tooltips'):
        app._raised_tooltips = RaisedToolTips(app)
        app.installEventFilter(app._raised_tooltips)
