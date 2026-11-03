from PySide6.QtCore import QEasingCurve, QEvent, QObject, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QHeaderView, QWidget


class ScrollEdgeFade(QWidget):
    def __init__(self, parent, bottom=False, background_only=False):
        super().__init__(parent)
        self.bottom = bottom
        self.background_only = background_only
        self.opacity = 0.0
        self.requested_visible = False
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(260)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self.set_opacity)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet('background: transparent;')
        self.hide()

    def reveal(self, visible):
        if not visible:
            self.requested_visible = False
            self.animation.stop()
            self.hide()
            self.set_opacity(0.0)
        elif not self.requested_visible or self.isHidden():
            self.requested_visible = True
            self.show()

    def showEvent(self, event):
        super().showEvent(event)
        if self.requested_visible:
            self.animation.stop()
            self.set_opacity(0.0)
            self.animation.start()

    def hideEvent(self, event):
        self.animation.stop()
        self.set_opacity(0.0)
        super().hideEvent(event)

    def set_opacity(self, value):
        self.opacity = float(value)
        self.update()
        area = self.parentWidget()
        if self.background_only and isinstance(area, QAbstractScrollArea):
            viewport = area.viewport()
            if viewport is not None:
                viewport.update()

    def paintEvent(self, event):
        if not self.background_only:
            painter = QPainter(self)
            self.paint_background(painter, self.rect())

    def paint_background(self, painter, rect):
        area = self.parentWidget()
        background = area.property('paperBackgroundColor')
        if not background:
            background = QApplication.instance().property('themeBackground') or '#393939'
            if area.objectName() in ('albumDriveDropdownView', 'opticalDiscs'):
                background = QColor(background).darker(110)
        color = QColor(background).darker(125)
        color.setAlpha(105)
        signature = (self.width(), self.height(), color.rgba(), self.bottom)
        if signature != getattr(self, '_signature', None):
            self._signature = signature
            self._image = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
            self._image.fill(Qt.transparent)
            layer = QPainter(self._image)
            clear = QColor(color)
            clear.setAlpha(0)
            gradient = QLinearGradient(0, 0, 0, self.height())
            gradient.setColorAt(0, clear if self.bottom else color)
            gradient.setColorAt(1, color if self.bottom else clear)
            layer.fillRect(self._image.rect(), gradient)
            sides = QLinearGradient(0, 0, self.width(), 0)
            sides.setColorAt(0, Qt.transparent)
            sides.setColorAt(.02, Qt.transparent)
            sides.setColorAt(.12, Qt.white)
            sides.setColorAt(.88, Qt.white)
            sides.setColorAt(.98, Qt.transparent)
            sides.setColorAt(1, Qt.transparent)
            layer.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            layer.fillRect(self._image.rect(), sides)
            layer.end()
        painter.save()
        painter.setOpacity(painter.opacity() * self.opacity)
        painter.drawImage(rect.topLeft(), self._image)
        painter.restore()


class ScrollEdgeShadows(QObject):
    def __init__(self, area):
        super().__init__(area)
        self.area = area
        self.fades = (ScrollEdgeFade(area), ScrollEdgeFade(area, bottom=True))
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        area.verticalScrollBar().valueChanged.connect(self.update)
        area.verticalScrollBar().rangeChanged.connect(self.update)
        self.update()

    def update(self, *args):
        rect = self.area.viewport().geometry()
        height = min(24, rect.height() // 4)
        bar = self.area.verticalScrollBar()
        for fade in self.fades:
            fade.setGeometry(rect.x(), rect.bottom() - height + 1 if fade.bottom else rect.y(),
                             rect.width(), height)
            fade.reveal(height > 0 and (bar.value() < bar.maximum() if fade.bottom else bar.value() > bar.minimum()))
            fade.raise_()
            fade.update()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest, QEvent.StyleChange, QEvent.PaletteChange):
            self.update()
        return False


class ScrollShadowInstaller(QObject):
    def eventFilter(self, widget, event):
        if (event.type() == QEvent.Show and isinstance(widget, QAbstractScrollArea)
                and not isinstance(widget, QHeaderView) and not hasattr(widget, 'edge_fades')):
            ancestor = widget
            while ancestor is not None:
                if ancestor.objectName() in ('fileBrowser', 'albumGrid'):
                    return False
                ancestor = ancestor.parentWidget()
            if not hasattr(widget, 'scroll_edge_shadows'):
                widget.scroll_edge_shadows = ScrollEdgeShadows(widget)
        return False


def install_scroll_shadows(app):
    if not hasattr(app, '_scroll_shadow_installer'):
        app._scroll_shadow_installer = ScrollShadowInstaller(app)
        app.installEventFilter(app._scroll_shadow_installer)

