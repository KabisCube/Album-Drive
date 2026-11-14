"""Folder-name search for the file browser: an expanding search bar, a background folder index and match filtering."""

import math
import os

from PySide6.QtCore import QDir, QObject, QPersistentModelIndex, QEasingCurve, QElapsedTimer, QPointF, QRectF, QThread, QTimer, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPalette, QPen, QRegion
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from button_sounds import play_button_sound
from themes import BUTTON_SHADOW, CONTROL_HEADROOM, button_paint_rect, control_face, button_scale, paint_control

SEARCH_FACE_HEIGHT = 28
SEARCH_DELAY_MS = 220
SEARCH_MATCH_LIMIT = 400
WIGGLE_WIDTH = 22


def browser_path(path):
    return QDir.fromNativeSeparators(os.path.normpath(str(path)))


class FolderIndexer(QThread):
    ready = Signal(str, object)

    def __init__(self, root, parent):
        super().__init__(parent)
        self.root = root

    def run(self):
        found = []
        pending = [self.root]
        while pending:
            if self.isInterruptionRequested():
                return
            directory = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir():
                                found.append(entry.path)
                                pending.append(entry.path)
                        except OSError:
                            continue
            except OSError:
                continue
        self.ready.emit(self.root, [browser_path(path) for path in found])


def search_matches(paths, query, limit=SEARCH_MATCH_LIMIT):
    needle = query.casefold().strip()
    if not needle:
        return []
    matches = []
    for path in paths:
        if needle in path.rsplit('/', 1)[-1].casefold():
            matches.append(path)
            if len(matches) >= limit:
                break
    return matches


def wiggle_path(left, center_y, width, phase):
    path = QPainterPath()
    steps = 24
    for step in range(steps + 1):
        amount = step / steps
        point = QPointF(left + width * amount, center_y + 2.4 * math.sin(amount * 12.566 + phase))
        path.moveTo(point) if step == 0 else path.lineTo(point)
    return path


