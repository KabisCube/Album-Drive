"""A local desktop music player for Windows and Linux."""

import sys
import hashlib
import logging
import json
import os
import subprocess
import time
from functools import lru_cache
from collections import OrderedDict, deque
from math import ceil
from pathlib import Path

from app_paths import ASSETS_DIR
from font_support import configure_font_rendering, font_families, load_handwriting_fonts, load_round_fallbacks

from PySide6.QtCore import QDir, QEvent, QEasingCurve, QElapsedTimer, QFile, QIODevice, QLoggingCategory, QPoint, QPointF, QVariantAnimation, QRectF, QSettings, QSignalBlocker, QSize, Qt, QThread, QTimer, QUrl, Signal

# Route FFmpeg output through Qt's severity-aware logger instead of native dumps.
os.environ['QT_FFMPEG_DEBUG'] = '1'
if sys.platform == 'win32':
    os.environ.setdefault('QT_FFMPEG_EXCLUDE_ENCODERS', 'h264_mf,hevc_mf,av1_mf')
QLoggingCategory.setFilterRules('*.debug=false\n*.info=false')
logging.basicConfig(level=logging.WARNING)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QTextLayout, QTextOption, QTransform
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileSystemModel, QGraphicsOpacityEffect, QHBoxLayout,
    QHeaderView, QLabel, QListView, QListWidget, QListWidgetItem, QLayout,
    QMainWindow, QScroller, QSlider, QSizePolicy, QSplitter, QStackedLayout, QStackedWidget, QStyle, QStyledItemDelegate, QStyleOptionSlider, QStyleOptionViewItem, QTableWidget,
    QTableWidgetItem, QToolButton, QTreeView, QVBoxLayout, QWidget,
)

from library import natural_key, scan_library
from file_paths import filesystem_path
from status_bar import FadingStatusBar
from metadata_editor import MetadataEditor
from album_grid import AlbumGrid
from open_case import AlbumPresentation, PLAYING_ROLE
from overflow_controls import OverflowControls
from adaptive_workspace import AdaptiveWorkspace, ResponsiveTransport
from music_folders import choose_music_directory, music_directory
from themes import signed_setting_int, resolve_font, THEME_DEFAULT, ALBUM_SORT_DEFAULT, VOLUME_DEFAULT, BUILDING_GRAY, GRASS_GREEN, TIMELINE_COLOR, CLEANING_DEFAULT, COLOR_SETTINGS, NUMERIC_DEFAULTS, ChunkyBrand, ThemedButton as QPushButton, ThemedComboBox, ThemeSlider, accent_knob, chunky_style, corner_radius, draw_centered_text, round_stylesheet, text_style
from theme_settings import ThemeSettingsDialog, capture_color_theme, custom_color_settings, saved_color_themes
from theme_transition import ThemeTransition, strip_theme_colors
from live_scrollbars import install_live_scrollbars
from scroll_shadows import paint_scroll_background
from case_shell import CASE_DEPTH, CASE_SHADOW_DEPTH, case_frame_color, paint_cd_case, paint_shell, artwork_tray_color, fitted_case_rect
from themes import control_offset
from case_geometry import CASE_WIDTH, CASE_HEIGHT, CASE_PIXMAP_SIZE, sleeve_rect
from color_rules import timeline_colors
from settings_store import create_app_settings, library_cache_path, write_theme_files
from themes import DEFAULT_THEME_IDS, THEME_FADE_MAX_SECONDS, ARTWORK_THEME_DEFAULT, ARTWORK_THEME_MODE_DEFAULT, UI_FONT_DEFAULT, CONTROL_HEADROOM, BUTTON_SHADOW, ThemedMenu, ThemeSaveIcon, button_scale, migrate_button_size
from app_theme import classic_artwork_style, artwork_theme_colors, simplify_theme_colors, soften_theme_colors, button_text_color_for_palette
from button_sounds import prepare_button_sounds, play_button_sound
from case_sounds import prepare_case_sounds, play_case_sound
from audio_devices import selected_output
from themes import MERGED_NUMERIC_SETTINGS, MERGED_COLOR_SETTINGS, MARKER_COLOR_DEFAULT, FONT_SCALE_KEYS, font_sizes, migrate_font_settings
from app_identity import APP_NAME
from responsive import running_on_android
from touch_input import MINIMUM_TOUCH_TARGET, add_touch
from audio_levels import volume_gain
from first_run import FirstRunDialog, apply_system_theme, needs_first_run
from session_palette import load_session_palette, save_session_palette
from app_identity import update_theme_icon
from windows_taskbar import WindowsTaskbar
from optical_discs import DiscEjector, DiscMonitor, DiscReader, audio_album, cached_audio_valid


CLASSIC_STYLE = """
QWidget { background: #16191e; color: #e9edf3; font-size: 13px; }
QMainWindow { background: #16191e; }
QLabel#brand { font-size: 24px; font-weight: 700; color: #bddc9c; }
QLabel#heading { font-size: 26px; font-weight: 700; }
QLabel#muted { color: #94a0ae; }
QLabel#cover { background: transparent; }
QPushButton { background: #2b333e; border: 1px solid #3b4654; border-radius: 6px; padding: 9px 14px; }
QPushButton:hover { background: #3b4959; }
QPushButton:disabled { color: #68727e; }
QPushButton#previous, QPushButton#next { padding: 0px; min-height: 0px; }
QPushButton#play { background: #bddc9c; color: #16191e; border: none; }
QLineEdit { background: #222831; padding: 11px; border: none; border-radius: 6px; }
QPlainTextEdit { border: none; }
QTreeView { background: #1c2128; border: none; padding: 5px; }
QTreeView::item { height: 27px; }
QTreeView::item:selected { background: #3b4c3a; }
QListWidget { background: #16191e; border: none; outline: none; }
QListWidget::item { padding: 8px; border-radius: 8px; }
QListWidget::item:hover { background: #222b30; }
QListWidget::item:selected { background: #344735; color: #ffffff; }
QTableWidget { background: #1c2128; alternate-background-color: #191d23; border: none; }
QTableWidget::item { padding: 7px; }
QTableWidget::item:selected { background: #344735; }
QHeaderView::section { background: #262e38; padding: 9px; border: none; }
QSlider::groove:horizontal { height: 5px; background: #38424d; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #bddc9c; border-radius: 2px; }
QSlider::handle:horizontal { background: #e0edcf; width: 12px; margin: -5px 0; border-radius: 6px; }
QSlider#timeline { min-height: 40px; }
QSlider#timeline::groove:horizontal { height: 32px; border-radius: 16px; }
QSlider#timeline::sub-page:horizontal { border-radius: 16px; }
QSlider#timeline::handle:horizontal { width: 36px; margin: -2px 0; border-radius: 18px; }
QSplitter::handle { background: transparent; border: none; image: none; }
QStatusBar { color: #94a0ae; }
QToolTip { background: #303945; color: #ffffff; border: 1px solid #566272; }
"""

STYLE = chunky_style(CLASSIC_STYLE)
THEMES = {'chunky': ('Chunky landscape', STYLE), 'classic': ('Classic dark', CLASSIC_STYLE)}


def load_app_font():
    app = QApplication.instance()
    if app.property('playerFontLoaded'):
        return
    path = ASSETS_DIR / 'fonts' / UI_FONT_DEFAULT
    font_id = QFontDatabase.addApplicationFont(str(path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        load_round_fallbacks()
        default_font = QFontDatabase.font(families[0], 'Bold', 10)
        default_font.setFamilies(font_families(families[0]))
        configure_font_rendering(default_font)
        app.setFont(default_font)
        marker_fonts = load_handwriting_fonts()
        app.setProperty('handwritingFonts', marker_fonts)
        app.setProperty('handwritingFamily', marker_fonts[0]['family'] if marker_fonts else families[0])
        app.setProperty('trackListFamily', families[0])
        catalog = []
        for font_path in sorted(path.parent.rglob('*')):
            if font_path.relative_to(path.parent).parts[0] in {'cjk', 'handwriting'}:
                continue
            if font_path.suffix.lower() not in {'.otf', '.ttf', '.ttc'}:
                continue
            loaded = QFontDatabase.addApplicationFont(str(font_path))
            bundled_families = QFontDatabase.applicationFontFamilies(loaded)
            for family in bundled_families:
                identity = font_path.relative_to(path.parent).as_posix()
                if len(bundled_families) > 1:
                    identity += '::' + family
                catalog.append({'id': identity, 'name': font_path.name, 'family': family})
        catalog.extend({'id': 'handwriting/' + font['id'], 'name': font['name'], 'family': font['family']}
                       for font in marker_fonts)
        app.setProperty('availableFonts', catalog)
        app.setProperty('playerFontLoaded', True)
    else:
        logging.warning('Unable to load app font: %s', path)


def time_text(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes}:{seconds:02}'


def handwritten_title_path(title, font, area):
    """Fit actual glyph outlines, including overshoots and tilt, inside the sleeve."""
    font = QFont(font)
    rotation = QTransform().rotate(-4)
    maximum = int(QApplication.instance().property('handwritingFontSize') or NUMERIC_DEFAULTS['handwriting_font_size'])
    for size in range(maximum, 5, -1):
        font.setPixelSize(size)
        layout = QTextLayout(title, font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WordWrap)
        layout.setTextOption(option)
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        y = 0.0
        layout.beginLayout()
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(area.width())
            ink = QPainterPath()
            ink.setFillRule(Qt.WindingFill)
            for run in line.glyphRuns():
                raw = run.rawFont()
                for glyph, position in zip(run.glyphIndexes(), run.positions()):
                    ink.addPath(raw.pathForGlyph(glyph).translated(position))
            bounds = ink.boundingRect()
            if not ink.isEmpty():
                ink.translate((area.width() - bounds.width()) / 2 - bounds.left(), y - bounds.top())
                path.addPath(ink)
                y += bounds.height() + max(2, size * 0.14)
        layout.endLayout()
        path = rotation.map(path)
        bounds = path.boundingRect()
        if bounds.width() <= area.width() and bounds.height() <= area.height():
            break
    # Also handle unusually long titles that still exceed the space at 6px.
    bounds = path.boundingRect()
    if bounds.width() > area.width() or bounds.height() > area.height():
        scale = min(area.width() / bounds.width(), area.height() / bounds.height())
        path = QTransform().scale(scale, scale).map(path)
        bounds = path.boundingRect()
    path.translate(area.center() - bounds.center())
    return path


def cd_case_pixmap(artwork, title, handwriting_font=None, case_key=None, tray_color=None):
    """Render a jewel case around the sleeve, with crisp edges on HiDPI screens."""
    pixmap = QPixmap(CASE_PIXMAP_SIZE)
    pixmap.setDevicePixelRatio(CASE_PIXMAP_SIZE.width() / CASE_WIDTH)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setPen(Qt.NoPen)
    paint_shell(painter, case_key, artwork, tray_color)
    sleeve = sleeve_rect(QRectF(0, 0, CASE_WIDTH, CASE_HEIGHT))
    cover = QPixmap()
    has_cover = bool(artwork) and cover.loadFromData(artwork)
    handwritten_title = not has_cover
    if has_cover:
        side = min(cover.width(), cover.height())
        source = QRectF((cover.width() - side) / 2, (cover.height() - side) / 2, side, side)
        painter.drawPixmap(sleeve, cover, source)
    if handwritten_title:
        painter.save()
        painter.setClipRect(sleeve)
        font = QFont(handwriting_font) if handwriting_font is not None else QFont(
            QApplication.instance().property('handwritingFamily') or 'cursive')
        ink = handwritten_title_path(title, font, sleeve.adjusted(7, 7, -7, -7))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(QApplication.instance().property('handwritingColor') or '#1b2834'))
        painter.drawPath(ink)
        painter.restore()
    painter.end()
    return pixmap


@lru_cache(maxsize=256)
def transport_icon(name, color, disabled_color=None):
    if name == 'save-theme':
        return QIcon(ThemeSaveIcon())
    pixmap = QPixmap(64, 64)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QPen(QColor(color), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if name == 'settings':
        gear = QPainterPath()
        gear.addEllipse(QRectF(6, 6, 20, 20))
        tooth = QPainterPath()
        tooth.addRoundedRect(QRectF(-2.5, -14, 5, 7), 1.5, 1.5)
        for angle in range(0, 360, 45):
            gear = gear.united(QTransform().translate(16, 16).rotate(angle).map(tooth))
        hole = QPainterPath()
        hole.addEllipse(QRectF(11.5, 11.5, 9, 9))
        painter.setPen(Qt.NoPen)
        painter.drawPath(gear.subtracted(hole))
    elif name == 'refresh':
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(5, 5, 22, 22), 35 * 16, 285 * 16)
        painter.drawLine(26, 5, 26, 13)
        painter.drawLine(26, 13, 18, 13)
    elif name == 'pause':
        painter.setPen(Qt.NoPen)
        for x in (7, 20):
            painter.drawRoundedRect(QRectF(x, 5, 6, 22), 3, 3)
    else:
        points = [(11, 6), (25, 16), (11, 26)]
        if name == 'previous':
            points = [(23, 7), (11, 16), (23, 25)]
            painter.drawLine(7, 6, 7, 26)
        elif name == 'next':
            points = [(9, 7), (21, 16), (9, 25)]
            painter.drawLine(25, 6, 25, 26)
        elif name == 'eject':
            points = [(8, 18), (16, 6), (24, 18)]
            painter.drawRoundedRect(QRectF(7, 25, 18, 2), 1, 1)
        elif name == 'back':
            points = [(21, 6), (7, 16), (21, 26)]
        path = QPainterPath()
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        path.closeSubpath()
        painter.drawPath(path)
    painter.end()
    icon = QIcon(pixmap)
    if disabled_color is not None:
        icon.addPixmap(transport_icon(name, disabled_color).pixmap(QSize(32, 32)), QIcon.Disabled)
    return icon


class NowPlayingCover(QWidget):
    """Scale the case to available space without imposing the artwork's size."""

    clicked = Signal()

    def __init__(self):
        super().__init__()
        self._pixmap = QPixmap()
        self.sheen_key = ''
        self.cover_pressed = False
        self.auto_height = True
        self.baked = running_on_android()
        self.baked_case = QPixmap()
        self.baked_tag = None
        self.frozen_theme = None
        self.baked_width = 0.0
        self.resizing = False
        self.setMinimumSize(64, 64)
        self.setContentsMargins(10, 0, 10, 0)

    def sizeHint(self):
        return QSize(210, 220)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.auto_height:
            return
        height = self.heightForWidth(self.width())
        if self.minimumHeight() != height or self.maximumHeight() != height:
            self.setFixedHeight(height)

    def heightForWidth(self, width):
        return max(64, round(max(1, width - 20) * CASE_HEIGHT / CASE_WIDTH))

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def pixmap(self):
        return self._pixmap

    def image_rect(self):
        return fitted_case_rect(self.contentsRect())

    def case_center_x(self):
        rect = self.image_rect()
        return rect.center().x() - control_offset(self, rect, CASE_DEPTH).x()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._pixmap.isNull() and self.image_rect().contains(event.position()):
            self.cover_pressed = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.cover_pressed:
            self.cover_pressed = False
            if not self._pixmap.isNull() and self.image_rect().contains(event.position()):
                self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        if self._pixmap.isNull():
            return
        target = self.image_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.baked:
            self.paint_baked(painter, target)
        else:
            self.paint_case(painter, target)

    def paint_case(self, painter, target):
        lighting = None
        source = getattr(self, 'lighting_source', None)
        if source is not None:
            origin = self.mapFromGlobal(source.mapToGlobal(QPoint()))
            lighting = QRectF(source.rect()).translated(origin)
        paint_cd_case(painter, self, target, self._pixmap, self.sheen_key, visible=lighting, shadow=True)

    def paint_baked(self, painter, target):
        """Copy a finished case, stretching the last one while a swipe resizes it."""
        ratio = self.devicePixelRatioF()
        margin = 2 * (CASE_DEPTH + CASE_SHADOW_DEPTH) + 4
        theme = self.frozen_theme or QApplication.instance().property('themeBackground')
        tag = self.sheen_key, self._pixmap.cacheKey(), ratio, theme
        if tag != self.baked_tag or (not self.resizing and abs(target.width() - self.baked_width) > .5):
            self.baked_case = QPixmap(ceil((target.width() + 2 * margin) * ratio), ceil((target.height() + 2 * margin) * ratio))
            self.baked_case.setDevicePixelRatio(ratio)
            self.baked_case.fill(Qt.transparent)
            layer = QPainter(self.baked_case)
            layer.setRenderHint(QPainter.SmoothPixmapTransform)
            layer.translate(margin - target.x(), margin - target.y())
            self.paint_case(layer, target)
            layer.end()
            self.baked_tag, self.baked_width = tag, target.width()
        scale = target.width() / self.baked_width
        painter.drawPixmap(QRectF(target.x() - margin * scale, target.y() - margin * scale,
                                  self.baked_case.deviceIndependentSize().width() * scale,
                                  self.baked_case.deviceIndependentSize().height() * scale),
                           self.baked_case, QRectF(self.baked_case.rect()))


class NowPlayingPanel(QWidget):
    geometryChanged = Signal()

    def __init__(self):
        super().__init__()
        self.content = QWidget(self)
        self.content.installEventFilter(self)
        self.cover = None
        self.resizable = False
        self.progress = 0.0
        self.content_height = 0
        self.expanded = False
        self.arranging = False
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(900)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)
        self.animation.valueChanged.connect(self.set_progress)
        self.animation.finished.connect(self.finish)
        self.setFixedHeight(0)
        self.hide()

    def reveal(self, expanded):
        if self.expanded == expanded:
            self.arrange()
            return
        self.expanded = expanded
        self.animation.stop()
        if not self.window().isVisible():
            self.setVisible(expanded)
            self.arrange()
            self.set_progress(1.0 if expanded else 0.0)
            self.finish()
            return
        self.show()
        self.arrange()
        target = 1.0 if expanded else 0.0
        with QSignalBlocker(self.animation):
            self.animation.setStartValue(self.progress)
            self.animation.setEndValue(target)
            self.animation.setDuration(max(180, round((900 if expanded else 420) * abs(target - self.progress))))
            self.animation.setCurrentTime(0)
        self.animation.start()

    def set_progress(self, value):
        self.progress = float(value)
        if self.resizable:
            return
        height = round(self.content_height * self.progress)
        if self.maximumHeight() != height:
            self.setFixedHeight(height)
            self.geometryChanged.emit()

    def set_resizable(self, resizable):
        if resizable == self.resizable:
            return
        self.resizable = resizable
        if resizable:
            self.setMinimumHeight(0)
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.arrange()

    def arrange(self):
        if self.arranging or self.cover is None or self.content.layout() is None:
            return
        self.arranging = True
        try:
            cover_height = self.cover.heightForWidth(self.width())
            other_height = self.content.layout().sizeHint().height() - self.cover.height()
            if self.resizable:
                maximum = cover_height + other_height
                if self.maximumHeight() != maximum:
                    self.setMaximumHeight(maximum)
                    self.geometryChanged.emit()
                cover_height = min(cover_height, max(0, self.height() - other_height))
            elif isinstance(self.parentWidget(), QSplitter):
                splitter = self.parentWidget()
                available = splitter.height() - splitter.widget(0).minimumHeight() - splitter.handleWidth()
                cover_height = min(cover_height, max(0, available - other_height))
            if self.cover.maximumHeight() != cover_height:
                self.cover.setFixedHeight(cover_height)
            height = self.height() if self.resizable else self.content.layout().sizeHint().height()
            self.content_height = height
            if self.content.size() != QSize(self.width(), height):
                self.content.setGeometry(0, 0, self.width(), height)
                self.content.layout().setGeometry(self.content.rect())
            self.set_progress(self.progress)
        finally:
            self.arranging = False

    def finish(self):
        if not self.expanded:
            self.hide()
            if self.cover is not None:
                self.cover.setPixmap(QPixmap())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.resizable or event.size().width() != event.oldSize().width():
            self.arrange()
        self.geometryChanged.emit()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.geometryChanged.emit()

    def event(self, event):
        if event.type() == QEvent.LayoutRequest and hasattr(self, 'arranging'):
            self.arrange()
        return super().event(event)

    def eventFilter(self, watched, event):
        if watched is self.content and event.type() == QEvent.LayoutRequest:
            self.arrange()
        elif watched is self.parentWidget() and event.type() == QEvent.Resize:
            self.arrange()
            self.geometryChanged.emit()
        return super().eventFilter(watched, event)


