"""One live scrollbar painter for steady themes and animated transitions."""
from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QScrollBar, QStyle, QStyleOptionSlider

from themes import CONTROL_HEADROOM, control_face, corner_radius, paint_control
from color_rules import slider_rail
from responsive import running_on_android
from scroll_shadows import install_scroll_shadows


class LiveScrollbars(QObject):
    def eventFilter(self, widget, event):
        if event.type() != QEvent.Paint or not isinstance(widget, QScrollBar):
            return False
        app = QApplication.instance()
        background = QColor(app.property('themeBackground') or '#393939')
        accent = QColor(app.property('themeAccent') or '#888888')
        rail_accent = QColor(app.property('themeBackgroundAccent')) if app.property('themeBackgroundAccent') else None
        paper_rail_accent = None
        fill = QColor(app.property('buttonFill') or '#cccccc')
        surface = QColor(background)
        parent = widget.parentWidget()
        while parent is not None:
            paper = parent.property('paperBackgroundColor')
            if paper:
                surface = QColor(paper)
                paper_accent = parent.property('paperButtonColor')
                paper_rail = parent.property('paperBackgroundAccentColor')
                if paper_accent:
                    accent = QColor(paper_accent)
                if paper_rail:
                    paper_rail_accent = QColor(paper_rail)
                break
            if parent.objectName() == 'fileBrowser':
                surface = background.darker(110)
                break
            if isinstance(parent, QAbstractScrollArea) and parent.window().objectName() == 'albumDriveDropdown':
                surface = QColor(fill)
                break
            parent = parent.parentWidget()
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(widget.rect(), surface)
        painter.setPen(Qt.NoPen)
        option = QStyleOptionSlider()
        widget.initStyleOption(option)
        handle = widget.style().subControlRect(QStyle.CC_ScrollBar, option, QStyle.SC_ScrollBarSlider, widget)
        knob = QRectF(handle).adjusted(0, 0, 0, -CONTROL_HEADROOM)
        groove = QRectF(widget.style().subControlRect(QStyle.CC_ScrollBar, option, QStyle.SC_ScrollBarGroove, widget))
        before = QRectF(groove)
        face = control_face(knob, widget=widget)
        if widget.orientation() == Qt.Vertical:
            margin = (before.width() - 8) / 2
            before.adjust(margin, 0, -margin, 0)
            before.setTop(groove.top() + CONTROL_HEADROOM)
            before.setBottom(groove.bottom() - CONTROL_HEADROOM)
            after = QRectF(before)
            before.setBottom(face.center().y())
            after.setTop(face.center().y())
        else:
            first = QRectF(handle)
            last = QRectF(handle)
            first.moveLeft(groove.left())
            last.moveRight(groove.right())
            before.setLeft(control_face(first, widget=widget, depth=0).left())
            before.setRight(control_face(last, widget=widget, depth=0).right())
            before.setTop(control_face(knob, widget=widget, depth=0).center().y() - 4)
            before.setHeight(8)
            after = QRectF(before)
            before.setRight(face.center().x())
            after.setLeft(face.center().x())
        painter.setBrush(paper_rail_accent or rail_accent or slider_rail(surface))
        painter.drawRoundedRect(before, corner_radius(2), corner_radius(2))
        painter.setBrush(accent)
        painter.drawRoundedRect(after, corner_radius(2), corner_radius(2))
        if (widget.maximum() > widget.minimum() and handle.width() > 2 * CONTROL_HEADROOM
                and handle.height() > CONTROL_HEADROOM):
            paint_control(painter, widget, knob, accent, shadow=True)
        painter.end()
        return True


def install_live_scrollbars(app):
    install_scroll_shadows(app)
    # Android shows no scrollbars, so it should not pay to inspect every event for them.
    if not running_on_android() and not hasattr(app, '_album_drive_scrollbars'):
        app._album_drive_scrollbars = LiveScrollbars(app)
        app.installEventFilter(app._album_drive_scrollbars)
