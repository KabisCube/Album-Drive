"""Repaint changing colors without rebuilding the application style each frame."""

import re

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QLabel, QScrollBar, QSplitterHandle, QStackedWidget, QWidget
from shiboken6 import isValid

from themes import accent_shade, corner_radius
from color_rules import disabled_text_color, settings_title_color


class ThemeTransition(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.palette = window.palette()
        self.autofill = window.autoFillBackground()
        # Keep geometry, fonts, transparent overlays and the paper's own style.
        # Solid surfaces and text use live palettes until the final style commit.
        style = QApplication.instance().styleSheet()
        style = re.sub(r'(?<![-\w])(background(?:-color)?|color|alternate-background-color|'
                       r'selection-background-color|selection-color|border-color)\s*:\s*([^;{}]+);',
                       lambda match: match[0] if match[2].strip() == 'transparent' else '', style)
        style = re.sub(r'border-image\s*:[^;{}]+;', '', style)
        QApplication.instance().setStyleSheet(style)
        window.update_button_sizes()
        window.setAutoFillBackground(True)
        self.overrides = []
        self.surfaces = set()
        self.registered = set()
        self.register_widgets()

    def register_widgets(self):
        # Include settings opened while the transition is already running.
        paper = self.window.album_presentation.booklet
        for widget in self.window.findChildren(QWidget):
            if id(widget) in self.registered:
                continue
            ancestor = widget
            while ancestor is not None and ancestor.objectName() not in ('albumDriveDropdown', 'albumDriveDropdownView'):
                ancestor = ancestor.parentWidget()
            if ancestor is not None:
                continue
            if widget is paper or paper.isAncestorOf(widget):
                continue
            if widget.window() is not self.window and not widget.window().isVisible():
                continue
            self.registered.add(id(widget))
            self.overrides.append((widget, widget.palette(), widget.autoFillBackground(), widget.testAttribute(Qt.WA_StyledBackground)))
            dimmed = widget is self.window.library_pages.widget(0) or self.window.library_pages.widget(0).isAncestorOf(widget)
            if dimmed:
                widget.setAutoFillBackground(False)
            # Item views paint their contents through the viewport's Paint
            # event. Consuming it here hides every folder/row during a fade.
            parent = widget.parentWidget()
            viewport = isinstance(parent, QAbstractScrollArea) and widget is parent.viewport()
            if ((widget is self.window.tree or type(widget) is QWidget or isinstance(widget, (QStackedWidget, QSplitterHandle)))
                    and not dimmed
                    and not viewport
                    and not widget.property('settingsRow')
                    and widget.graphicsEffect() is None
                    and 'background: transparent' not in widget.styleSheet()):
                widget.setAutoFillBackground(widget is not self.window.tree)
                widget.setAttribute(Qt.WA_StyledBackground, False)
                self.surfaces.add(widget)
                widget.installEventFilter(self)

    def update_colors(self):
        self.register_widgets()
        app = QApplication.instance()
        background = QColor(app.property('themeBackground'))
        text = QColor(app.property('textColor'))
        accent = QColor(app.property('themeAccent'))
        palette = QPalette(self.palette)
        for role, color in {
            QPalette.Window: background, QPalette.Base: background,
            QPalette.AlternateBase: background.darker(119), QPalette.WindowText: text,
            QPalette.Text: text, QPalette.Button: QColor(app.property('buttonFill')),
            QPalette.ButtonText: QColor(app.property('buttonTextColor')),
            QPalette.Highlight: QColor(accent_shade(accent.name(), .32)),
            QPalette.HighlightedText: QColor(app.property('selectedTextColor')),
            QPalette.Light: background.lighter(115), QPalette.Mid: accent,
            QPalette.Dark: background.darker(130), QPalette.Shadow: accent.darker(125),
        }.items():
            palette.setColor(role, color)
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(app.property('disabledTextColor')))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(app.property('disabledTextColor')))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text_color(text))
        self.window.setPalette(palette)
        for widget, _, _, _ in self.overrides:
            if not isValid(widget):
                continue
            if widget.window() is not self.window and not widget.window().isVisible():
                continue
            special = QPalette(palette)
            if widget is self.window.tree or self.window.tree.isAncestorOf(widget):
                special.setColor(QPalette.Base, background.darker(110))
                special.setColor(QPalette.Window, background.darker(110))
            elif isinstance(widget, QLabel) and widget.objectName() in ('heading', 'muted', 'nowPlayingTitle'):
                prop = 'headingTextColor' if widget.objectName() == 'heading' else 'secondaryTextColor'
                special.setColor(QPalette.WindowText, QColor(app.property(prop)))
            elif isinstance(widget, QLabel) and widget.property('settingsOptionTitle'):
                title = settings_title_color(text, background)
                special.setColor(QPalette.WindowText, title)
                special.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text_color(title))
            widget.setPalette(special)
            widget.update()
        # Paper retains its cover palette; its knobs follow live button colors.
        for bar in self.window.findChildren(QScrollBar):
            bar.update()
        popup = app.activePopupWidget()
        if popup is not None:
            popup.update()
            for child in popup.findChildren(QWidget):
                child.update()
        self.window.update()
        self.window.tree.viewport().update()

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Paint and widget in self.surfaces:
            painter = QPainter(widget)
            if widget is self.window.tree:
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setPen(Qt.NoPen)
                painter.setBrush(widget.palette().window())
                radius = corner_radius(8, widget.width(), widget.height())
                painter.drawRoundedRect(QRectF(widget.rect()), radius, radius)
            else:
                painter.fillRect(widget.rect(), widget.palette().window())
            painter.end()
            return True
        return False

    def finish(self):
        for widget in self.surfaces:
            if isValid(widget):
                widget.removeEventFilter(self)
        for widget, palette, autofill, styled in self.overrides:
            if isValid(widget):
                widget.setPalette(palette)
                widget.setAutoFillBackground(autofill)
                widget.setAttribute(Qt.WA_StyledBackground, styled)
        self.window.setPalette(self.palette)
        self.window.setAutoFillBackground(self.autofill)
        self.deleteLater()
