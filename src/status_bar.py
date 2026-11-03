from PySide6.QtCore import QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStatusBar


class FadingStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.opacity = QGraphicsOpacityEffect(self)
        self.opacity.setOpacity(1)
        self.setGraphicsEffect(self.opacity)
        self.message_timer = QTimer(self)
        self.message_timer.setSingleShot(True)
        self.fade = QPropertyAnimation(self.opacity, b'opacity', self)
        self.fade.setDuration(500)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.message_timer.timeout.connect(self.fade.start)
        self.fade.finished.connect(self.clearMessage)
        self.hide()

    def showMessage(self, message, timeout=15000):
        self.message_timer.stop()
        self.fade.stop()
        self.opacity.setOpacity(1)
        super().showMessage(message)
        self.setVisible(bool(message))
        if message and timeout > 0:
            self.message_timer.start(timeout)

    def clearMessage(self):
        self.message_timer.stop()
        self.fade.stop()
        super().clearMessage()
        self.hide()
        self.opacity.setOpacity(1)
