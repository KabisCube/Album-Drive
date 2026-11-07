"""Helpers shared by windows that run on both desktops and phones."""
import sys

from PySide6.QtCore import QObject, QSize
from PySide6.QtWidgets import QApplication, QSizePolicy

NARROW_WIDTH = 640
SHORT_HEIGHT = 480


def running_on_android():
    return sys.platform == 'android' or QApplication.platformName() == 'android'


def wrap_freely(label):
    """Let a word-wrapped label narrow to any width and still grow tall enough for its text."""
    # A new policy clears the height-for-width flag QLabel sets for wrapped text.
    policy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    policy.setHeightForWidth(True)
    label.setSizePolicy(policy)


def wrappable_path(path):
    """Add invisible break points so a label can wrap a long path between folders."""
    return str(path).replace('/', '/​').replace('\\', '\\​')


class ScreenFit(QObject):
    """Open a dialog at its preferred size, filling the screen on phones in either orientation."""

    def __init__(self, dialog, width, height):
        super().__init__(dialog)
        self.dialog = dialog
        self.preferred = QSize(width, height)
        self.apply()
        if running_on_android():
            dialog.screen().availableGeometryChanged.connect(self.apply)

    def apply(self, *_):
        screen = self.dialog.screen().availableGeometry()
        if running_on_android() and min(screen.width(), screen.height()) < NARROW_WIDTH:
            self.dialog.setGeometry(screen)
        else:
            self.dialog.resize(self.preferred.boundedTo(screen.size()))