class ArtworkHeading(QLabel):
    def __init__(self, cover):
        super().__init__('NOW PLAYING')
        self.cover = cover

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect()).translated(self.cover.case_center_x() - self.width() / 2, 0)
        draw_centered_text(painter, rect, self.font(), self.text(),
                           QApplication.instance().property('textColor') or '#e9edf3')


class MarqueeTitle(QLabel):
    """Single-line track title, with a slow loop only when it overflows."""

    def __init__(self):
        super().__init__()
        self.offset = 0.0
        self.pause_remaining = 1.2
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.advance)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(0, self.fontMetrics().height() + 4)

    def setText(self, text):
        super().setText(text)
        self.restart()

    def restart(self):
        self.offset = 0.0
        self.pause_remaining = 1.2
        self.clock.start()
        if self.isVisible() and self.fontMetrics().horizontalAdvance(self.text()) > self.width():
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def advance(self):
        seconds = self.clock.restart() / 1000
        if self.pause_remaining > 0:
            self.pause_remaining -= seconds
            return
        width = self.fontMetrics().horizontalAdvance(self.text())
        self.offset += seconds * 20
        if self.offset >= width + 40:
            self.offset = 0.0
            self.pause_remaining = 1.2
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.restart()

    def showEvent(self, event):
        super().showEvent(event)
        self.restart()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(QApplication.instance().property('secondaryTextColor') or '#d0dce2'))
        y = (self.height() - self.fontMetrics().height()) / 2 + self.fontMetrics().ascent()
        painter.drawText(QPointF(-self.offset, y), self.text())
        width = self.fontMetrics().horizontalAdvance(self.text())
        if width > self.width():
            painter.drawText(QPointF(width + 40 - self.offset, y), self.text())


