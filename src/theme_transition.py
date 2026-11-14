"""Repaint changing colors without rebuilding the application style each frame."""

import re

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QLabel, QLineEdit, QPlainTextEdit, QScrollBar, QSplitterHandle, QStackedWidget, QWidget
from shiboken6 import isValid

from themes import FIELD_SHADE, PANEL_SHADE, accent_shade, corner_radius
from color_rules import disabled_text_color, settings_title_color


TEXT_FIELDS = (QLineEdit, QPlainTextEdit)


def strip_theme_colors(style):
    """Keep geometry, fonts and transparent overlays; palettes supply the colors instead."""
    style = re.sub(r'(?<![-\w])(background(?:-color)?|color|alternate-background-color|placeholder-text-color|'
                   r'selection-background-color|selection-color|border-color)\s*:\s*([^;{}]+);',
                   lambda match: match[0] if match[2].strip() == 'transparent' else '', style)
    return re.sub(r'border-image\s*:[^;{}]+;', '', style)


class ThemeTransition(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.palette = window.palette()
        self.autofill = window.autoFillBackground()
        # Solid surfaces and text use live palettes until the final style commit.
        # Reloading a stylesheet restyles every widget, which takes a second on phones.
        current = QApplication.instance().styleSheet()
        style = strip_theme_colors(current)
        if style != current:
            QApplication.instance().setStyleSheet(style)
            window.update_button_sizes()
        window.setAutoFillBackground(True)
        self.overrides = []
        self.surfaces = set()
        self.registered = set()
        self.register_widgets()

    def register_widgets(self):
        # Include settings opened while the transition is already running.
        self.overrides = [entry for entry in self.overrides if isValid(entry[0])]
        self.registered = {id(entry[0]) for entry in self.overrides}
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
            if isinstance(widget, QSplitterHandle) and widget.splitter() is getattr(self.window, 'browser_splitter', None):
                # The browser column paints its own raised panel; its handle stays see-through.
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

    def tint_text_field(self, field, background, text, placeholder):
        # Stylesheets ignore later palette changes on text fields, so each one gets its own rule.
        tint = field.property('liveThemeTint')
        if tint != background + text and (tint is not None or not field.styleSheet()):
            field.setProperty('liveThemeTint', background + text)
            field.setStyleSheet(f'background: {background}; color: {text}; placeholder-text-color: {placeholder}; border: none;')

    def update_colors(self):
        self.register_widgets()
        app = QApplication.instance()
        background = QColor(app.property('themeBackground'))
        text = QColor(app.property('textColor'))
        accent = QColor(app.property('themeAccent'))
        palette = QPalette(self.palette)
        for role, color in {
            QPalette.Window: background, QPalette.Base: background,
            QPalette.AlternateBase: background.darker(FIELD_SHADE), QPalette.WindowText: text,
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
        media = getattr(self.window, 'android_media', None)
        if media is not None:
            media.set_system_bars(background.name())
        for widget, _, _, _ in self.overrides:
            if not isValid(widget):
                continue
            if widget.window() is not self.window and not widget.window().isVisible():
                continue
            special = QPalette(palette)
            if widget is self.window.tree or self.window.tree.isAncestorOf(widget):
                special.setColor(QPalette.Base, background.darker(PANEL_SHADE))
                special.setColor(QPalette.Window, background.darker(PANEL_SHADE))
            elif isinstance(widget, QLabel) and widget.objectName() in ('heading', 'muted', 'nowPlayingTitle'):
                prop = 'headingTextColor' if widget.objectName() == 'heading' else 'secondaryTextColor'
                special.setColor(QPalette.WindowText, QColor(app.property(prop)))
            elif isinstance(widget, QLabel) and widget.property('settingsOptionTitle'):
                title = settings_title_color(text, background)
                special.setColor(QPalette.WindowText, title)
                special.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text_color(title))
            widget.setPalette(special)
            if self.window.live_theme and isinstance(widget, TEXT_FIELDS):
                self.tint_text_field(widget, background.darker(FIELD_SHADE).name(), text.name(), QColor(disabled_text_color(text)).name())
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
                painter.end()
                # The browser still paints its sunken folder list and halftone on top.
                return False
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