class FolderSearchBar(QWidget):
    """A search button in the browser's top-left corner that unrolls rightward into a search field."""

    queryChanged = Signal(str)
    expandedChanged = Signal(bool)
    progressChanged = Signal(float)

    def __init__(self, parent, icon_factory):
        super().__init__(parent)
        self.icon_factory = icon_factory
        self.setProperty('centerFlatFace', True)
        self.progress = 0.0
        self.expanded = False
        self.pressed_part = None
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.set_progress)
        self.animation.finished.connect(self.finish)
        self.field = QLineEdit(self)
        self.field.setObjectName('folderSearchField')
        self.field.setPlaceholderText('Search')
        self.field.setAccessibleName('Search folders')
        self.field.setFrame(False)
        self.field.hide()
        self.field.textChanged.connect(self.queryChanged)
        self.field.textChanged.connect(lambda _: self.update())
        self.field.installEventFilter(self)
        self.field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setAccessibleName('Search folders')
        self.setCursor(Qt.PointingHandCursor)
        self.keyboard_shown = False
        QGuiApplication.inputMethod().visibleChanged.connect(self.keyboard_visibility_changed)

    def face_height(self):
        return round(SEARCH_FACE_HEIGHT * button_scale())

    def preferred_height(self):
        return self.face_height() + 2 * CONTROL_HEADROOM + 2 * BUTTON_SHADOW

    def collapsed_width(self):
        return self.face_height() + 2 * CONTROL_HEADROOM

    def outer_rect(self):
        outer = button_paint_rect(self)
        width = self.collapsed_width() + (outer.width() - self.collapsed_width()) * self.progress
        outer.setRight(outer.left() + width)
        return outer

    def face_rect(self):
        return control_face(self.outer_rect(), widget=self)

    def icon_rect(self, face):
        return QRectF(face.left(), face.top(), face.height(), face.height())

    def clear_rect(self, face):
        return QRectF(face.right() - face.height(), face.top(), face.height(), face.height())

    def toggle(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded, animate=True):
        if expanded == self.expanded:
            return
        self.expanded = expanded
        self.animation.stop()
        if not expanded:
            self.keyboard_shown = False
            self.field.clear()
            self.field.clearFocus()
        if animate and self.isVisible():
            self.animation.setStartValue(self.progress)
            self.animation.setEndValue(1.0 if expanded else 0.0)
            self.animation.start()
        else:
            self.set_progress(1.0 if expanded else 0.0)
            self.finish()
        self.expandedChanged.emit(expanded)

    def set_progress(self, value):
        self.progress = float(value)
        self.place_field()
        self.update()
        self.progressChanged.emit(self.progress)

    def finish(self):
        self.place_field()
        if self.expanded:
            self.field.setFocus(Qt.MouseFocusReason)
            # Phones only show their keyboard for a tap in the field, so ask for it once the bar is open.
            QGuiApplication.inputMethod().show()

    def keyboard_visibility_changed(self):
        # Android's Back hides the keyboard without telling the app; with nothing typed, that Back closes the search.
        visible = QGuiApplication.inputMethod().isVisible()
        if visible and self.expanded:
            self.keyboard_shown = True
        elif not visible and self.keyboard_shown:
            self.keyboard_shown = False
            if self.expanded and not self.field.text():
                self.set_expanded(False)

    def apply_text_color(self, color):
        # The app stylesheet colors every text field, so only a rule on this field itself wins over it.
        placeholder = QColor(color)
        placeholder.setAlphaF(.6)
        style = (f'QLineEdit#folderSearchField {{ background: transparent; border: none; padding: 0; '
                 f'color: {color.name()}; placeholder-text-color: {placeholder.name(QColor.HexArgb)}; }}')
        if style != self.field.styleSheet():
            self.field.setStyleSheet(style)

    def update_mask(self):
        outer = self.outer_rect().adjusted(-BUTTON_SHADOW, -BUTTON_SHADOW, 0, BUTTON_SHADOW)
        self.setMask(QRegion(outer.toAlignedRect()))

    def place_field(self):
        self.update_mask()
        face = self.face_rect()
        inner = face.adjusted(face.height(), 0, -face.height(), 0)
        visible = self.progress > .55 and inner.width() > 24
        self.field.setVisible(visible)
        if visible:
            metrics = QFontMetricsF(self.field.font())
            lift = (metrics.ascent() - metrics.descent()) / 2 - (metrics.capHeight() + metrics.xHeight()) / 4
            self.field.setGeometry(inner.translated(0, -lift).toRect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_field()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        face = self.face_rect()
        point = event.position()
        if not face.contains(point):
            event.ignore()
            return
        self.pressed_part = ('icon' if self.icon_rect(face).contains(point) or not self.expanded
                             else 'clear' if self.field.text() and self.clear_rect(face).contains(point) else 'field')
        if self.pressed_part != 'field':
            play_button_sound()
        else:
            self.field.setFocus(Qt.MouseFocusReason)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        part, self.pressed_part = self.pressed_part, None
        self.update()
        if event.button() != Qt.LeftButton or part is None:
            event.ignore()
            return
        face = self.face_rect()
        point = event.position()
        if part == 'icon' and (self.icon_rect(face).contains(point) or not self.expanded):
            self.toggle()
        elif part == 'clear' and self.clear_rect(face).contains(point):
            self.field.clear()
            self.field.setFocus(Qt.MouseFocusReason)
        event.accept()

    def eventFilter(self, watched, event):
        if watched is self.field and event.type() == event.Type.KeyPress and event.key() == Qt.Key_Escape:
            self.set_expanded(False)
            return True
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        app = QApplication.instance()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        fill = QColor(app.property('themeAccent') or '#cfe10e')
        ink = QColor(app.property('themeBackgroundAccent') or '#16191e')
        face = paint_control(painter, self, self.outer_rect(), fill, self.pressed_part in ('icon', 'clear'))
        self.apply_text_color(ink)
        size = face.height() * .62
        icon = QRectF(0, 0, size, size)
        icon.moveCenter(self.icon_rect(face).center())
        # Once open, the button only closes the bar, so it shows that instead of the magnifier.
        self.icon_factory('collapse' if self.progress > .5 else 'search', ink.name()).paint(painter, icon.toRect())
        if self.progress > .55 and self.field.text():
            icon.moveCenter(self.clear_rect(face).center())
            painter.setOpacity(min(1.0, (self.progress - .55) / .3))
            self.icon_factory('clear', ink.name()).paint(painter, icon.toRect())


class FolderSearch(QObject):
    """Matches, kept ancestors and row hiding for one FolderBrowser."""

    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree
        self.index_root = None
        self.index_paths = None
        self.indexer = None
        self.query = ''
        self.matches = set()
        self.keep = set()
        self.hidden_rows = []
        self.saved_expanded = None
        self.saved_scroll = 0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SEARCH_DELAY_MS)
        self.timer.timeout.connect(self.run)
        self.wiggle_clock = QElapsedTimer()
        self.wiggle_clock.start()
        self.wiggle_timer = QTimer(self)
        self.wiggle_timer.setInterval(33)
        self.wiggle_timer.timeout.connect(lambda: self.tree.viewport().update())

    @property
    def active(self):
        return bool(self.query.strip())

    def root_path(self):
        model = self.tree.model()
        return model.filePath(self.tree.rootIndex()) if model is not None else ''

    def set_query(self, text):
        starting = not self.active and text.strip()
        if starting:
            self.saved_expanded = self.expanded_paths()
            self.saved_scroll = self.tree.verticalScrollBar().value()
        self.query = text
        if not self.active:
            self.timer.stop()
            self.clear()
            return
        self.timer.start()

    def expanded_paths(self):
        model = self.tree.model()
        found, pending = [], [self.tree.rootIndex()]
        while pending:
            parent = pending.pop()
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                if self.tree.isExpanded(index):
                    found.append(model.filePath(index))
                    pending.append(index)
        return found

    def run(self):
        root = self.root_path()
        if not root or not self.active:
            return
        if self.index_root != root or self.index_paths is None:
            if self.indexer is None or self.indexer.root != root:
                if self.indexer is not None:
                    self.indexer.requestInterruption()
                self.indexer = FolderIndexer(root, self)
                self.indexer.ready.connect(self.index_ready)
                self.indexer.finished.connect(self.indexer.deleteLater)
                self.indexer.start(QThread.LowPriority)
            return
        self.apply(search_matches(self.index_paths, self.query))

    def index_ready(self, root, paths):
        if self.indexer is not None and self.indexer.root == root:
            self.indexer = None
        self.index_root, self.index_paths = root, paths
        if self.active and root == self.root_path():
            self.apply(search_matches(paths, self.query))

    def invalidate(self):
        self.index_root = self.index_paths = None

    def apply(self, matches):
        model = self.tree.model()
        root = self.root_path()
        self.matches = set(matches)
        self.keep = set(self.matches)
        for path in matches:
            parent = path.rsplit('/', 1)[0]
            while len(parent) > len(root) and parent not in self.keep:
                self.keep.add(parent)
                parent = parent.rsplit('/', 1)[0]
        self.tree.collapseAll()
        for path in sorted(self.keep - self.matches, key=len):
            self.tree.expand(model.index(path))
        self.filter_rows()
        if matches:
            self.tree.scrollTo(model.index(sorted(matches, key=lambda path: path.casefold())[0]))
        self.wiggle_timer.start() if self.matches else self.wiggle_timer.stop()
        self.tree.viewport().update()

    def filter_rows(self, parent=None):
        model = self.tree.model()
        pending = [self.tree.rootIndex() if parent is None else parent]
        while pending:
            parent = pending.pop()
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                path = model.filePath(index)
                hidden = self.active and path not in self.keep
                if self.tree.isRowHidden(row, parent) != hidden:
                    self.tree.setRowHidden(row, parent, hidden)
                    if hidden:
                        self.hidden_rows.append(QPersistentModelIndex(index))
                if not hidden and self.tree.isExpanded(index):
                    pending.append(index)

    def directory_loaded(self, path):
        if self.active:
            index = self.tree.model().index(path)
            if index.isValid():
                self.filter_rows(index)

    def clear(self):
        model = self.tree.model()
        self.matches, self.keep = set(), set()
        self.wiggle_timer.stop()
        if model is not None:
            # Rows hidden inside folders that have since closed are out of filter_rows' reach.
            for index in self.hidden_rows:
                if index.isValid():
                    self.tree.setRowHidden(index.row(), index.parent(), False)
            self.hidden_rows = []
            self.filter_rows()
            if self.saved_expanded is not None:
                self.tree.collapseAll()
                for path in self.saved_expanded:
                    index = model.index(path)
                    if index.isValid():
                        self.tree.expand(index)
                self.tree.doItemsLayout()
                self.tree.verticalScrollBar().setValue(self.saved_scroll)
        self.saved_expanded = None
        self.tree.viewport().update()

    def is_match(self, index):
        return bool(self.matches) and self.tree.model().filePath(index) in self.matches

    def phase(self):
        return self.wiggle_clock.elapsed() / 1000 * 7.0

    def shutdown(self):
        if self.indexer is not None:
            self.indexer.requestInterruption()
            self.indexer.wait()