class AlbumOverlay(QWidget):
    dismissed = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dismissed.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class AlbumScaleIcon(QWidget):
    """Small and large jewel cases identify the album-size slider."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 26)
        self.setAccessibleName('Album size: small to large CD cases')
        self.setToolTip('Change album size')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(QApplication.instance().property('textColor') or '#ffffff')
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.NoBrush)
        for rect in (QRectF(1, 12, 12.5, 11), QRectF(16, 6, 19.3, 17)):
            painter.drawRoundedRect(rect, 1.5, 1.5)
            spine = rect.left() + rect.width() * .2
            painter.drawLine(QPointF(spine, rect.top()), QPointF(spine, rect.bottom()))


class FolderModel(QFileSystemModel):
    """The folder tree uses names and disclosure arrows without system icons."""

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DecorationRole:
            return None
        return super().data(index, role)


class FolderNameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        plain = QStyleOptionViewItem(option)
        plain.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus | QStyle.State_MouseOver)
        super().paint(painter, plain, index)
        if self.parent().selectionModel().isSelected(index):
            text = QStyleOptionViewItem(plain)
            self.initStyleOption(text, index)
            rect = self.parent().style().subElementRect(QStyle.SE_ItemViewItemText, text, self.parent())
            width = min(rect.width() - 4, text.fontMetrics.horizontalAdvance(text.text))
            if width > 0:
                painter.save()
                painter.setPen(QPen(QColor(QApplication.instance().property('themeAccent') or GRASS_GREEN),
                                    3, Qt.SolidLine, Qt.FlatCap))
                y = min(option.rect.bottom() - 2, rect.center().y() + text.fontMetrics.height() / 2 + 1)
                left = rect.right() - width - 2 if text.direction == Qt.RightToLeft else rect.left() + 2
                painter.drawLine(QPointF(left, y), QPointF(left + width, y))
                painter.restore()


class FolderBrowser(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QTreeView.ScrollPerPixel)
        self.scroll_target = 0
        self.wheel_remainder = 0
        self.scroll_animation = QVariantAnimation(self)
        self.scroll_animation.setDuration(240)
        self.scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.scroll_animation.valueChanged.connect(lambda value: self.verticalScrollBar().setValue(round(value)))
        self.verticalScrollBar().sliderPressed.connect(self.scroll_animation.stop)
        self.verticalScrollBar().actionTriggered.connect(self.scroll_animation.stop)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if event.pixelDelta().y():
            distance = event.pixelDelta().y()
        elif event.angleDelta().y():
            self.wheel_remainder += event.angleDelta().y()
            steps = int(self.wheel_remainder / 120)
            self.wheel_remainder -= steps * 120
            row_height = max(1, self.sizeHintForRow(0))
            distance = steps * row_height * QApplication.wheelScrollLines()
        else:
            super().wheelEvent(event)
            return
        if distance:
            bar = self.verticalScrollBar()
            base = self.scroll_target if self.scroll_animation.state() == QVariantAnimation.Running else bar.value()
            self.scroll_target = max(bar.minimum(), min(bar.maximum(), base - distance))
            self.scroll_animation.stop()
            self.scroll_animation.setStartValue(float(bar.value()))
            self.scroll_animation.setEndValue(float(self.scroll_target))
            self.scroll_animation.start()
        event.accept()

    def keyPressEvent(self, event):
        self.scroll_animation.stop()
        super().keyPressEvent(event)

    def setRootIndex(self, index):
        self.scroll_animation.stop()
        self.wheel_remainder = 0
        super().setRootIndex(index)

    def drawRow(self, painter, option, index):
        plain = QStyleOptionViewItem(option)
        plain.showDecorationSelected = False
        plain.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus | QStyle.State_MouseOver)
        super().drawRow(painter, plain, index)

    def setModel(self, model):
        super().setModel(model)
        model.directoryLoaded.connect(lambda _: self.viewport().update())

    def drawBranches(self, painter, rect, index):
        model = self.model()
        if model.canFetchMore(index):
            model.fetchMore(index)
        has_children = model.rowCount(index) > 0
        selected = self.selectionModel().isSelected(index)
        if selected:
            painter.save()
            painter.setClipRect(rect, Qt.IntersectClip)
            painter.fillRect(rect, self.palette().base())
            paint_scroll_background(painter, self.viewport())
            painter.restore()
        if not has_children and not selected:
            return
        app = QApplication.instance()
        color = app.property('folderArrowColor') or '#d0dce2'
        arrow = transport_icon('play', color)
        painter.save()
        bounds = QRectF(rect)
        x = bounds.left() + self.indentation() / 2 if self.isRightToLeft() else bounds.right() - self.indentation() / 2
        painter.translate(x, bounds.center().y())
        painter.translate(0, -1)
        if self.isExpanded(index):
            painter.rotate(90)
        elif self.isRightToLeft():
            painter.rotate(180)
        if has_children:
            arrow.paint(painter, -8, -8, 16, 16)
        painter.restore()


class TimelineSlider(QSlider):
    """Seek slider with an elapsed-time overlay that leaves dragging intact."""

    def wheelEvent(self, event):
        event.ignore()

    seekRequested = Signal(int)

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setObjectName('timeline')
        self.setAccessibleName('Playback position')
        self.setMinimumHeight(60)
        self.setStyleSheet('''
QSlider#timeline::groove:horizontal { height: 32px; }
QSlider#timeline::handle:horizontal { width: 60px; height: 48px; margin: -14px 0 -2px 0; border: none; background: transparent; }
''')
        self.click_seeking = False
        self.fade_colors = None
        self.knob = accent_knob(QApplication.instance().property('themeAccent') or GRASS_GREEN,
                                QApplication.instance().property('buttonFill') or '#f7f5f1')

    def seek_to_point(self, point):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        span = max(1, self.width() - handle.width())
        position = max(0, min(span, round(point.x() - handle.width() / 2)))
        value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), position, span, option.upsideDown)
        self.setValue(value)
        return value

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.click_seeking = True
            self.setFocus(Qt.MouseFocusReason)
            self.setSliderDown(True)
            self.seekRequested.emit(self.seek_to_point(event.position()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.click_seeking:
            self.seek_to_point(event.position())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.click_seeking and event.button() == Qt.LeftButton:
            value = self.seek_to_point(event.position())
            self.seekRequested.emit(value)
            self.click_seeking = False
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def timestamp_path(self):
        font = QFont(self.font())
        font.setPixelSize(int(QApplication.instance().property('timelineFontSize') or NUMERIC_DEFAULTS['timeline_font_size']))
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        path.addText(0, 0, font, time_text(self.value() / 1000))
        path.translate(QRectF(self.rect()).center() - path.boundingRect().center())
        return path

    def colors(self):
        if self.fade_colors is not None:
            return self.fade_colors
        app = QApplication.instance()
        return timeline_colors(app.property('themeBackground') or BUILDING_GRAY,
                              app.property('themeAccent') or TIMELINE_COLOR,
                              app.property('themeBackgroundAccent'))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        knob_width = max(1, min(handle.width() - 2 * CONTROL_HEADROOM, handle.height() - CONTROL_HEADROOM))
        inset = (handle.width() - knob_width) / 2
        groove = QRectF(inset, (self.height() - 32) / 2, max(1, self.width() - 2 * inset), 32)
        clip = QPainterPath()
        radius = corner_radius(16, groove.width(), groove.height())
        clip.addRoundedRect(groove, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        unfilled_color, progress_color, filled_text, unfilled_text = self.colors()
        painter.fillRect(groove, unfilled_color)
        fill = QRectF(groove)
        if option.upsideDown:
            fill.setLeft(handle.center().x())
        else:
            fill.setRight(handle.center().x())
        painter.fillRect(fill, progress_color)
        painter.restore()
        text_path = self.timestamp_path()
        painter.save()
        painter.setClipRect(QRectF(self.rect()).intersected(fill))
        painter.fillPath(text_path, filled_text)
        painter.restore()
        painter.save()
        unfilled = QRectF(groove)
        if option.upsideDown:
            unfilled.setRight(fill.left())
        else:
            unfilled.setLeft(fill.right())
        painter.setClipRect(unfilled)
        painter.fillPath(text_path, unfilled_text)
        painter.restore()
        # The timestamp sits over the fill, and the knob passes over it.
        self.knob.paint(painter, handle)
        painter.end()


class DiscEjectButton(QToolButton):
    """A real keyboard-accessible eject button without a selection fill."""
    def paintEvent(self, event):
        painter = QPainter(self)
        color = QApplication.instance().property('themeBackgroundAccent') or '#cfe10e'
        if not self.isEnabled():
            painter.setOpacity(.4)
        icon = transport_icon('eject', color)
        icon.paint(painter, self.rect().adjusted(5, 5, -5, -5))
        if self.underMouse() or self.hasFocus():
            painter.setPen(QPen(QColor(QApplication.instance().property('themeAccent') or GRASS_GREEN), 3))
            painter.drawLine(5, self.height() - 3, self.width() - 5, self.height() - 3)


class DiscDriveDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        app = QApplication.instance()
        painter.save()
        painter.setFont(option.font)
        painter.setPen(QColor(app.property('textColor') or '#ffffff'))
        icon = QRectF(option.rect.left() + 2, option.rect.center().y() - 9, 18, 18)
        app.windowIcon().paint(painter, icon.toRect())
        text = option.rect.adjusted(28, 0, -36, 0)
        title = option.fontMetrics.elidedText(str(index.data()), Qt.ElideRight, text.width())
        painter.drawText(text, Qt.AlignVCenter | Qt.AlignLeft, title)
        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(QColor(app.property('themeAccent') or GRASS_GREEN), 3, Qt.SolidLine, Qt.FlatCap))
            width = min(text.width(), option.fontMetrics.horizontalAdvance(title))
            y = min(text.bottom() - 2, text.center().y() + option.fontMetrics.height() / 2 + 1)
            painter.drawLine(QPointF(text.left(), y), QPointF(text.left() + width, y))
        painter.restore()


class DiscDriveList(QListWidget):
    ejectRequested = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.buttons = {}
        self.setObjectName('opticalDiscs')
        self.setAccessibleName('Disc Drive')
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setItemDelegate(DiscDriveDelegate(self))
        self.setStyleSheet('''QListWidget#opticalDiscs { background: transparent; border: none; padding: 5px; outline: none; }
QListWidget#opticalDiscs::item { padding: 0; border: none; background: transparent; }
QListWidget#opticalDiscs::item:selected, QListWidget#opticalDiscs::item:hover { background: transparent; }''')

    def sync_buttons(self):
        for button in self.buttons.values():
            button.deleteLater()
        self.buttons = {}
        for row in range(self.count()):
            root = self.item(row).data(Qt.UserRole)
            button = DiscEjectButton(self.viewport())
            button.setStyleSheet('background: transparent; border: none;')
            button.setAccessibleName('Eject Disc Drive ' + str(Path(root).drive))
            button.setToolTip('Pause and eject disc')
            button.setFocusPolicy(Qt.StrongFocus)
            button.pressed.connect(play_button_sound)
            button.clicked.connect(lambda checked=False, root=root: self.ejectRequested.emit(root))
            self.buttons[root] = button
        self.position_buttons()

    def position_buttons(self):
        if not hasattr(self, 'buttons'):
            return
        for row in range(self.count()):
            button = self.buttons.get(self.item(row).data(Qt.UserRole))
            if button is None:
                continue
            rect = self.visualItemRect(self.item(row))
            size = min(28, rect.height())
            button.setGeometry(self.viewport().width() - size - 2, rect.center().y() - size // 2, size, size)
            button.setVisible(rect.intersects(self.viewport().rect()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_buttons()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.position_buttons()


class DiscDrivePanel(QWidget):
    """Clip the drive rows as they slide out above the folder browser."""
    def __init__(self):
        super().__init__()
        self.list = DiscDriveList(self)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(lambda value: self.setFixedHeight(round(value)))
        self.animation.finished.connect(lambda: self.setVisible(self.height() > 0))
        self.content_height = 0
        self.setFixedHeight(0)
        self.hide()

    def reveal(self, height):
        self.animation.stop()
        self.content_height = max(height, self.content_height if height == 0 else 0)
        start = self.height() if self.isVisible() else 0
        self.show()
        self.animation.setStartValue(start)
        self.animation.setEndValue(height)
        self.animation.start()
        self.arrange()

    def arrange(self):
        self.list.setGeometry(0, self.height() - self.content_height, self.width(), self.content_height)
        self.list.position_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(QApplication.instance().property('themeBackground') or BUILDING_GRAY).darker(110))


class ThemePreparer(QThread):
    """Work out album colors ahead of time so opening an album does not pause the interface."""
    ready = Signal(object, object)

    def __init__(self, jobs, parent):
        super().__init__(parent)
        self.jobs = jobs

    def run(self):
        for job in self.jobs:
            if self.isInterruptionRequested():
                return
            self.ready.emit(job, artwork_theme_colors(*job))


class Scanner(QThread):
    result = Signal(object, object)
    progress = Signal(int)
    failed = Signal(str)

    def __init__(self, folder, parent):
        super().__init__(parent)
        self.folder = folder
        self.cache_path = library_cache_path(parent.settings)
        self.disc = parent.optical_discs.get(str(Path(folder))) if hasattr(parent, 'optical_discs') else None

    def run(self):
        try:
            last_progress = 0
            def progress(count):
                nonlocal last_progress
                now = time.monotonic()
                if now - last_progress >= .1:
                    self.progress.emit(count)
                    last_progress = now
            albums, skipped = scan_library(self.folder, self.isInterruptionRequested, progress, cache_path=self.cache_path)
            if self.disc is not None and self.disc.audio and not self.isInterruptionRequested():
                album = audio_album(self.disc, self.cache_path.parent, self.isInterruptionRequested)
                if album is not None:
                    albums.insert(0, album)
            if not self.isInterruptionRequested():
                self.result.emit(albums, skipped)
        except Exception as error:
            self.failed.emit(str(error))


NOW_PLAYING_FLICK_SPEED = 900
THEME_COLOR_CACHE_SIZE = 64
THEME_PREPARE_DELAY_MS = 400
ANDROID_THEME_STEP_MS = 100
SETTINGS_PREPARE_DELAY_MS = 2500
VOLATILE_SETTINGS = {'browsing_state', 'window_geometry', 'sidebar_width', 'volume', 'settings_view_state'}
ANDROID_TRANSPORT_ROW_GAP = -8
PLAYBACK_STALL_MS = 1500
FILE_MANAGER_LABEL = 'Open in Windows Explorer' if sys.platform == 'win32' else 'Open in file manager'


class PlayerWindow(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        load_app_font()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)
        self.compact_mode = False
        self.is_android = running_on_android()
        self.live_theme = False
        self.theme_renderer = None
        self.setMinimumSize(320, 320 if self.is_android else 600)
        self.settings = settings if settings is not None else create_app_settings()
        migrate_font_settings(self.settings)
        self.first_run_needed = needs_first_run(self.settings)
        if self.first_run_needed:
            apply_system_theme(self.settings)
        if not self.settings.value('artwork_theme_enabled', ARTWORK_THEME_DEFAULT, type=bool):
            selected = next((preset for preset in saved_color_themes(self.settings)
                             if preset['id'] == self.settings.value('selected_color_theme', '')), None)
            if selected is not None:
                for key, value in selected['colors'].items():
                    self.settings.setValue(key, value)
        palette = load_session_palette(self.settings)
        self.set_theme(str(self.settings.value('theme', THEME_DEFAULT)),
                       palette['colors'] if palette else None, palette.get('artwork', False) if palette else None)
        self.albums = []
        self.queue = []
        self.queue_index = -1
        self.resume_scanner = None
        self.resume_position = None
        self.resume_play_requested = False
        self.resume_seek_scheduled = False
        self.scanners = set()
        self.generation = 0
        self.closing = False
        self.current_folder = None
        try:
            self.browsing_state = json.loads(str(self.settings.value('browsing_state', '{}')))
            if not isinstance(self.browsing_state, dict):
                self.browsing_state = {}
        except (ValueError, TypeError):
            self.browsing_state = {}
        for key in ('browser_scroll', 'browser_horizontal', 'album_scroll'):
            self.browsing_state[key] = max(0, signed_setting_int(self.browsing_state.get(key, 0)))
        if not isinstance(self.browsing_state.get('expanded', []), list):
            self.browsing_state['expanded'] = []
        self.browsing_restore_attempts = 0
        self.browsing_restore_signature = None
        self.browsing_restore_stable = 0
        self.browsing_restore_timer = QTimer(self)
        self.browsing_restore_timer.setSingleShot(True)
        self.browsing_restore_timer.setInterval(30)
        self.browsing_restore_timer.timeout.connect(self.restore_browsing_state)
        self.viewed_album = None
        self.theme_colors = OrderedDict()
        self.theme_preparer = None
        self.prepared_settings = None
        self.prepared_settings_values = None
        self.settings_prepare_timer = QTimer(self)
        self.settings_prepare_timer.setSingleShot(True)
        self.settings_prepare_timer.setInterval(SETTINGS_PREPARE_DELAY_MS)
        self.settings_prepare_timer.timeout.connect(self.prepare_settings)
        self.theme_prepare_timer = QTimer(self)
        self.theme_prepare_timer.setSingleShot(True)
        self.theme_prepare_timer.setInterval(THEME_PREPARE_DELAY_MS)
        self.theme_prepare_timer.timeout.connect(self.prepare_visible_themes)
        self.optical_discs = {}
        self.disc_monitor = None
        self.pending_eject = None
        self.disc_ejector = None
        self.cd_request = 0
        self.cd_loading = False

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setDevice(selected_output())
        self.player.setAudioOutput(self.audio)
        self.playback_shutdown = False
        QApplication.instance().aboutToQuit.connect(self.shutdown_playback)
        self.media_devices = QMediaDevices(self)
        self.media_devices.audioOutputsChanged.connect(self.refresh_audio_output, Qt.QueuedConnection)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.seekableChanged.connect(lambda seekable: self.seek.setEnabled(seekable and self.player.duration() > 0))
        self.player.seekableChanged.connect(lambda seekable: self.apply_resume_position())
        self.player.playbackStateChanged.connect(self.playback_changed)
        self.player.mediaStatusChanged.connect(self.media_status_changed)
        self.player.errorOccurred.connect(self.playback_error)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setSizeConstraint(QLayout.SetNoConstraint)
        outer.setContentsMargins(16, 16, 16, 0 if self.is_android else 10)
        splitter = AdaptiveWorkspace()
        self.workspace = splitter
        splitter.sidebar_width = self.settings.value('sidebar_width', splitter.sidebar_width, type=int)
        outer.addWidget(splitter, 1)

        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        self.sidebar_layout = side
        side.setContentsMargins(0, 0, 0, 0)
        brand = ChunkyBrand(APP_NAME)
        self.brand = brand
        brand.setObjectName('brand')
        side.addWidget(brand)
        self.disc_panel = DiscDrivePanel()
        self.disc_list = self.disc_panel.list
        self.disc_panel.animation.finished.connect(self.finish_disc_animation)
        self.disc_list.currentItemChanged.connect(self.select_optical_disc)
        self.disc_list.ejectRequested.connect(self.eject_optical_disc)
        side.addWidget(self.disc_panel)
        self.files = FolderModel(self)
        self.files.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
        self.files.setReadOnly(True)
        self.files.setRootPath(QDir.rootPath())
        self.tree = FolderBrowser()
        self.tree.setObjectName('fileBrowser')
        self.tree.setStyleSheet('QTreeView#fileBrowser { padding: 16px 16px 14px; }')
        self.tree.setIndentation(28)
        self.tree.setItemDelegate(FolderNameDelegate(self.tree))
        self.tree.setModel(self.files)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_folder_menu)
        self.folder_menu = ThemedMenu(self.tree)
        self.folder_menu.setObjectName('folderContextMenu')
        self.open_folder_action = self.folder_menu.addAction(FILE_MANAGER_LABEL)
        self.open_folder_action.triggered.connect(lambda: self.open_in_file_manager(self.folder_menu_path))
        self.folder_menu_path = None
        self.files.directoryLoaded.connect(self.schedule_browsing_restore)
        self.tree.pressed.connect(self.cancel_browsing_restore)
        self.tree.verticalScrollBar().sliderPressed.connect(self.cancel_browsing_restore)
        for bar in (self.tree.verticalScrollBar(), self.tree.horizontalScrollBar()):
            bar.parentWidget().setObjectName('fileBrowserScrollBarContainer')
            bar.parentWidget().setAttribute(Qt.WA_StyledBackground, True)
        self.tree.setHeaderHidden(True)
        for column in range(1, self.files.columnCount()):
            self.tree.hideColumn(column)
        self.tree.selectionModel().currentChanged.connect(self.folder_selected)
        self.tree.clicked.connect(self.open_compact_folder)
        self.tree.setMinimumHeight(70)
        browser_column = QSplitter(Qt.Vertical)
        self.browser_splitter = browser_column
        browser_column.setHandleWidth(0)
        browser_column.addWidget(self.tree)
        browser_column.setCollapsible(0, False)
        now_playing = NowPlayingPanel()
        self.now_playing = now_playing
        playing_layout = QVBoxLayout(now_playing.content)
        playing_layout.setContentsMargins(0, side.spacing(), 0, 0)
        playing_layout.setSpacing(2)
        self.cover = NowPlayingCover()
        self.cover.auto_height = False
        now_playing.cover = self.cover
        self.cover.setObjectName('cover')
        self.cover.clicked.connect(self.open_now_playing_album)
        self.now_playing_heading = ArtworkHeading(self.cover)
        self.now_playing_heading.setObjectName('nowPlayingHeading')
        playing_layout.addWidget(self.now_playing_heading)
        playing_layout.addWidget(self.cover)
        self.track_title = MarqueeTitle()
        self.track_title.setObjectName('nowPlayingTitle')
        playing_layout.addWidget(self.track_title)
        browser_column.addWidget(now_playing)
        now_playing.geometryChanged.connect(self.restore_sidebar_split, Qt.QueuedConnection)
        self.split_animation = QVariantAnimation(self)
        self.split_animation.setDuration(180)
        self.split_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.split_animation.valueChanged.connect(lambda height: self.set_now_playing_height(round(height)))
        self.split_animation.finished.connect(self.finish_now_playing_resize)
        self.pending_split_drag = 0.0
        self.split_drag_timer = QTimer(self)
        self.split_drag_timer.setSingleShot(True)
        self.split_drag_timer.setInterval(16)
        self.split_drag_timer.timeout.connect(self.apply_now_playing_drag)
        if self.is_android:
            now_playing.set_resizable(True)
            add_touch(now_playing, on_drag=self.drag_now_playing, on_drag_end=self.settle_now_playing)
        browser_column.installEventFilter(now_playing)
        browser_column.setStretchFactor(0, 1)
        browser_column.setStretchFactor(1, 0)
        side.addWidget(browser_column, 1)
        splitter.addWidget(sidebar)

        library_area = QWidget()
        self.library_area = library_area
        library_layout = QVBoxLayout(library_area)
        self.library_layout = library_layout
        library_layout.setContentsMargins(16, 0, 0, 0)
        splitter.addWidget(library_area)
        self.library_pages = QStackedWidget()
        library = QWidget()
        library.setObjectName('albumLibrary')
        library.setStyleSheet('QWidget#albumLibrary { background: transparent; }')
        self.library_pages.addWidget(library)
        self.library_opacity = QGraphicsOpacityEffect(library)
        self.library_opacity.setOpacity(1)
        library.setGraphicsEffect(self.library_opacity)
        content = QVBoxLayout(library)
        self.album_content = content
        content.setContentsMargins(0, 0, 0, 0)
        self.count_label = QLabel('No folder selected')
        self.count_label.setObjectName('muted')
        self.album_header = OverflowControls(self.count_label)
        header = self.album_header.controls
        self.album_scale_control = QWidget()
        self.album_scale_control.setStyleSheet('background: transparent;')
        self.album_scale_control.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        scale_layout = QHBoxLayout(self.album_scale_control)
        scale_layout.setContentsMargins(0, CONTROL_HEADROOM, 0, 0)
        scale_layout.setSpacing(2)
        self.album_scale_icon = AlbumScaleIcon()
        scale_layout.addWidget(self.album_scale_icon)
        self.album_size = ThemeSlider()
        self.album_size.setAccessibleName('Album size')
        self.album_size.setRange(50, 150)
        self.album_size.setFixedWidth(140 + 2 * CONTROL_HEADROOM)
        self.album_size.setValue(int(self.settings.value('album_scale', NUMERIC_DEFAULTS['album_scale'])))
        self.album_size.valueChanged.connect(self.change_album_size)
        scale_layout.addWidget(self.album_size)
        header.addWidget(self.album_scale_control)
        self.sort_albums = ThemedComboBox()
        self.sort_albums.setAccessibleName('Sort albums')
        self.sort_albums.setMinimumWidth(160)
        self.sort_albums.setFixedHeight(44)
        for label, mode in (('Alphabetical', 'alphabetical'), ('Oldest', 'oldest'), ('Newest', 'newest'), ('Custom', 'custom')):
            self.sort_albums.addItem(label, mode)
        self.sort_albums.setCurrentIndex(max(0, self.sort_albums.findData(str(self.settings.value('album_sort', ALBUM_SORT_DEFAULT)))))
        self.sort_albums.currentIndexChanged.connect(self.change_album_sort)
        header.addWidget(self.sort_albums)
        self.save_theme_button = QPushButton()
        self.save_theme_button.setObjectName('saveTheme')
        self.save_theme_button.clicked.connect(self.save_current_theme)
        header.addWidget(self.save_theme_button)
        self.theme_toast = QLabel(self)
        self.theme_toast.setObjectName('themeSavedToast')
        self.theme_toast.setTextFormat(Qt.PlainText)
        self.theme_toast.setWordWrap(True)
        self.theme_toast.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.theme_toast.hide()
        self.theme_toast_timer = QTimer(self)
        self.theme_toast_timer.setSingleShot(True)
        self.theme_toast_timer.timeout.connect(self.theme_toast.hide)
        refresh = QPushButton('Refresh')
        self.refresh_button = refresh
        refresh.clicked.connect(lambda: self.scan(self.current_folder) if self.current_folder else self.choose_folder())
        header.addWidget(refresh)
        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.edit_theme_settings)
        header.addWidget(self.settings_button)
        self.tidy_button = QPushButton('Tidy up')
        self.tidy_button.clicked.connect(lambda: self.grid.tidy_up())
        header.addWidget(self.tidy_button)
        if self.is_android:
            # Phones need the header space more than these two controls.
            self.album_scale_control.hide()
            refresh.hide()
            self.sort_albums.setProperty('fitButtonTextLocally', True)
            self.album_header.flexible = self.sort_albums
            self.pinch_scale = NUMERIC_DEFAULTS['album_scale']
        self.album_header_opacities = []
        # The fixed-size slider moves during resize; an opacity-effect source
        # cache can retain an old clipped area until the next hover repaint.
        # Its own painter handles dimming instead.
        fading_controls = [self.count_label, self.album_scale_icon, self.sort_albums, self.save_theme_button, refresh, self.tidy_button]
        if self.is_android:
            fading_controls.append(self.settings_button)
        for control in fading_controls:
            opacity = QGraphicsOpacityEffect(control)
            opacity.setOpacity(1)
            control.setGraphicsEffect(opacity)
            self.album_header_opacities.append(opacity)
        # Keep the header accessible above both the grid and the track overlay.
        if self.is_android:
            # The open case slides over this header to leave more room for tracks.
            self.album_header.setParent(library_area)
        else:
            library_layout.addWidget(self.album_header)
        library_layout.addWidget(self.library_pages, 1)
        self.grid = AlbumGrid()
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self.show_album_metadata_menu)
        self.grid.itemPressed.connect(self.cancel_browsing_restore)
        self.grid.verticalScrollBar().sliderPressed.connect(self.cancel_browsing_restore)
        if self.is_android:
            for view in (self.tree, self.grid):
                QScroller.scroller(view.viewport()).stateChanged.connect(lambda state: self.cancel_browsing_restore())
            QScroller.scroller(self.grid.viewport()).stateChanged.connect(self.grid_scroll_state_changed)
        else:
            for widget in (self.tree, self.grid, self.tree.viewport(), self.grid.viewport(),
                           self.tree.verticalScrollBar(), self.tree.horizontalScrollBar(), self.grid.verticalScrollBar()):
                widget.installEventFilter(self)
        self.grid.setObjectName('albumGrid')
        self.grid.setStyleSheet('QListWidget#albumGrid { background: transparent; }')
        self.cover.lighting_source = self.grid.viewport()
        self.grid.orderChanged.connect(self.save_custom_order)
        self.case_icon_cache = OrderedDict()
        self.case_source_cache = OrderedDict()
        self.case_cache_bytes = {'icons': 0, 'sources': 0}
        self.case_prefetch_signature = None
        self.album_scale_timer = QTimer(self)
        self.album_scale_timer.setSingleShot(True)
        self.album_scale_timer.setInterval(33)
        self.album_scale_timer.timeout.connect(self.apply_album_size)
        self.album_size.sliderReleased.connect(self.apply_album_size)
        self.case_prefetch_rows = deque()
        self.case_prefetch_timer = QTimer(self)
        self.case_prefetch_timer.setSingleShot(True)
        self.case_prefetch_timer.timeout.connect(self.prefetch_album_icon)
        self.grid.verticalScrollBar().valueChanged.connect(self.schedule_icon_prefetch)
        self.grid.icon_provider = self.album_icon
        self.grid.sheen_key_provider = lambda row: str(self.albums[self.grid.item(row).data(Qt.UserRole)].folder)
        placeholder = QPixmap(CASE_PIXMAP_SIZE)
        placeholder.setDevicePixelRatio(3)
        placeholder.fill(Qt.transparent)
        self.case_placeholder = QIcon(placeholder)
        self.grid.set_cleaning(self.settings.value('i_like_cleaning', CLEANING_DEFAULT, type=bool))
        self.tidy_button.setVisible(self.grid.cleaning_enabled)
        self.grid.tidyStateChanged.connect(lambda tidying: self.update_album_header_controls())
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setMovement(QListView.Free)
        self.grid.setResizeMode(QListView.Fixed)
        self.grid.setIconSize(QSize(328, 300))
        self.grid.setGridSize(QSize(354, 328))
        self.grid.set_hover_options(float(self.settings.value('hover_rotation', NUMERIC_DEFAULTS['hover_rotation'])),
                                    float(self.settings.value('hover_growth', NUMERIC_DEFAULTS['hover_growth'])),
                                    int(self.settings.value('album_horizontal_spacing', NUMERIC_DEFAULTS['album_horizontal_spacing'])),
                                    int(self.settings.value('album_vertical_spacing', NUMERIC_DEFAULTS['album_vertical_spacing'])),
                                    int(self.settings.value('hover_lift', NUMERIC_DEFAULTS['hover_lift'])))
        self.grid.setSpacing(10)
        self.grid.setWordWrap(True)
        self.grid.setUniformItemSizes(True)
        self.change_album_size(self.album_size.value())
        self.grid.itemActivated.connect(self.open_album)
        self.grid.itemClicked.connect(self.open_album)
        if self.is_android:
            add_touch(self.grid.viewport(), scrolls=True, on_pinch=self.pinch_albums, on_pinch_end=self.finish_album_pinch)
        content.addWidget(self.grid, 1)
        self.album_page = AlbumOverlay()
        self.album_page.setObjectName('albumOverlay')
        self.album_page.setStyleSheet('QWidget#albumOverlay { background: transparent; }')
        self.album_page.dismissed.connect(self.show_albums)
        self.library_pages.addWidget(self.album_page)
        self.library_pages.layout().setStackingMode(QStackedLayout.StackAll)
        self.album_page.hide()
        album_layout = QVBoxLayout(self.album_page)
        album_layout.setContentsMargins(16, 0, 0, 0)
        self.album_presentation = AlbumPresentation()
        self.album_presentation.dismissed.connect(self.show_albums)
        album_layout.addWidget(self.album_presentation, 1)
        self.album_artwork = self.album_presentation.front
        self.album_artwork.lighting_source = self.grid.viewport()
        if self.is_android:
            add_touch(self.album_artwork)
        self.album_table = self.album_presentation.table
        self.album_table.setShowGrid(False)
        self.album_table.setAlternatingRowColors(False)
        self.album_table.setHorizontalHeaderLabels(['#', 'Title'])
        self.album_table.horizontalHeader().hide()
        self.album_table.verticalHeader().hide()
        self.album_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.album_table.setSelectionMode(QTableWidget.SingleSelection)
        self.album_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.album_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.album_table.customContextMenuRequested.connect(self.show_track_metadata_menu)
        self.cover.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cover.customContextMenuRequested.connect(self.show_playing_metadata_menu)
        self.album_artwork.setContextMenuPolicy(Qt.CustomContextMenu)
        self.album_artwork.customContextMenuRequested.connect(self.show_open_metadata_menu)
        self.album_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        (self.album_table.cellClicked if self.is_android else self.album_table.cellDoubleClicked).connect(
            lambda row, column: self.play_album(self.viewed_album, row) if self.viewed_album else None)
        self.play = QPushButton('Play')
        self.play.setObjectName('play')
        self.play.setProperty('themeRole', 'highlight')
        self.play.setFixedHeight(44)
        self.play.clicked.connect(self.toggle_play)
        self.previous = QPushButton('Previous')
        self.previous.setObjectName('previous')
        self.previous.setFixedHeight(32)
        self.previous.clicked.connect(self.previous_track)
        self.seek = TimelineSlider()
        self.seek.setRange(0, 0)
        self.seek.setEnabled(False)
        self.seek.seekRequested.connect(self.player.setPosition)
        self.next = QPushButton('Next')
        self.next.setObjectName('next')
        self.next.setFixedHeight(32)
        self.next.clicked.connect(self.next_track)
        self.volume = ThemeSlider()
        self.volume.setAccessibleName('Volume')
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(100 + 2 * CONTROL_HEADROOM)
        self.volume.setValue(int(self.settings.value('volume', VOLUME_DEFAULT)))
        self.volume.setToolTip(f'{self.volume.value()}%')
        self.volume.valueChanged.connect(lambda value: self.volume.setToolTip(f'{value}%'))
        self.audio.setVolume(volume_gain(self.volume.value()))
        self.volume.valueChanged.connect(lambda value: self.audio.setVolume(volume_gain(value)))
        for button in (self.play, self.previous, self.next):
            button.setProperty('centerFlatFace', True)
        self.transport = ResponsiveTransport(self.play, self.previous, self.next, self.seek, self.volume)
        if self.is_android:
            self.transport.compact_row_gap = ANDROID_TRANSPORT_ROW_GAP
        self.workspace.mode_animation.valueChanged.connect(self.transport.set_mix)
        outer.addWidget(self.transport)
        self.back_button = QPushButton('Back')
        self.back_button.setAccessibleName('Back to file browser')
        self.back_button.clicked.connect(self.navigate_back)
        self.back_button.hide()
        outer.addWidget(self.back_button)
        self.back_action = QAction(self)
        self.back_action.setShortcut(QKeySequence('Back'))
        self.back_action.triggered.connect(self.navigate_back)
        self.back_action.setEnabled(False)
        self.addAction(self.back_action)
        self.escape_action = QAction(self)
        self.escape_action.setShortcut(QKeySequence('Esc'))
        self.escape_action.triggered.connect(self.navigate_back)
        self.escape_action.setEnabled(False)
        self.addAction(self.escape_action)
        self.update_transport_icons()
        self.set_controls()
        self.update_button_sizes()

        self.play_action = QAction(self)
        self.play_action.setShortcut(QKeySequence('Space'))
        self.play_action.triggered.connect(self.toggle_play)
        self.addAction(self.play_action)
        (self.library_area if self.is_android else QApplication.instance()).installEventFilter(self)
        self.setStatusBar(FadingStatusBar(self))
        if not self.first_run_needed:
            QTimer.singleShot(0, self.open_saved_library)
        geometry = self.settings.value('window_geometry')
        if geometry is not None:
            self.restoreGeometry(geometry)
        QTimer.singleShot(0, self.restore_last_session)
        self.taskbar = WindowsTaskbar(self, transport_icon)
        if self.is_android:
            self.enter_live_theme()
            QApplication.instance().focusWindowChanged.connect(self.refresh_live_theme)
            self.settings_prepare_timer.start()
        self.update_responsive_layout(animate=False)
        self.disc_timer = QTimer(self)
        self.disc_timer.setInterval(3000)
        self.disc_timer.timeout.connect(self.poll_optical_discs)
        if sys.platform == 'win32' and QApplication.platformName() == 'windows':
            from windows_identity import update_windows_identity
            update_windows_identity(QApplication.instance())
            self.disc_timer.start()
            QTimer.singleShot(0, self.poll_optical_discs)

    def set_theme(self, name, colors=None, artwork_active=None):
        self.clear_theme_fade()
        self.leave_live_theme()
        if name not in THEMES:
            name = 'chunky'
        saved = self.saved_theme_colors()
        accent, background, timeline = (saved[prop] for prop in ('themeAccent', 'themeBackground', 'timelineColor'))
        QApplication.instance().setProperty('playerTheme', name)
        for prop, color in saved.items():
            QApplication.instance().setProperty(prop, color)
        QApplication.instance().setProperty('artworkTheme', bool(colors) if artwork_active is None else artwork_active)
        QApplication.instance().setProperty('customColorTheme', self.settings.value('selected_color_theme', '') not in ('', *DEFAULT_THEME_IDS))
        if colors:
            colors = soften_theme_colors(colors)
            for prop, color in colors.items():
                QApplication.instance().setProperty(prop, color)
            accent = colors['themeAccent']
            background = colors['themeBackground']
            timeline = colors['timelineColor']
        app = QApplication.instance()
        install_live_scrollbars(app)
        marker = QColor(str(self.settings.value('marker_text_color', MARKER_COLOR_DEFAULT)))
        app.setProperty('handwritingColor', marker.name() if marker.isValid() else MARKER_COLOR_DEFAULT)
        app.setProperty('audioOutputDevice', str(self.settings.value('audio_output_device', '')))
        properties = {key: prop for _, _, key, prop, _ in COLOR_SETTINGS}
        for alias, canonical in MERGED_COLOR_SETTINGS.items():
            app.setProperty(properties[alias], app.property(properties[canonical]))
        migrate_button_size(self.settings)
        rounding = max(0, min(100, int(self.settings.value('corner_roundness', NUMERIC_DEFAULTS['corner_roundness']))))
        QApplication.instance().setProperty('cornerRoundness', rounding)
        resolved_fonts = font_sizes(self.settings)
        for key, default in NUMERIC_DEFAULTS.items():
            if key.endswith('_font_size') or key in ('button_size', 'button_icon_size', 'ui_thickness', 'folder_vertical_spacing', 'button_sound_volume', 'case_open_volume', 'case_close_volume'):
                prop = key.split('_')[0] + ''.join(word.title() for word in key.split('_')[1:])
                source = MERGED_NUMERIC_SETTINGS.get(key, key)
                value = resolved_fonts[key] if key.endswith('_font_size') else signed_setting_int(self.settings.value(source, default))
                QApplication.instance().setProperty(prop, value)
        prepare_button_sounds()
        prepare_case_sounds()
        QApplication.instance().setProperty('trackListVerticalSpacing', max(-32, min(48,
            signed_setting_int(self.settings.value('track_list_vertical_spacing', NUMERIC_DEFAULTS['track_list_vertical_spacing'])))))
        fonts = QApplication.instance().property('availableFonts') or []
        ui_font_id = str(self.settings.value('ui_font', UI_FONT_DEFAULT))
        ui_font = resolve_font(fonts, ui_font_id)
        family = ui_font_id.removeprefix('system:') if ui_font_id.startswith('system:') else (ui_font['family'] if ui_font else '')
        if family not in QFontDatabase.families():
            fallback = resolve_font(fonts, UI_FONT_DEFAULT)
            family = fallback['family'] if fallback else QApplication.instance().font().family()
        app.setProperty('uiFontFamily', family)
        interface_font = QFontDatabase.font(family, 'Bold' if ui_font_id.split('::')[0] == UI_FONT_DEFAULT else '', 10)
        interface_font.setFamilies(font_families(family))
        configure_font_rendering(interface_font)
        if app.font() != interface_font:
            app.setFont(interface_font)
        app.setProperty('trackListFamily', family)
        self.refresh_theme_colors(update_tracklist=True)
        self.settings.setValue('theme', name)
        if hasattr(self, 'brand'):
            self.brand.updateGeometry()
            self.brand.update()
        if hasattr(self, 'grid'):
            self.album_size.setValue(int(self.settings.value('album_scale', NUMERIC_DEFAULTS['album_scale'])))
            self.grid.set_cleaning(self.settings.value('i_like_cleaning', CLEANING_DEFAULT, type=bool))
            self.tidy_button.setVisible(self.grid.cleaning_enabled)
            self.grid.set_hover_options(float(self.settings.value('hover_rotation', NUMERIC_DEFAULTS['hover_rotation'])),
                                        float(self.settings.value('hover_growth', NUMERIC_DEFAULTS['hover_growth'])),
                                        int(self.settings.value('album_horizontal_spacing', NUMERIC_DEFAULTS['album_horizontal_spacing'])),
                                        int(self.settings.value('album_vertical_spacing', NUMERIC_DEFAULTS['album_vertical_spacing'])),
                                        int(self.settings.value('hover_lift', NUMERIC_DEFAULTS['hover_lift'])))
        if hasattr(self, 'play'):
            self.album_scale_icon.update()
            self.album_presentation.update_theme()
            self.seek.knob = accent_knob(accent, QApplication.instance().property('buttonFill'))
            self.update_transport_icons()
            self.seek.update()
            artwork_signature = (app.property('handwritingColor'), resolved_fonts['handwriting_font_size'])
            if artwork_signature == getattr(self, '_artwork_settings_signature', None):
                self.grid.viewport().update()
                return
            self._artwork_settings_signature = artwork_signature
            self.clear_case_cache()
            self.grid.viewport().update()
            if self.viewed_album is not None:
                album = self.viewed_album
                self.album_artwork.pixmap = cd_case_pixmap(album.artwork, album.title,
                    handwriting_font=self.artist_handwriting(album.folder.parent), case_key=str(album.folder))
                self.album_artwork.update()
            if self.queue_index >= 0:
                album = self.queue[self.queue_index][1]
                self.update_now_playing_cover(album)
            else:
                self.update_now_playing_cover()

    def refresh_theme_colors(self, update_tracklist=False):
        """Update colors without resetting layouts, artwork or UI animations."""
        app = QApplication.instance()
        name = app.property('playerTheme')
        app.setProperty('brandTextColor', app.property('themeHighlight'))
        for prop in ('buttonTextColor', 'buttonIconColor', 'disabledTextColor'):
            app.setProperty(prop, app.property('themeBackgroundAccent'))
        for prop in ('secondaryTextColor', 'headingTextColor', 'selectedTextColor',
                     'timelineTextColor', 'paperTextColor'):
            app.setProperty(prop, app.property('textColor'))
        if (update_tracklist and getattr(self, 'album_presentation', None) is not None
                and self.album_presentation.uses_global_text):
            self.album_presentation.update_theme()
        colors = {prop: app.property(prop) for _, _, _, prop, _ in COLOR_SETTINGS}
        accent, background, timeline = (colors[prop] for prop in ('themeAccent', 'themeBackground', 'timelineColor'))
        update_theme_icon(app, colors['themeHighlight'])
        rounding = app.property('cornerRoundness')
        transition = getattr(self, 'theme_renderer', None)
        if transition is not None:
            transition.update_colors()
            self.brand.update()
            self.seek.knob = accent_knob(accent, app.property('buttonFill'))
            self.seek.update()
            self.update_transport_icons()
            return
        style = chunky_style(CLASSIC_STYLE, accent, background, timeline, rounding) if name == 'chunky' else CLASSIC_STYLE
        if name == 'classic' and (app.property('artworkTheme') or app.property('customColorTheme')):
            style = classic_artwork_style(style, colors)
        style += text_style()
        style += 'QListWidget#albumGrid::item:hover, QListWidget#albumGrid::item:selected { background: transparent; border: none; }'
        style += '''
QTreeView, QTableWidget, QTabWidget::pane { border-radius: 8px; }
QTabBar::tab, QMenu, QSpinBox, QDoubleSpinBox { border-radius: 6px; }
QToolTip { border-radius: 4px; }
'''
        if name == 'classic':
            style += 'QPushButton, QPushButton#play { background: ' + QApplication.instance().property('buttonFill') + '; }'
        style = round_stylesheet(style, rounding)
        # Cap radii to the available width so extra rounding never becomes square.
        panel = QColor(background).darker(110).name()
        style += f'''
QTreeView#fileBrowser QScrollBar:vertical {{ background: {panel}; border-radius: {12 * rounding / 100:g}px; }}
QTreeView#fileBrowser QScrollBar:horizontal {{ background: {panel}; border-radius: {12 * rounding / 100:g}px; }}
QTreeView#fileBrowser QScrollBar::sub-page, QTreeView#fileBrowser QScrollBar::add-page {{ border-radius: {4 * rounding / 100:g}px; }}
QWidget#fileBrowserScrollBarContainer, QTreeView#fileBrowser::corner {{ background: {panel}; }}
QTreeView#fileBrowser::item:selected, QTreeView#fileBrowser::item:hover {{ background: transparent; }}
QTreeView#fileBrowser::branch {{ background: transparent; }}
QTreeView#fileBrowser {{ outline: none; background: {panel}; }}
'''
        if self.is_android:
            style = strip_theme_colors(style)
        if QApplication.instance().styleSheet() != style:
            QApplication.instance().setStyleSheet(style)
        if hasattr(self, 'disc_panel') and self.optical_discs:
            target = min(3, self.disc_list.count()) * self.disc_list.sizeHintForRow(0) + 10
            if target != self.disc_panel.content_height:
                self.disc_panel.reveal(target)
        if hasattr(self, 'play'):
            self.update_button_sizes()
        if hasattr(self, 'brand'):
            self.brand.update()
        if hasattr(self, 'play'):
            self.album_scale_icon.update()
            self.seek.knob = accent_knob(accent, app.property('buttonFill'))
            self.update_transport_icons()
            self.seek.update()
        self.update()
        if self.live_theme:
            self.enter_live_theme()

    def theme_fade_seconds(self):
        seconds = self.settings.value('theme_fade_seconds', NUMERIC_DEFAULTS['theme_fade_seconds'], type=float)
        return max(0, min(THEME_FADE_MAX_SECONDS, seconds))

    def clear_theme_fade(self):
        fading = getattr(self, 'theme_fade', None) is not None
        if fading:
            self.theme_fade.stop()
            self.theme_fade.deleteLater()
            self.theme_fade = None
        if getattr(self, 'theme_renderer', None) is not None and (fading or not self.live_theme):
            if not self.live_theme:
                self.leave_live_theme()
            self.seek.fade_colors = None
            self.freeze_case_theme(None)
            self.refresh_theme_colors()
            self.grid.viewport().update()
            self.cover.update()

    def leave_live_theme(self):
        if getattr(self, 'theme_renderer', None) is not None:
            self.theme_renderer.finish()
            self.theme_renderer = None

    def enter_live_theme(self):
        """Android stays on palette colors so a new album never reloads the whole stylesheet."""
        self.live_theme = True
        self.theme_renderer = ThemeTransition(self)
        self.theme_renderer.update_colors()

    def refresh_live_theme(self, *_):
        if self.live_theme and self.theme_renderer is not None:
            self.theme_renderer.update_colors()

    def freeze_case_theme(self, theme):
        """Keep cached cases through a fade; rebuilding them for every color step is what makes it slow."""
        self.grid.frozen_theme = theme
        self.cover.frozen_theme = theme

    def now_playing_theme_colors(self):
        if not self.settings.value('artwork_theme_enabled', ARTWORK_THEME_DEFAULT, type=bool):
            return None
        if 0 <= self.queue_index < len(self.queue):
            colors = self.cached_theme_colors(self.queue[self.queue_index][1].artwork,
                                              str(self.settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT)))
            if colors is not None:
                colors.pop('paperBackgroundColor', None)  # Belongs to the track list, not the app.
            return colors
        return None

    def album_track_theme_colors(self, artwork):
        return self.cached_theme_colors(
            artwork, str(self.settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT)))

    def album_paper_colors(self, artwork):
        """Album colors for the track list; albums without art use the default theme."""
        colors = self.album_track_theme_colors(artwork)
        if colors is None:
            colors = self.saved_theme_colors()
            colors['paperBackgroundColor'] = colors['themeBackground']
        return colors

    def refresh_open_album_colors(self):
        if self.viewed_album is not None:
            self.album_presentation.set_artwork(self.viewed_album.artwork, self.album_paper_colors(self.viewed_album.artwork))

    def store_theme_colors(self, job, colors):
        self.theme_colors[job] = colors
        self.theme_colors.move_to_end(job)
        while len(self.theme_colors) > THEME_COLOR_CACHE_SIZE:
            self.theme_colors.popitem(last=False)

    def cached_theme_colors(self, artwork, mode):
        job = artwork, mode
        if job in self.theme_colors:
            self.theme_colors.move_to_end(job)
        else:
            self.store_theme_colors(job, artwork_theme_colors(artwork, mode))
        colors = self.theme_colors[job]
        return dict(colors) if colors is not None else None

    def prepare_visible_themes(self):
        if self.closing or self.theme_preparer is not None or not self.grid.isVisible():
            return
        columns = self.grid.layout_columns
        pitch = max(1, self.grid.row_pitch())
        first = self.grid.verticalScrollBar().value() // pitch * columns
        visible = (self.grid.viewport().height() // pitch + 2) * columns
        mode = str(self.settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT))
        jobs = []
        for row in range(first, min(self.grid.count(), first + visible)):
            job = self.albums[self.grid.item(row).data(Qt.UserRole)].artwork, mode
            if job[0] and job not in self.theme_colors and job not in jobs:
                jobs.append(job)
        if jobs:
            self.theme_preparer = ThemePreparer(jobs, self)
            self.theme_preparer.ready.connect(self.store_theme_colors)
            self.theme_preparer.finished.connect(self.theme_preparer_finished)
            self.theme_preparer.start(QThread.LowPriority)

    def theme_preparer_finished(self):
        self.theme_preparer.deleteLater()
        self.theme_preparer = None
        if QScroller.scroller(self.grid.viewport()).state() == QScroller.Inactive:
            self.theme_prepare_timer.start()

    def grid_scroll_state_changed(self, state):
        self.theme_prepare_timer.stop()
        if state != QScroller.Inactive:
            if self.theme_preparer is not None:
                self.theme_preparer.requestInterruption()
        else:
            self.theme_prepare_timer.start()

    def saved_theme_colors(self):
        colors = {}
        selected = next((preset for preset in saved_color_themes(self.settings)
                         if preset['id'] == self.settings.value('selected_color_theme', '')), None)
        base = selected['colors'] if selected is not None else custom_color_settings(self.settings)
        for _, _, key, prop, default in COLOR_SETTINGS:
            canonical = MERGED_COLOR_SETTINGS.get(key, key)
            color = QColor(base[canonical])
            colors[prop] = color.name() if color.isValid() else default
        if selected is not None and selected.get('preserve_palette') is True:
            colors = soften_theme_colors(colors)
            foreground = button_text_color_for_palette(colors)
            colors.update({prop: foreground for prop in ('buttonTextColor', 'buttonIconColor', 'disabledTextColor')})
            return colors
        return simplify_theme_colors(colors)

    def theme_from_now_playing(self):
        app = QApplication.instance()
        custom = self.settings.value('selected_color_theme', '') not in ('', *DEFAULT_THEME_IDS)
        mode_changed = app.property('customColorTheme') != custom
        app.setProperty('customColorTheme', custom)
        artwork_colors = self.now_playing_theme_colors()
        target = self.saved_theme_colors()
        target.update(artwork_colors or {})
        for prop in ('brandTextColor',):
            target[prop] = target['themeHighlight']
        # An unchanged album must not restart a transition already in progress.
        if getattr(self, 'theme_target', None) == target and getattr(self, 'theme_fade', None) is not None:
            return
        app = QApplication.instance()
        if all(app.property(prop) == color for prop, color in target.items()):
            # A new target can equal the current frame while an older fade is
            # still running; cancel that fade so it cannot restore stale colors.
            self.clear_theme_fade()
            self.theme_target = target
            if mode_changed or bool(app.property('artworkTheme')) != bool(artwork_colors):
                app.setProperty('artworkTheme', bool(artwork_colors))
                self.refresh_theme_colors()
            return
        start = {prop: QColor(app.property(prop)) for prop in target}
        timeline_start = self.seek.colors()
        self.clear_theme_fade()
        self.theme_target = target
        target_colors = {prop: QColor(color) for prop, color in target.items()}
        duration = self.theme_fade_seconds()
        if duration == 0:
            for prop, color in target.items():
                app.setProperty(prop, color)
            app.setProperty('artworkTheme', bool(artwork_colors))
            self.refresh_theme_colors()
            return
        # Keep classic's dynamic surfaces active until the final fallback frame.
        app.setProperty('artworkTheme', True)
        timeline_target = timeline_colors(target['themeBackground'], target['themeAccent'],
                                          target['themeBackgroundAccent'])
        self.seek.fade_colors = timeline_start
        self.freeze_case_theme((app.property('themeBackground'), case_frame_color().name()))
        if self.theme_renderer is None:
            self.theme_renderer = ThemeTransition(self)
        self.theme_renderer.update_colors()
        self.theme_fade = QVariantAnimation(self)
        self.theme_fade.setDuration(round(duration * 1000))
        self.theme_fade.setStartValue(0.0)
        self.theme_fade.setEndValue(1.0)
        self.theme_fade.setEasingCurve(QEasingCurve.Linear)
        last_frame = -100
        step_interval = ANDROID_THEME_STEP_MS if self.is_android else 16

        def advance(amount):
            nonlocal last_frame
            elapsed = self.theme_fade.currentTime()
            if amount < 1 and elapsed - last_frame < step_interval:
                return
            last_frame = elapsed
            self.seek.fade_colors = tuple(
                QColor(*(round(a + (b - a) * amount) for a, b in
                         zip(first.getRgb()[:3], second.getRgb()[:3])))
                for first, second in zip(timeline_start, timeline_target))
            for prop, first in start.items():
                second = target_colors[prop]
                color = QColor(*(round(a + (b - a) * amount) for a, b in
                                 zip(first.getRgb()[:3], second.getRgb()[:3])))
                app.setProperty(prop, color.name())
            app.setProperty('brandLineColor', QColor(app.property('themeBackground')).darker(110).name())
            if amount >= 1:
                app.setProperty('artworkTheme', bool(artwork_colors))
            self.refresh_theme_colors()

        self.theme_fade.valueChanged.connect(advance)
        self.theme_fade.finished.connect(self.clear_theme_fade)
        self.theme_fade.start()

    def update_now_playing_cover(self, album=None):
        self.cover.sheen_key = str(album.folder) if album is not None else ''
        self.cover.setCursor(Qt.PointingHandCursor if album is not None else Qt.ArrowCursor)
        if album is None:
            self.now_playing.reveal(False)
            return
        font = self.artist_handwriting(album.folder.parent)
        case = cd_case_pixmap(album.artwork, album.title, handwriting_font=font,
                              case_key=str(album.folder))
        self.cover.setPixmap(case)
        self.now_playing.reveal(True)
        if self.now_playing.resizable and self.now_playing.height() == 0:
            height = self.browser_splitter.height()
            self.browser_splitter.setSizes([round(height * .4), round(height * .6)])

    def show_first_run_setup(self):
        if not self.first_run_needed:
            return
        self.settings.setValue('welcome_started', True)
        self.settings.sync()
        dialog = FirstRunDialog(self.settings, self)
        accepted = dialog.exec() == QDialog.Accepted
        self.first_run_needed = False
        if accepted:
            self.apply_settings()
        if self.current_folder is None:
            self.open_saved_library()

    def open_saved_library(self):
        last = Path(str(self.settings.value('folder', music_directory())))
        browser_root = Path(str(self.settings.value('browser_root', last)))
        if filesystem_path(browser_root).is_dir():
            self.select_folder(browser_root, last)
        elif filesystem_path(last).is_dir():
            self.select_folder(last)

    def edit_theme_settings(self):
        if getattr(self, 'settings_dialog', None) is not None:
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        self._applied_settings = {key: self.settings.value(key) for key in self.settings.allKeys()}
        dialog = self.take_prepared_settings() or ThemeSettingsDialog(self.settings, self)
        self.settings_dialog = dialog
        dialog.applied.connect(self.apply_settings)
        def finished(result):
            self.settings_dialog = None
            dialog.deleteLater()
            if self.is_android:
                self.settings_prepare_timer.start()
        dialog.finished.connect(finished)
        dialog.show()
        self.refresh_live_theme()

    def settings_values(self):
        return {key: self.settings.value(key) for key in self.settings.allKeys()
                if key not in VOLATILE_SETTINGS and not key.startswith('session/')}

    def prepare_settings(self):
        """Build Settings while idle, because phones take most of a second to do it on demand."""
        if (self.closing or self.prepared_settings is not None or getattr(self, 'settings_dialog', None) is not None
                or self.first_run_needed or QApplication.activeModalWidget() is not None):
            return
        if QScroller.scroller(self.grid.viewport()).state() != QScroller.Inactive:
            self.settings_prepare_timer.start()
            return
        dialog = ThemeSettingsDialog(self.settings, self)
        dialog.color_preview_timer.stop()
        dialog.ensurePolished()
        self.prepared_settings = dialog
        self.prepared_settings_values = self.settings_values()

    def discard_prepared_settings(self):
        if self.prepared_settings is not None:
            self.prepared_settings.deleteLater()
            self.prepared_settings = None

    def take_prepared_settings(self):
        dialog = self.prepared_settings
        if dialog is None or self.prepared_settings_values != self.settings_values():
            self.discard_prepared_settings()
            return None
        self.prepared_settings = None
        dialog.original_settings = {key: self.settings.value(key) for key in self.settings.allKeys()}
        return dialog

    def apply_settings(self):
        app = QApplication.instance()
        values = {key: self.settings.value(key) for key in self.settings.allKeys()}
        previous = getattr(self, '_applied_settings', {})
        changed = {key for key in values.keys() | previous.keys() if values.get(key) != previous.get(key)}
        self._applied_settings = values
        geometry_keys = set(FONT_SCALE_KEYS.values()) | {
            'theme', 'main_font_size', 'ui_font', 'button_size', 'button_icon_size', 'ui_thickness',
            'corner_roundness', 'folder_vertical_spacing', 'track_list_vertical_spacing', 'marker_text_color'}
        geometry_changed = not previous or bool(changed & geometry_keys)
        if geometry_changed:
            current = {prop: app.property(prop) for _, _, _, prop, _ in COLOR_SETTINGS}
            self.set_theme(str(self.settings.value('theme', THEME_DEFAULT)), current,
                           bool(app.property('artworkTheme')))
        else:
            if 'album_scale' in changed:
                self.album_size.setValue(self.settings.value('album_scale', NUMERIC_DEFAULTS['album_scale'], type=int))
            for key in ('button_sound_volume', 'case_open_volume', 'case_close_volume'):
                if key in changed:
                    prop = key.split('_')[0] + ''.join(word.title() for word in key.split('_')[1:])
                    app.setProperty(prop, self.settings.value(key, NUMERIC_DEFAULTS[key], type=int))
            if 'i_like_cleaning' in changed:
                self.grid.set_cleaning(self.settings.value('i_like_cleaning', CLEANING_DEFAULT, type=bool))
                self.tidy_button.setVisible(self.grid.cleaning_enabled)
            if changed & {'hover_rotation', 'hover_growth', 'hover_lift', 'album_horizontal_spacing', 'album_vertical_spacing'}:
                self.grid.set_hover_options(*(self.settings.value(key, NUMERIC_DEFAULTS[key], type=kind)
                    for key, kind in (('hover_rotation', float), ('hover_growth', float),
                                      ('album_horizontal_spacing', int), ('album_vertical_spacing', int), ('hover_lift', int))))
        color_keys = {key for _, _, key, _, _ in COLOR_SETTINGS} | {
            'artwork_theme_enabled', 'artwork_theme_mode', 'selected_color_theme', 'custom_theme_colors'}
        if geometry_changed or changed & color_keys:
            self.theme_from_now_playing()
            self.refresh_open_album_colors()
        if not previous or 'continuous_playback' in changed:
            self.set_controls()
        if not previous or 'audio_output_device' in changed:
            app.setProperty('audioOutputDevice', str(self.settings.value('audio_output_device', '')))
            self.refresh_audio_output()
        dialog = getattr(self, 'settings_dialog', None)
        if dialog is not None and dialog.restoring and dialog.original_library_state is not None:
            root, selected = dialog.original_library_state
            if selected is not None:
                if self.current_folder != selected or self.files.filePath(self.tree.rootIndex()) != root:
                    self.select_folder(Path(root), selected)
            else:
                self.generation += 1
                for scanner in self.scanners:
                    if isinstance(scanner, Scanner):
                        scanner.requestInterruption()
                self.current_folder = None
                self.files.setRootPath(root)
                self.tree.setRootIndex(self.files.index(root))
                self.grid.clear()
                self.albums = []
                self.clear_case_cache()
                self.count_label.setText('No folder selected')
            return
        if self.first_run_needed:
            return
        folder = Path(str(self.settings.value('browser_root', self.current_folder or Path.home() / 'Music')))
        current_root = self.files.filePath(self.tree.rootIndex())
        if filesystem_path(folder).is_dir() and str(folder) != str(Path(current_root)):
            self.select_folder(folder, Path(str(self.settings.value('folder', folder))))

    def update_transport_icons(self):
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        for button, name, label in (
            (self.play, 'pause' if playing else 'play', 'Pause' if playing else 'Play'),
            (self.previous, 'previous', 'Previous'),
            (self.next, 'next', 'Next'),
            (self.settings_button, 'settings', 'Settings'),
            (self.refresh_button, 'refresh', 'Refresh'),
            (self.save_theme_button, 'save-theme', 'Save current theme'),
        ):
            button.setText('')
            app = QApplication.instance()
            color = (app.property('themeAccent') if button.property('themeRole') == 'highlight'
                     else app.property('themeBackgroundAccent')) or '#cfe10e'
            disabled = color
            button.setIcon(transport_icon(name, color, disabled))
            size = round(QApplication.instance().property('buttonIconSize') or 20)
            button.setIconSize(QSize(round(size * 1.5), size) if name == 'save-theme' else QSize(size, size))
            button.setAccessibleName(label)
            button.setToolTip(label)

    def save_current_theme(self):
        self.discard_prepared_settings()
        album = self.queue[self.queue_index][1] if 0 <= self.queue_index < len(self.queue) else self.viewed_album
        if album is None and self.grid.currentItem() is not None:
            album = self.albums[self.grid.currentItem().data(Qt.UserRole)]
        presets = saved_color_themes(self.settings)
        dialog = getattr(self, 'settings_dialog', None)
        if dialog is not None:
            presets = dialog.presets[:]
        preset = capture_color_theme(presets, album.title if album is not None else 'Custom colors')
        presets.append(preset)
        try:
            write_theme_files(self.settings, presets)
        except OSError as error:
            self.statusBar().showMessage(str(error))
            return
        if dialog is not None:
            dialog.presets.append(preset)
            with QSignalBlocker(dialog.saved_theme_choice):
                dialog.saved_theme_choice.addItem(preset['name'], preset['id'])
        app = QApplication.instance()
        background = QColor(app.property('themeBackground') or BUILDING_GRAY).darker(120).name()
        color = app.property('textColor') or '#ffffff'
        self.theme_toast.setStyleSheet(f'QLabel#themeSavedToast {{ background: {background}; color: {color}; padding: 10px 14px; border-radius: 8px; }}')
        self.theme_toast.setText(f'Theme Saved as "{preset["name"]}"')
        self.theme_toast.setFixedWidth(min(self.width() - 32, self.theme_toast.fontMetrics().horizontalAdvance(self.theme_toast.text()) + 36))
        self.theme_toast.adjustSize()
        self.position_theme_toast()
        self.theme_toast.show()
        self.theme_toast.raise_()
        self.theme_toast_timer.start(3000)

    def position_theme_toast(self):
        anchor = self.save_theme_button.mapTo(self, self.save_theme_button.rect().bottomRight())
        self.theme_toast.move(max(16, min(anchor.x() - self.theme_toast.width(), self.width() - self.theme_toast.width() - 16)),
                              min(anchor.y() + 6, self.height() - self.theme_toast.height() - 16))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'theme_toast') and self.theme_toast.isVisible():
            self.position_theme_toast()
        if hasattr(self, 'album_presentation'):
            self.album_presentation.arrange()
        if hasattr(self, 'back_action'):
            self.update_responsive_layout()

    def restore_sidebar_split(self):
        height = self.now_playing.height()
        available = self.browser_splitter.height() - self.browser_splitter.handleWidth()
        self.browser_splitter.setSizes([max(0, available - height), height])

    def update_responsive_layout(self, animate=True):
        frame = self.frameGeometry()
        compact = frame.width() * 3 <= frame.height() * 2
        if compact != self.compact_mode:
            self.compact_mode = compact
            self.now_playing.set_resizable(compact or self.is_android)
            self.browser_splitter.setHandleWidth(8 if compact and not self.is_android else 0)
            self.browser_splitter.setCollapsible(1, compact and not self.is_android)
            self.library_layout.setContentsMargins(0 if compact else 16, 0, 0, 0)
            self.place_album_header()
            if compact and self.viewed_album is not None:
                self.workspace.set_page('library', animate=False)
            if compact:
                height = self.browser_splitter.height()
                self.browser_splitter.setSizes([round(height * .4), round(height * .6)])
        self.workspace.set_compact(compact, animate)
        self.transport.set_mix(self.workspace.mode_mix)
        self.update_compact_navigation()

    def place_album_header(self):
        if not self.is_android:
            return
        height = self.album_header.minimumHeight()
        left = self.library_layout.contentsMargins().left()
        self.album_header.setGeometry(left, 0, max(0, self.library_area.width() - left), height)
        self.album_content.setContentsMargins(0, height + self.library_layout.spacing(), 0, 0)

    def now_playing_limits(self):
        panel = self.now_playing
        minimum = max(MINIMUM_TOUCH_TARGET, panel.content.layout().sizeHint().height() - panel.cover.height())
        return minimum, min(panel.maximumHeight(), self.browser_splitter.height() - self.tree.minimumHeight())

    def set_now_playing_height(self, height):
        minimum, maximum = self.now_playing_limits()
        height = max(minimum, min(maximum, height))
        self.browser_splitter.setSizes([self.browser_splitter.height() - height, height])

    def drag_now_playing(self, delta):
        self.split_animation.stop()
        self.cover.resizing = True
        self.pending_split_drag += delta
        if not self.split_drag_timer.isActive():
            self.split_drag_timer.start()

    def apply_now_playing_drag(self):
        self.split_drag_timer.stop()
        distance, self.pending_split_drag = self.pending_split_drag, 0.0
        self.set_now_playing_height(self.now_playing.height() - round(distance))

    def finish_now_playing_resize(self):
        self.cover.resizing = False
        self.cover.update()

    def settle_now_playing(self, velocity):
        self.apply_now_playing_drag()
        if abs(velocity) < NOW_PLAYING_FLICK_SPEED:
            self.finish_now_playing_resize()
            return
        minimum, maximum = self.now_playing_limits()
        self.split_animation.stop()
        self.split_animation.setStartValue(float(self.now_playing.height()))
        self.split_animation.setEndValue(float(maximum if velocity < 0 else minimum))
        self.split_animation.start()

    def pinch_albums(self, scale, started):
        if started:
            self.pinch_scale = self.album_size.value()
            self.album_size.setSliderDown(True)
        self.album_size.setValue(round(self.pinch_scale * scale))

    def finish_album_pinch(self):
        self.album_size.setSliderDown(False)
        self.apply_album_size()

    def update_compact_navigation(self):
        library = self.compact_mode and self.workspace.page == 'library'
        self.transport.setVisible(self.is_android or not library)
        self.back_button.setVisible(library and not self.is_android)
        self.back_action.setEnabled(library)
        self.escape_action.setEnabled(library or (not self.compact_mode and self.viewed_album is not None))
        self.back_button.setAccessibleName('Back to albums' if self.viewed_album is not None else 'Back to file browser')

    def navigate_back(self):
        if self.viewed_album is not None and (not self.compact_mode or self.workspace.page == 'library'):
            self.show_albums()
        elif self.compact_mode and self.workspace.page == 'library':
            self.show_compact_browser()

    def show_compact_browser(self):
        if not self.compact_mode:
            return
        self.workspace.set_page('browser')
        self.update_compact_navigation()
        self.tree.setFocus()

    def show_compact_library(self):
        if self.compact_mode:
            self.workspace.set_page('library')
            self.update_compact_navigation()

    def open_compact_folder(self, index):
        if self.compact_mode and index.isValid():
            self.show_albums()
            self.show_compact_library()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Resize and watched is self.library_area:
            self.place_album_header()
        if kind == QEvent.KeyPress and isinstance(watched, QWidget) and watched.window() is self:
            key = event.key()
            navigation = (Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                          Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Return, Qt.Key_Enter)
            item_view = watched in (self.tree, self.grid, self.album_table)
            if (key in navigation or (key == Qt.Key_Space and event.modifiers() != Qt.NoModifier)
                    or (item_view and key not in (Qt.Key_Space, Qt.Key_Escape, Qt.Key_Back))):
                event.accept()
                return True
        if kind in (QEvent.Wheel, QEvent.MouseButtonPress, QEvent.KeyPress):
            self.cancel_browsing_restore()
        return super().eventFilter(watched, event)

    def update_button_sizes(self):
        scale = button_scale()
        # Initial stylesheet polish can restore the constructor's minimum size.
        # Finish it before applying the user's fixed transport dimensions.
        for widget in self.findChildren(QWidget):
            if isinstance(widget, (QPushButton, ThemedComboBox)):
                widget.ensurePolished()
                widget.updateGeometry()
        for button, base in ((self.play, 44), (self.previous, 32), (self.next, 32)):
            base = max(base, MINIMUM_TOUCH_TARGET - 2 * CONTROL_HEADROOM) if self.is_android else base
            button.setFixedHeight(round(base * scale) + 2 * CONTROL_HEADROOM + 2 * BUTTON_SHADOW)
        for button, width in ((self.save_theme_button, 64), (self.refresh_button, 44), (self.settings_button, 44)):
            button.setFixedWidth(round(width * scale) + 2 * CONTROL_HEADROOM)
        self.album_scale_control.setMinimumWidth(self.album_scale_control.minimumSizeHint().width())
        self.sort_albums.setFixedHeight(self.sort_albums.sizeHint().height())
        self.album_header.refresh()
        self.place_album_header()
        self.transport.arrange()
        self.album_presentation.arrange()

    def refresh_audio_output(self):
        if self.closing or self.playback_shutdown:
            return
        device = selected_output()
        if device != self.audio.device():
            # Keep the player, track position, volume and paused/playing state.
            self.audio.setDevice(device)

    def choose_folder(self):
        folder = choose_music_directory(self, 'Choose music library root', self.current_folder or music_directory())
        if folder:
            self.select_folder(Path(folder))

    def poll_optical_discs(self):
        if self.closing or self.disc_monitor is not None or self.pending_eject is not None:
            return
        monitor = DiscMonitor(self)
        self.disc_monitor = monitor
        self.scanners.add(monitor)
        monitor.result.connect(self.update_optical_discs)
        def finished():
            self.disc_monitor = None
            self.scanner_finished(monitor)
        monitor.finished.connect(finished)
        monitor.start()

    def update_optical_discs(self, discs):
        if self.closing or self.pending_eject is not None:
            return
        incoming = {str(Path(disc.root)): disc for disc in discs}
        if incoming == self.optical_discs:
            return
        previous = self.optical_discs
        self.optical_discs = incoming
        current = str(self.current_folder) if self.current_folder else ''
        # Keep the outgoing row's icon/text until it has slid behind the clip.
        # Disable its actions immediately, since the media is already gone.
        self.disc_list.setEnabled(bool(incoming))
        if incoming:
            with QSignalBlocker(self.disc_list):
                self.disc_list.clear()
                for root, disc in incoming.items():
                    drive = Path(root).drive
                    item = QListWidgetItem('Disc Drive' + (f' ({drive})' if drive else ''))
                    item.setData(Qt.UserRole, root)
                    item.setToolTip(disc.title)
                    self.disc_list.addItem(item)
                    if root == current:
                        self.disc_list.setCurrentItem(item)
            self.disc_list.sync_buttons()
        row_height = self.disc_list.sizeHintForRow(0) if incoming else 0
        self.disc_panel.reveal(min(3, len(incoming)) * row_height + 10 if incoming else 0)
        if self.queue and 0 <= self.queue_index < len(self.queue):
            track = self.queue[self.queue_index][0]
            disc = incoming.get(str(Path(track.cd_source))) if track.cd_source else None
            data_root = next((root for root in previous if track.path.is_relative_to(Path(root))), None)
            audio_removed = track.cd_source and (disc is None or disc.identity != track.cd_disc_id)
            data_removed = data_root and previous.get(data_root) != incoming.get(data_root)
            if audio_removed or data_removed:
                self.cd_request += 1
                self.cd_loading = False
                for worker in self.scanners:
                    if isinstance(worker, DiscReader):
                        worker.requestInterruption()
                self.player.stop()
                self.player.setSource(QUrl())
                self.queue = []
                self.queue_index = -1
                self.track_title.setText('')
                self.setWindowTitle(APP_NAME)
                self.update_now_playing_cover()
                self.set_controls()
                self.theme_from_now_playing()
                self.statusBar().showMessage('The CD was removed or changed.')
        if current in previous and previous.get(current) != incoming.get(current):
            if current in incoming:
                self.scan(Path(current))
            else:
                folder = Path(str(self.settings.value('folder', self.settings.value('browser_root', Path.home() / 'Music'))))
                self.scan(folder)

    def finish_disc_animation(self):
        if not self.optical_discs and self.disc_panel.height() == 0:
            with QSignalBlocker(self.disc_list):
                self.disc_list.clear()
            self.disc_list.sync_buttons()

    def select_optical_disc(self, current, previous=None):
        if current is not None:
            with QSignalBlocker(self.tree.selectionModel()):
                self.tree.clearSelection()
            self.scan(Path(current.data(Qt.UserRole)))

    def eject_optical_disc(self, root):
        if root not in self.optical_discs or self.pending_eject is not None:
            return
        self.player.pause()
        position = self.player.position()
        index = self.queue_index
        track = self.queue[index][0] if 0 <= index < len(self.queue) else None
        from_disc = track is not None and (str(Path(track.cd_source)) == root if track.cd_source
                                           else track.path.is_relative_to(Path(root)))
        self.pending_eject = root
        self.cd_request += 1
        self.cd_loading = False
        if from_disc:
            self.player.setSource(QUrl())  # Release a data CD's open audio file.
        button = self.disc_list.buttons.get(root)
        if button is not None:
            button.setEnabled(False)
        def uses_drive(worker):
            return (isinstance(worker, DiscMonitor)
                    or isinstance(worker, DiscReader) and str(Path(worker.track.cd_source)) == root
                    or isinstance(worker, Scanner) and worker.folder.is_relative_to(Path(root)))
        readers = [worker for worker in self.scanners if uses_drive(worker)]
        for worker in readers:
            worker.requestInterruption()
        self.statusBar().showMessage('Pausing and releasing Disc Drive...', 0)
        def begin_eject():
            if self.closing or self.pending_eject != root:
                return
            if any(worker.isRunning() for worker in self.scanners if uses_drive(worker)):
                QTimer.singleShot(40, begin_eject)
                return
            worker = DiscEjector(root, self)
            self.disc_ejector = worker
            self.scanners.add(worker)
            def result(ok, message):
                self.pending_eject = None
                if self.closing:
                    return
                if ok:
                    self.update_optical_discs([disc for drive, disc in self.optical_discs.items() if drive != root])
                    self.statusBar().showMessage('Disc ejected.', 5000)
                else:
                    if button is not None:
                        button.setEnabled(True)
                    if from_disc and self.queue_index == index:
                        self.play_index(index, autoplay=False, position=position)
                    self.statusBar().showMessage('Could not eject disc: ' + message)
            worker.result.connect(result)
            def finished():
                self.disc_ejector = None
                self.scanner_finished(worker)
            worker.finished.connect(finished)
            worker.start()
        QTimer.singleShot(100, begin_eject)

    def select_folder(self, folder, selected=None):
        folder = Path(folder).resolve()
        selected = Path(selected).resolve() if selected is not None else folder
        if not filesystem_path(selected).is_dir() or not selected.is_relative_to(folder):
            selected = folder
        # Only choosing a library changes the root; browsing children keeps it.
        with QSignalBlocker(self.tree.selectionModel()):
            root_index = self.files.setRootPath(str(folder))
            self.tree.setRootIndex(root_index)
            index = self.files.index(str(selected))
            ancestor = index.parent()
            while ancestor.isValid() and ancestor != root_index:
                self.tree.expand(ancestor)
                ancestor = ancestor.parent()
            self.tree.setCurrentIndex(index)
            self.tree.scrollTo(index)
        self.settings.setValue('browser_root', str(folder))
        self.scan(selected)
        self.schedule_browsing_restore()

    def show_folder_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid() or self.is_android:
            return
        folder = Path(self.files.filePath(index))
        if not filesystem_path(folder).is_dir():
            return
        self.folder_menu_path = folder
        self.folder_menu.popup(self.tree.viewport().mapToGlobal(position))

    def open_in_file_manager(self, folder, selected_file=None):
        if folder is None:
            return
        try:
            if not filesystem_path(folder).is_dir():
                raise OSError('The folder is no longer available.')
            if sys.platform == 'win32':
                path = filesystem_path(folder) if any(part.endswith(('.', ' ')) for part in folder.parts) else folder
                if selected_file is not None and filesystem_path(selected_file).is_file():
                    # A plain string keeps Explorer's unusual /select,"path" quoting intact.
                    subprocess.Popen(f'explorer.exe /select,"{selected_file}"')
                else:
                    subprocess.Popen(['explorer.exe', str(path)])
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                raise OSError('Could not open the file manager.')
        except OSError as error:
            self.statusBar().showMessage(f'Unable to open folder: {error}')

    def folder_selected(self, current, previous):
        if self.first_run_needed:
            return
        path = self.files.filePath(current)
        if path:
            with QSignalBlocker(self.disc_list):
                self.disc_list.clearSelection()
                self.disc_list.setCurrentItem(None)
            self.scan(Path(path))

    def scan(self, folder):
        self.show_albums()
        self.current_folder = Path(folder)
        if str(Path(folder)) not in self.optical_discs:
            self.settings.setValue('folder', str(folder))
            with QSignalBlocker(self.disc_list):
                self.disc_list.clearSelection()
                self.disc_list.setCurrentItem(None)
        self.generation += 1
        generation = self.generation
        for scanner in self.scanners:
            if isinstance(scanner, Scanner) and scanner is not self.resume_scanner:
                scanner.requestInterruption()
        self.grid.clear()
        self.clear_case_cache()
        self.case_prefetch_rows.clear()
        self.case_prefetch_timer.stop()
        self.albums = []
        self.count_label.setText('Scanning folders…')
        self.set_controls()
        scanner = Scanner(folder, self)
        scanner.result.connect(lambda albums, skipped: self.scan_complete(generation, albums, skipped))
        scanner.progress.connect(lambda count: self.scan_progress(generation, count))
        scanner.failed.connect(lambda message: self.scan_failed(generation, message))
        scanner.finished.connect(lambda: self.scanner_finished(scanner))
        self.scanners.add(scanner)
        scanner.start()

    def scan_progress(self, generation, count):
        if generation == self.generation:
            self.count_label.setText(f'Scanning… {count} album folders found')

    def scan_failed(self, generation, message):
        if generation == self.generation:
            self.count_label.setText(f'Unable to scan: {message}')

    def scanner_finished(self, scanner):
        self.scanners.discard(scanner)
        if scanner is self.resume_scanner:
            self.resume_scanner = None
        scanner.deleteLater()
        if self.closing and not self.scanners:
            self.close()

    def scan_complete(self, generation, albums, skipped):
        if generation != self.generation or self.closing:
            return
        self.albums = albums
        self.apply_album_sort()
        self.schedule_icon_prefetch()
        self.count_label.setText(f'{len(albums)} albums' if albums else 'No music found.')
        self.set_controls()
        if self.queue_index >= 0:
            queued_folder = self.queue[self.queue_index][1].folder
            for index, album in enumerate(albums):
                if album.folder == queued_folder:
                    self.grid.setCurrentRow(index)
                    break
        self.schedule_browsing_restore()
        if skipped:
            self.statusBar().showMessage(f'{len(skipped)} inaccessible folders skipped. {skipped[0]}')
        else:
            self.statusBar().clearMessage()

    def clear_case_cache(self, sources=True):
        self.case_icon_cache.clear()
        self.case_cache_bytes['icons'] = 0
        if sources:
            self.case_source_cache.clear()
            self.case_cache_bytes['sources'] = 0
        self.case_prefetch_signature = None

    def cache_case_pixmap(self, cache, kind, index, pixmap):
        cache[index] = pixmap
        self.case_cache_bytes[kind] += pixmap.width() * pixmap.height() * pixmap.depth() // 8
        while len(cache) > 1 and self.case_cache_bytes[kind] > 48 * 1024 * 1024:
            _, removed = cache.popitem(last=False)
            self.case_cache_bytes[kind] -= removed.width() * removed.height() * removed.depth() // 8

    def album_icon(self, row):
        item = self.grid.item(row)
        if item is None:
            return self.case_placeholder
        index = item.data(Qt.UserRole)
        icon = self.case_icon_cache.get(index)
        if icon is None:
            source = self.case_source_cache.get(index)
            if source is None:
                album = self.albums[index]
                source = cd_case_pixmap(album.thumbnail or album.artwork, album.title,
                    handwriting_font=self.artist_handwriting(album.folder.parent), case_key=str(album.folder),
                    tray_color=artwork_tray_color(
                        album.thumbnail if self.is_android and album.thumbnail else album.artwork) or '')
                self.cache_case_pixmap(self.case_source_cache, 'sources', index, source)
            self.case_source_cache.move_to_end(index)
            ratio = self.grid.devicePixelRatioF()
            size = self.grid.iconSize()
            icon = source.scaled(round(size.width() * ratio), round(size.height() * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon.setDevicePixelRatio(ratio)
            self.cache_case_pixmap(self.case_icon_cache, 'icons', index, icon)
        self.case_icon_cache.move_to_end(index)
        return icon

    def schedule_icon_prefetch(self, *args):
        if not self.grid.count() or not self.grid.isVisible():
            return
        columns = self.grid.layout_columns
        pitch = max(1, self.grid.row_pitch())
        first_row = max(0, self.grid.verticalScrollBar().value() // pitch - 1)
        rows = self.grid.viewport().height() // pitch + 4
        signature = (first_row, rows, columns, self.grid.count(), self.grid.iconSize().width())
        if signature == self.case_prefetch_signature:
            return
        self.case_prefetch_signature = signature
        self.case_prefetch_rows = deque(range(first_row * columns, min(self.grid.count(), (first_row + rows) * columns)))
        if not self.case_prefetch_timer.isActive():
            self.case_prefetch_timer.start(8)

    def prefetch_album_icon(self):
        if self.closing or not self.grid.isVisible():
            self.case_prefetch_rows.clear()
            return
        if self.is_android and QScroller.scroller(self.grid.viewport()).state() != QScroller.Inactive:
            self.case_prefetch_timer.start(120)  # Keep the finger's frames free.
            return
        while self.case_prefetch_rows:
            row = self.case_prefetch_rows.popleft()
            item = self.grid.item(row)
            if item is not None and item.data(Qt.UserRole) not in self.case_icon_cache:
                self.album_icon(row)
                break
        if self.case_prefetch_rows:
            self.case_prefetch_timer.start(8)
        elif self.is_android:
            self.theme_prepare_timer.start()

    def custom_order_key(self):
        identity = str(self.current_folder).replace('\\', '/').casefold()
        return 'album_custom_order/' + hashlib.sha256(identity.encode('utf-8')).hexdigest()

    def change_album_sort(self):
        if self.isVisible():
            self.cancel_browsing_restore()
        self.settings.setValue('album_sort', self.sort_albums.currentData())
        if self.current_folder is not None:
            self.apply_album_sort()
            self.set_controls()

    def change_album_size(self, percent):
        if self.isVisible():
            self.cancel_browsing_restore()
        self.settings.setValue('album_scale', percent)
        self.album_size.setToolTip(f'Album size: {percent}%')
        if self.album_size.isSliderDown():
            if not self.album_scale_timer.isActive():
                self.album_scale_timer.start()
        else:
            self.apply_album_size()

    def apply_album_size(self):
        self.album_scale_timer.stop()
        percent = self.album_size.value()
        if self.grid.iconSize().width() == round(328 * percent / 100):
            return
        self.clear_case_cache(sources=False)
        self.grid.set_album_scale(percent)
        self.schedule_icon_prefetch()

    def apply_album_sort(self):
        selected = self.grid.currentItem()
        selected_folder = self.albums[selected.data(Qt.UserRole)].folder if selected is not None else None
        mode = self.sort_albums.currentData()
        alphabetical = lambda album: (natural_key(album.title), natural_key(album.folder))
        if mode == 'custom':
            saved = self.settings.value(self.custom_order_key(), [])
            if isinstance(saved, str):
                saved = [saved]
            positions = {path: index for index, path in enumerate(saved)}
            key = lambda album: (positions.get(str(album.folder), len(positions)), alphabetical(album))
        elif mode in ('oldest', 'newest'):
            direction = 1 if mode == 'oldest' else -1
            key = lambda album: (not bool(album.release_date),
                direction * int(album.release_date.replace('-', '') or 0), alphabetical(album))
        else:
            key = alphabetical
        self.albums.sort(key=key)
        self.grid.clear()
        self.clear_case_cache()
        for index, album in enumerate(self.albums):
            item = QListWidgetItem(self.case_placeholder, '')
            item.setData(Qt.AccessibleTextRole, f'{album.title}, {album.artist}')
            item.setData(Qt.UserRole, index)
            self.grid.addItem(item)
            if album.folder == selected_folder:
                self.grid.setCurrentItem(item)
        self.grid.set_custom_order(mode == 'custom')
        if self.viewed_album is not None:
            self.grid.suppressed_album = next((index for index, album in enumerate(self.albums)
                                               if album.folder == self.viewed_album.folder), None)
            self.grid.viewport().update()

    def save_custom_order(self):
        paths = [str(self.albums[self.grid.item(row).data(Qt.UserRole)].folder)
                 for row in range(self.grid.count())]
        self.settings.setValue(self.custom_order_key(), paths)
        self.set_controls()

    def artist_handwriting(self, artist_folder):
        fonts = QApplication.instance().property('handwritingFonts') or []
        if not fonts:
            return QFont(QApplication.instance().property('handwritingFamily') or 'cursive')
        identity = str(Path(artist_folder).resolve()).replace('\\', '/').casefold()
        digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
        self.settings.beginGroup('artist_handwriting')
        try:
            saved = self.settings.value(digest)
            chosen = next((font for font in fonts if font['id'] == saved), None)
            if chosen is None:
                used = {self.settings.value(key) for key in self.settings.childKeys()}
                offset = int(digest[:8], 16) % len(fonts)
                choices = fonts[offset:] + fonts[:offset]
                chosen = next((font for font in choices if font['id'] not in used), choices[0])
                self.settings.setValue(digest, chosen['id'])
        finally:
            self.settings.endGroup()
        font = QFont(chosen['family'])
        font.setStyleName(chosen['style'])
        return font

    def show_albums(self, play_sound=True):
        if play_sound and self.viewed_album is not None:
            play_case_sound('close')
        self.stop_view_fade()
        self.grid.suppressed_album = None
        self.grid.viewport().update()
        self.album_page.hide()
        self.set_album_backdrop_opacity(1)
        self.library_pages.setCurrentIndex(0)
        self.viewed_album = None
        self.update_album_header_controls()
        self.grid.setFocus()

    def open_album(self, item):
        album = self.albums[item.data(Qt.UserRole)]
        self.show_album(album)

    def show_metadata_menu(self, album, track, position):
        if not hasattr(self, 'metadata_menu'):
            self.metadata_menu = ThemedMenu(self)
            self.metadata_menu.setObjectName('metadataContextMenu')
            self.metadata_action = self.metadata_menu.addAction('View metadata')
            self.metadata_action.triggered.connect(self.open_metadata_editor)
            if not self.is_android:
                self.metadata_folder_action = self.metadata_menu.addAction(FILE_MANAGER_LABEL)
                self.metadata_folder_action.triggered.connect(self.open_metadata_target_folder)
        self.metadata_target = album, track
        self.metadata_menu.popup(position)

    def open_metadata_target_folder(self):
        album, track = self.metadata_target
        if track is None:
            self.open_in_file_manager(album.folder)
        else:
            self.open_in_file_manager(Path(track.path).parent, track.path)

    def show_album_metadata_menu(self, position):
        item = self.grid.itemAt(position)
        if item is not None:
            self.show_metadata_menu(self.albums[item.data(Qt.UserRole)], None, self.grid.viewport().mapToGlobal(position))

    def show_track_metadata_menu(self, position):
        row = self.album_table.indexAt(position).row()
        if self.viewed_album is not None and 0 <= row < len(self.viewed_album.tracks):
            self.show_metadata_menu(self.viewed_album, self.viewed_album.tracks[row], self.album_table.viewport().mapToGlobal(position))

    def show_playing_metadata_menu(self, position):
        if 0 <= self.queue_index < len(self.queue):
            self.show_metadata_menu(self.queue[self.queue_index][1], None, self.cover.mapToGlobal(position))

    def show_open_metadata_menu(self, position):
        if self.viewed_album is not None:
            self.show_metadata_menu(self.viewed_album, None, self.album_artwork.mapToGlobal(position))

    def open_metadata_editor(self):
        existing = getattr(self, 'metadata_dialog', None)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return
        album, track = self.metadata_target
        dialog = MetadataEditor(album, track, self)
        self.metadata_dialog = dialog
        dialog.saved.connect(self.refresh_metadata)
        dialog.saving.connect(self.prepare_metadata_save)
        dialog.saveFinished.connect(self.resume_metadata_playback)
        def finished(result):
            self.metadata_dialog = None
            dialog.deleteLater()
            if getattr(self, 'close_after_metadata', False):
                QTimer.singleShot(0, self.close)
        dialog.finished.connect(finished)
        dialog.show()

    def prepare_metadata_save(self, paths):
        self.metadata_playback = None
        if 0 <= self.queue_index < len(self.queue):
            track, album = self.queue[self.queue_index]
            if track.path in paths and not self.player.source().isEmpty():
                self.metadata_playback = track.path, self.player.position(), self.player.playbackState() == QMediaPlayer.PlayingState
                self.player.pause()
                self.player.setSource(QUrl())
                self.clear_playback_file()

    def resume_metadata_playback(self):
        state = getattr(self, 'metadata_playback', None)
        self.metadata_playback = None
        if state is not None and 0 <= self.queue_index < len(self.queue):
            path, position, playing = state
            if self.queue[self.queue_index][0].path == path:
                if getattr(self, 'close_after_metadata', False):
                    self.resume_position = position
                else:
                    self.play_index(self.queue_index, autoplay=False, position=position)
                    if playing:
                        if self.resume_position is not None:
                            self.resume_play_requested = True
                            self.apply_resume_position()
                        else:
                            self.player.play()

    def refresh_metadata(self, albums):
        refreshed = {album.folder: album for album in albums}
        targets = list(self.albums) + [album for track, album in self.queue]
        if self.viewed_album is not None:
            targets.append(self.viewed_album)
        seen = set()
        for album in targets:
            if id(album) in seen or album.folder not in refreshed:
                continue
            seen.add(id(album))
            updated = refreshed[album.folder]
            old_tracks = {track.path: track for track in album.tracks}
            tracks = []
            for track in updated.tracks:
                original = old_tracks.get(track.path, track)
                original.__dict__.update(track.__dict__)
                tracks.append(original)
            album.__dict__.update(updated.__dict__)
            album.tracks = tracks
        by_path = {track.path: track for album in albums for track in album.tracks}
        for track, album in self.queue:
            if track.path in by_path:
                track.__dict__.update(by_path[track.path].__dict__)
        if 0 <= self.queue_index < len(self.queue):
            current_track, current_album = self.queue[self.queue_index]
            if current_album.folder in refreshed:
                current_path = current_track.path
                self.queue = [(track, current_album) for track in current_album.tracks]
                self.queue_index = next(index for index, (track, album) in enumerate(self.queue) if track.path == current_path)
        scroll = self.grid.verticalScrollBar().value()
        self.apply_album_sort()
        self.grid.doItemsLayout()
        self.grid.verticalScrollBar().setValue(scroll)
        self.schedule_icon_prefetch()
        if self.viewed_album is not None and self.viewed_album.folder in refreshed:
            album = self.viewed_album
            self.populate_album_tracks(album)
            self.album_presentation.set_artwork(album.artwork, self.album_paper_colors(album.artwork))
            self.album_artwork.pixmap = cd_case_pixmap(album.artwork, album.title,
                handwriting_font=self.artist_handwriting(album.folder.parent), case_key=str(album.folder))
            self.album_artwork.update()
        if 0 <= self.queue_index < len(self.queue):
            track, album = self.queue[self.queue_index]
            self.track_title.setText(track.title)
            self.setWindowTitle(f'{APP_NAME} — {track.title}')
            self.update_now_playing_cover(album)
            self.theme_from_now_playing()
        self.set_controls()

    def open_now_playing_album(self):
        if 0 <= self.queue_index < len(self.queue):
            self.show_album(self.queue[self.queue_index][1])

    def update_album_header_controls(self):
        enabled = self.viewed_album is None
        for control in (self.album_scale_control, self.sort_albums, self.save_theme_button, self.refresh_button):
            control.setEnabled(enabled)
        if self.is_android:
            self.settings_button.setEnabled(enabled)
            self.album_header.raise_() if enabled else self.album_header.lower()
        self.tidy_button.setEnabled(enabled and not self.grid.tidying)
        if hasattr(self, 'escape_action'):
            self.update_compact_navigation()

    def set_album_backdrop_opacity(self, amount):
        self.library_opacity.setOpacity(amount)
        self.album_size.set_paint_opacity(amount)
        for opacity in self.album_header_opacities:
            opacity.setOpacity(amount)

    def stop_view_fade(self):
        fade = getattr(self, 'view_fade', None)
        if fade is not None:
            fade.stop()
            fade.deleteLater()
            self.view_fade = None

    def show_album(self, album, play_sound=True):
        self.show_compact_library()
        if play_sound and (self.viewed_album is None or self.viewed_album.folder != album.folder):
            play_case_sound('open')
        self.stop_view_fade()
        self.viewed_album = album
        self.update_album_header_controls()
        self.album_artwork.sheen_key = str(album.folder)
        self.album_presentation.set_album_title(album.title)
        self.album_presentation.set_artwork(album.artwork, self.album_paper_colors(album.artwork))
        self.grid.suppressed_album = next((index for index, entry in enumerate(self.albums)
                                           if entry.folder == album.folder), None)
        self.grid.viewport().update()
        self.populate_album_tracks(album)
        self.set_album_backdrop_opacity(.2)
        self.album_page.show()
        self.library_pages.setCurrentWidget(self.album_page)
        self.album_presentation.reveal(cd_case_pixmap(
            album.artwork, album.title, handwriting_font=self.artist_handwriting(album.folder.parent), case_key=str(album.folder)))
        self.album_table.setFocus()

    def populate_album_tracks(self, album):
        self.album_table.setRowCount(len(album.tracks))
        for row, track in enumerate(album.tracks):
            for column, value in enumerate([str(track.number or row + 1), track.title]):
                self.album_table.setItem(row, column, QTableWidgetItem(value))
        self.album_table.clearSelection()
        if self.queue_index >= 0 and self.queue[self.queue_index][1].folder == album.folder:
            self.album_table.selectRow(self.queue_index)
        self.update_track_markers()

    def play_album(self, album, index):
        self.queue = [(track, album) for track in album.tracks]
        self.play_index(index)

    def clear_playback_file(self):
        source = getattr(self, 'playback_file', None)
        if source is not None:
            self.playback_file = None
            source.close()
            source.deleteLater()

    def set_playback_source(self, path):
        if getattr(self, 'playback_file', None) is not None:
            self.player.setSource(QUrl())
            self.clear_playback_file()
        url = QUrl.fromLocalFile(str(path.resolve()))
        if os.name == 'nt' and any(part.endswith(('.', ' ')) for part in path.parts):
            try:
                descriptor = os.open(filesystem_path(path), os.O_RDONLY | os.O_BINARY)
            except OSError as error:
                self.playback_error(QMediaPlayer.ResourceError, str(error))
                return False
            source = QFile(self.player)
            if not source.open(descriptor, QIODevice.ReadOnly, QFile.AutoCloseHandle):
                os.close(descriptor)
                self.playback_error(QMediaPlayer.ResourceError, source.errorString())
                source.deleteLater()
                return False
            self.playback_file = source
            self.player.setSourceDevice(source, url)
        else:
            self.player.setSource(url)
        return True

    def play_index(self, index, autoplay=True, position=0):
        if not 0 <= index < len(self.queue):
            return
        self.queue_index = index
        self.cd_request += 1
        request = self.cd_request
        self.cd_loading = False
        for worker in self.scanners:
            if isinstance(worker, DiscReader):
                worker.requestInterruption()
        track, album = self.queue[index]
        if self.viewed_album and self.viewed_album.folder == album.folder:
            self.album_table.selectRow(index)
        self.track_title.setText(track.title)
        self.update_now_playing_cover(album)
        self.setWindowTitle(f'{APP_NAME} — {track.title}')
        self.resume_position = max(0, int(position)) or None
        self.resume_play_requested = False
        if track.cd_source and not cached_audio_valid(track):
            self.cd_loading = True
            self.player.stop()
            self.player.setSource(QUrl())
            reader = DiscReader(track, self)
            self.scanners.add(reader)
            def ready(path):
                if self.closing or request != self.cd_request:
                    return
                self.cd_loading = False
                if not self.set_playback_source(path):
                    return
                if autoplay:
                    self.player.play()
                self.set_controls()
                self.statusBar().clearMessage()
            def failed(message):
                if not self.closing and request == self.cd_request:
                    self.cd_loading = False
                    self.set_controls()
                    self.statusBar().showMessage(f'Unable to read the CD: {message}')
            reader.ready.connect(ready)
            reader.failed.connect(failed)
            reader.progress.connect(lambda value: self.statusBar().showMessage(f'Reading CD track {track.number}: {value}%', 0)
                                    if not self.closing and request == self.cd_request else None)
            reader.finished.connect(lambda: self.scanner_finished(reader))
            reader.start()
            self.set_controls()
            self.theme_from_now_playing()
            return
        if not self.set_playback_source(track.path):
            self.set_controls()
            return
        if autoplay:
            self.player.play()
        self.set_controls()
        self.theme_from_now_playing()

    def restore_last_session(self):
        track_path = Path(str(self.settings.value('session/track', '')))
        album_folder = Path(str(self.settings.value('session/album', '')))
        if self.queue or not filesystem_path(track_path).is_file() or not filesystem_path(album_folder).is_dir():
            return
        position = max(0, int(self.settings.value('session/position', 0)))
        scanner = Scanner(album_folder, self)
        self.resume_scanner = scanner

        def restore(albums, skipped):
            if self.closing or self.queue:
                return
            for album in albums:
                for index, track in enumerate(album.tracks):
                    if track.path.resolve() == track_path.resolve():
                        self.queue = [(entry, album) for entry in album.tracks]
                        self.show_album(album, play_sound=False)
                        # Restore the resumed album's final palette immediately;
                        # fades are reserved for later album changes.
                        colors = self.saved_theme_colors()
                        artwork = (self.cached_theme_colors(album.artwork, str(self.settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT)))
                                   if self.settings.value('artwork_theme_enabled', ARTWORK_THEME_DEFAULT, type=bool) else None)
                        colors.update(artwork or {})
                        self.set_theme(str(self.settings.value('theme', THEME_DEFAULT)), colors, bool(artwork))
                        self.play_index(index, autoplay=False, position=position)
                        for row, visible in enumerate(self.albums):
                            if visible.folder == album.folder:
                                self.grid.setCurrentRow(row)
                                break
                        self.schedule_browsing_restore()
                        return

        scanner.result.connect(restore)
        scanner.finished.connect(lambda: self.scanner_finished(scanner))
        self.scanners.add(scanner)
        scanner.start()

    def apply_resume_position(self):
        if (self.resume_position is None or not self.player.isSeekable() or self.player.duration() <= 0
                or self.player.mediaStatus() not in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia,
                                                     QMediaPlayer.BufferingMedia)):
            return
        if not self.resume_seek_scheduled:
            self.resume_seek_scheduled = True
            QTimer.singleShot(0, self.finish_resume_seek)

    def finish_resume_seek(self):
        self.resume_seek_scheduled = False
        if self.resume_position is None or not self.player.isSeekable() or self.player.duration() <= 0:
            return
        position = min(self.resume_position, self.player.duration() - 1)
        self.resume_position = None
        self.player.setPosition(position)
        self.seek.setValue(position)
        if self.resume_play_requested:
            self.resume_play_requested = False
            self.player.play()

    def save_session(self):
        if 0 <= self.queue_index < len(self.queue):
            track, album = self.queue[self.queue_index]
            self.settings.setValue('session/track', str(track.path.resolve()))
            self.settings.setValue('session/album', str(album.folder.resolve()))
            self.settings.setValue('session/position', self.resume_position if self.resume_position is not None else self.player.position())

    def save_browsing_state(self):
        expanded = []
        pending = [self.tree.rootIndex()]
        while pending:
            parent = pending.pop()
            for row in range(self.files.rowCount(parent)):
                index = self.files.index(row, 0, parent)
                if self.tree.isExpanded(index):
                    expanded.append(self.files.filePath(index))
                    pending.append(index)
        item = self.grid.currentItem()
        selected_album = str(self.albums[item.data(Qt.UserRole)].folder) if item is not None else ''
        state = dict(root=self.files.filePath(self.tree.rootIndex()), folder=str(self.current_folder or ''),
                     expanded=expanded, browser_scroll=self.tree.verticalScrollBar().value(),
                     browser_horizontal=self.tree.horizontalScrollBar().value(), album=selected_album,
                     album_scroll=self.grid.verticalScrollBar().value())
        self.settings.setValue('browsing_state', json.dumps(state))

    def schedule_browsing_restore(self, *args):
        if self.browsing_restore_attempts < 100 and not self.closing:
            self.browsing_restore_timer.start()

    def cancel_browsing_restore(self, *args):
        self.browsing_restore_attempts = 100
        self.browsing_restore_timer.stop()

    def restore_browsing_state(self):
        ready = self.resume_scanner is None and not any(isinstance(scanner, Scanner) for scanner in self.scanners)
        if ready:
            self.browsing_restore_attempts += 1
        state = self.browsing_state
        root = self.files.filePath(self.tree.rootIndex())
        matches = state.get('root') == root and state.get('folder') == str(self.current_folder)
        if matches:
            for path in state.get('expanded', []):
                index = self.files.index(path)
                if index.isValid():
                    self.tree.expand(index)
            selected = self.files.index(state['folder'])
            if selected.isValid():
                with QSignalBlocker(self.tree.selectionModel()):
                    self.tree.setCurrentIndex(selected)
            self.tree.doItemsLayout()
            self.tree.verticalScrollBar().setValue(int(state.get('browser_scroll', 0)))
            self.tree.horizontalScrollBar().setValue(int(state.get('browser_horizontal', 0)))
        elif self.current_folder is not None:
            self.tree.scrollTo(self.files.index(str(self.current_folder)))
        if ready:
            album = state.get('album', '') if matches else str(self.queue[self.queue_index][1].folder) if self.queue_index >= 0 else ''
            if matches or album:
                self.grid.doItemsLayout()
                self.grid.finish_reflow()
            for row in range(self.grid.count()):
                if str(self.albums[self.grid.item(row).data(Qt.UserRole)].folder) == album:
                    self.grid.setCurrentRow(row)
                    if not matches:
                        self.grid.scrollToItem(self.grid.item(row))
                    break
            if matches:
                self.grid.verticalScrollBar().setValue(int(state.get('album_scroll', 0)))
        signature = (self.tree.verticalScrollBar().maximum(), self.grid.verticalScrollBar().maximum(), self.grid.count())
        self.browsing_restore_stable = self.browsing_restore_stable + 1 if signature == self.browsing_restore_signature else 0
        self.browsing_restore_signature = signature
        settled = (not matches or (self.tree.verticalScrollBar().maximum() >= int(state.get('browser_scroll', 0))
                                  and self.grid.verticalScrollBar().maximum() >= int(state.get('album_scroll', 0))))
        if ready and settled and self.browsing_restore_stable >= 3:
            self.cancel_browsing_restore()
            return
        if self.browsing_restore_attempts < 100:
            self.browsing_restore_timer.start(30 if ready else 100)

    def set_controls(self):
        self.play.setEnabled(bool(self.queue) and not self.cd_loading)
        self.previous.setEnabled(bool(self.queue))
        self.next.setEnabled(self.queue_index + 1 < len(self.queue) or self.next_album() is not None)
        self.update_track_markers()
        if getattr(self, 'taskbar', None):
            self.taskbar.update()

    def update_track_markers(self):
        playing_row = -1
        if (self.viewed_album is not None and self.queue_index >= 0
                and self.player.playbackState() == QMediaPlayer.PlayingState
                and self.queue[self.queue_index][1].folder == self.viewed_album.folder):
            playing_row = self.queue_index
        for row in range(self.album_table.rowCount()):
            item = self.album_table.item(row, 0)
            if item is not None:
                item.setData(PLAYING_ROLE, row == playing_row)
                item.setData(Qt.AccessibleDescriptionRole, 'Playing' if row == playing_row else '')

    def toggle_play(self):
        if not self.queue or self.cd_loading:
            return
        if self.player.source().isEmpty() and self.queue[self.queue_index][0].cd_source:
            self.play_index(self.queue_index)
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if self.resume_position is not None:
                self.resume_play_requested = True
                self.apply_resume_position()
            else:
                self.player.play()

    def previous_track(self):
        if self.player.position() > 3000 or self.queue_index == 0:
            self.player.setPosition(0)
        else:
            self.play_index(self.queue_index - 1)

    def next_track(self):
        if self.queue_index + 1 < len(self.queue):
            self.play_index(self.queue_index + 1)
        else:
            album = self.next_album()
            if album is not None:
                self.show_album(album)
                self.play_album(album, 0)

    def next_album(self):
        if not self.queue or not self.settings.value('continuous_playback', True, type=bool):
            return None
        current = self.queue[self.queue_index][1].folder
        ordered = [self.albums[self.grid.item(row).data(Qt.UserRole)] for row in range(self.grid.count())]
        index = next((i for i, album in enumerate(ordered) if album.folder == current), -1)
        return next((album for album in ordered[index + 1:] if album.tracks), None) if index >= 0 else None

    def media_status_changed(self, status):
        self.apply_resume_position()
        if status == QMediaPlayer.EndOfMedia:
            if not self.queue:
                return
            if self.queue_index + 1 < len(self.queue):
                self.next_track()
            elif self.next_album() is not None:
                self.next_track()
            else:
                self.finish_playback()

    def finish_playback(self):
        if not self.queue:
            return
        opacity = self.library_opacity.opacity()
        self.cd_request += 1
        self.cd_loading = False
        for worker in self.scanners:
            if isinstance(worker, DiscReader):
                worker.requestInterruption()
        self.player.stop()
        self.player.setSource(QUrl())
        self.queue = []
        self.queue_index = -1
        self.resume_position = None
        self.resume_play_requested = False
        for key in ('track', 'album', 'position'):
            self.settings.remove('session/' + key)
        self.track_title.setText('')
        self.setWindowTitle(APP_NAME)
        self.update_now_playing_cover()
        self.show_albums(play_sound=False)
        play_case_sound('close')
        self.set_controls()
        self.theme_from_now_playing()
        duration = round(self.theme_fade_seconds() * 1000)
        if duration and opacity < 1:
            self.set_album_backdrop_opacity(opacity)
            self.view_fade = QVariantAnimation(self)
            self.view_fade.setDuration(duration)
            self.view_fade.setStartValue(opacity)
            self.view_fade.setEndValue(1.0)
            self.view_fade.valueChanged.connect(self.set_album_backdrop_opacity)
            self.view_fade.finished.connect(self.stop_view_fade)
            self.view_fade.start()

    def playback_changed(self, state):
        self.update_transport_icons()
        self.update_track_markers()
        if getattr(self, 'taskbar', None):
            self.taskbar.update()

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)

    def duration_changed(self, duration):
        self.seek.setRange(0, duration)
        self.seek.setEnabled(duration > 0 and self.player.isSeekable())
        self.apply_resume_position()

    def playback_error(self, error, message):
        logging.error('Playback error %s for %s: %s', error.name, self.player.source().toDisplayString(), message)
        if error == QMediaPlayer.FormatError and self.player.playbackState() == QMediaPlayer.PlayingState and self.player.position() > 0:
            # A damaged frame is skipped and playback carries on, so stay quiet unless it really stalls.
            source, position = self.player.source(), self.player.position()
            QTimer.singleShot(PLAYBACK_STALL_MS, lambda: self.report_playback_stall(source, position, message))
            return
        self.statusBar().showMessage(f'Playback error: {message}')

    def report_playback_stall(self, source, position, message):
        if (not self.closing and self.player.source() == source and self.player.position() == position
                and self.player.playbackState() == QMediaPlayer.PlayingState):
            self.statusBar().showMessage(f'Playback error: {message}')

    def shutdown_playback(self):
        if self.playback_shutdown:
            return
        self.playback_shutdown = True
        self.player.stop()
        self.player.setSource(QUrl())
        self.clear_playback_file()
        self.player.setAudioOutput(None)

    def closeEvent(self, event):
        metadata = getattr(self, 'metadata_dialog', None)
        if metadata is not None:
            if metadata.job is not None and metadata.job.isRunning():
                self.close_after_metadata = True
                metadata.close()
                event.ignore()
                return
            metadata.close()
        self.browsing_restore_timer.stop()
        self.album_scale_timer.stop()
        self.case_prefetch_timer.stop()
        self.theme_prepare_timer.stop()
        self.settings_prepare_timer.stop()
        self.discard_prepared_settings()
        if self.theme_preparer is not None:
            self.theme_preparer.requestInterruption()
            self.theme_preparer.wait()
        self.pending_eject = None
        if getattr(self, 'settings_dialog', None) is not None:
            self.settings_dialog.accept()
        self.stop_view_fade()
        self.disc_timer.stop()
        self.cd_request += 1
        if getattr(self, 'taskbar', None):
            self.taskbar.close()
        if not self.closing:
            save_session_palette(self.settings)
        self.clear_theme_fade()
        if not self.closing:
            self.settings.setValue('window_geometry', self.saveGeometry())
            self.settings.setValue('sidebar_width', self.workspace.sidebar_width)
            self.save_browsing_state()
            self.save_session()
        self.settings.setValue('volume', self.volume.value())
        self.shutdown_playback()
        if self.scanners:
            self.closing = True
            for scanner in self.scanners:
                scanner.requestInterruption()
            event.ignore()
            self.hide()
        else:
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    if running_on_android():
        # Packaged image plugins stay beside PySide6 instead of the app's native libraries.
        import PySide6
        QApplication.addLibraryPath(str(Path(PySide6.__file__).parent / 'Qt' / 'plugins' / 'imageformats'))
    from app_identity import configure_app
    configure_app(app)
    from runtime_errors import install_error_log
    install_error_log(app)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    if '--install-desktop-entry' in sys.argv:
        from app_identity import install_desktop_entry
        install_desktop_entry()
        sys.exit(0)
    elif '--smoke-test' in sys.argv:
        from packaging_smoke import run_smoke
        sys.exit(run_smoke(app, PlayerWindow))
    else:
        window = PlayerWindow()
        window.show()
        QTimer.singleShot(0, window.show_first_run_setup)
        sys.exit(app.exec())
