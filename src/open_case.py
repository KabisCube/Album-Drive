"""A closed CD case with a paper track list sliding out from behind it."""

from io import BytesIO
import colorsys
from PIL import Image
from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRect, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontInfo, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap, QRegion, QTransform
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget, QVBoxLayout, QWidget
from themes import NUMERIC_DEFAULTS, button_paint_rect, control_face, paint_control
from font_support import font_family_css
from shiboken6 import isValid
from case_shell import paint_cd_case, fitted_case_rect
from case_geometry import CASE_WIDTH, CASE_HEIGHT
from color_rules import artwork_text_color, color_contrast, comfortable_color

PLAYING_ROLE = Qt.UserRole + 1


def artwork_palette(artwork, colors=8, minimum=.025):
    """Extract cover colors by prominence, excluding transparent pixels."""
    if not artwork:
        return ()
    try:
        with Image.open(BytesIO(artwork)) as image:
            image.thumbnail((64, 64))
            rgba = image.convert('RGBA')
            data = rgba.get_flattened_data() if hasattr(rgba, 'get_flattened_data') else rgba.getdata()
            pixels = [pixel[:3] for pixel in data if pixel[3] >= 128]
        if not pixels:
            return ()
        sample = Image.new('RGB', (len(pixels), 1))
        sample.putdata(pixels)
        palette_image = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        palette = palette_image.getpalette()
        # Near-identical shades otherwise occupy most slots on photographic
        # covers; tiny lettering/noise can then become the only accent choice.
        groups = []
        for count, index in sorted(palette_image.getcolors(), reverse=True):
            rgb = palette[index * 3:index * 3 + 3]
            group = next((entry for entry in groups
                          if sum((a - b) ** 2 for a, b in zip(entry[1], rgb)) < 32 ** 2), None)
            if group is None:
                groups.append([count, rgb])
            else:
                total = group[0] + count
                group[1] = [round((a * group[0] + b * count) / total) for a, b in zip(group[1], rgb)]
                group[0] = total
        return tuple(QColor(*rgb) for count, rgb in sorted(groups, key=lambda entry: entry[0], reverse=True)
                     if count >= len(pixels) * minimum)
    except (OSError, ValueError, Image.DecompressionBombError):
        return ()


def artwork_accent_palette(artwork):
    if not artwork:
        return ()
    try:
        with Image.open(BytesIO(artwork)) as image:
            image.thumbnail((128, 128))
            rgba = image.convert('RGBA')
            data = rgba.get_flattened_data() if hasattr(rgba, 'get_flattened_data') else rgba.getdata()
            pixels = [pixel[:3] for pixel in data if pixel[3] >= 128]
        groups = {}
        for rgb in pixels:
            high, low = max(rgb), min(rgb)
            if high - low < 51 or not 61 <= high + low <= 449:
                continue
            hue, saturation, _ = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
            if saturation >= .5:
                groups.setdefault(int(hue * 36) % 36, []).append(rgb)
        colors = []
        for group in sorted(groups.values(), key=len, reverse=True):
            if len(group) < max(8, len(pixels) * .003):
                continue
            strongest = sorted(group, key=lambda rgb: max(rgb) - min(rgb), reverse=True)[:max(1, len(group) // 3)]
            colors.append(QColor(*(round(sum(rgb[channel] for rgb in strongest) / len(strongest)) for channel in range(3))))
        return tuple(colors)
    except (OSError, ValueError, Image.DecompressionBombError):
        return ()


def artwork_background(artwork):
    palette = artwork_palette(artwork)
    return palette[0] if palette else None


def readable_paper_text(background, preferred, palette=()):
    if palette:
        return artwork_text_color((background,), palette)
    if color_contrast(background, preferred) >= 4.5:
        return preferred
    return artwork_text_color((background,), (preferred,))


def artwork_scrollbar_colors(background, palette):
    accent = next((color for color in palette if color_contrast(background, color) >= 3), None)
    if accent is None:
        # Single-color/subtle covers need a contrasting shade of their main hue.
        target = max((QColor('white'), QColor('black')),
                     key=lambda color: color_contrast(background, color))
        for step in range(1, 21):
            amount = step / 20
            accent = QColor(*(round(first * (1 - amount) + second * amount) for first, second in
                              zip(background.getRgb()[:3], target.getRgb()[:3])))
            if color_contrast(background, accent) >= 3:
                break
    candidates = (*palette, accent.lighter(150), accent.darker(150), QColor('white'), QColor('black'))
    fill = next((color for color in candidates if color_contrast(background, color) >= 3
                 and color_contrast(accent, color) >= 1.25), accent)
    return accent, fill


class TrackNumberDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        table = self.parent()
        painter.fillRect(option.rect, QColor(table.property('paperBackgroundColor') or '#f2efdf'))
        color = QColor(table.property('paperForegroundColor') or
                       QApplication.instance().property('paperTextColor') or '#24383f')
        center = QRectF(option.rect).center()
        text = str(index.data(Qt.DisplayRole) or '')
        font = QFont(option.font)
        bounds = QFontMetricsF(font).tightBoundingRect(text)
        width, height = max(1, option.rect.width() - 24), max(1, option.rect.height() - 6)
        size = QFontInfo(font).pixelSize()
        while size > 1 and (bounds.width() > width or bounds.height() > height):
            factor = min(width / max(1, bounds.width()), height / max(1, bounds.height()))
            size = max(1, min(size - 1, int(size * factor)))
            font.setPixelSize(size)
            bounds = QFontMetricsF(font).tightBoundingRect(text)
        ratio = painter.device().devicePixelRatioF()
        origin = QPointF(round((option.rect.left() + 12 - bounds.left()) * ratio) / ratio,
                         round((center.y() - bounds.center().y()) * ratio) / ratio)
        center = bounds.translated(origin).center()
        painter.setFont(font)
        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(color, 3))
            painter.setBrush(Qt.NoBrush)
            content_height = max(44, QFontMetricsF(option.font).height() + 12)
            radius = min(content_height / 2 - 3, option.rect.height() / 2 - 3,
                         center.x() - option.rect.left() - 2,
                         option.rect.right() - center.x() - 2)
            painter.drawEllipse(center, radius, radius)
        painter.setPen(color)
        if index.data(PLAYING_ROLE):
            triangle = QPainterPath()
            triangle.moveTo(center.x() - 3, center.y() - 5)
            triangle.lineTo(center.x() + 5, center.y())
            triangle.lineTo(center.x() - 3, center.y() + 5)
            triangle.closeSubpath()
            painter.setBrush(color)
            painter.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(triangle)
        else:
            painter.setPen(color)
            painter.drawText(origin, text)
        painter.restore()


class TrackTitleDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        plain = QStyleOptionViewItem(option)
        plain.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus | QStyle.State_MouseOver)
        super().paint(painter, plain, index)


class CaseFront(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.sheen_key = ''
        self.lighting_source = None
        self.setStyleSheet('background: transparent;')

    def image_rect(self):
        return fitted_case_rect(self.rect())

    def paintEvent(self, event):
        if self.pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        target = self.image_rect()
        lighting = None
        if self.lighting_source is not None and isValid(self.lighting_source):
            origin = self.mapFromGlobal(self.lighting_source.mapToGlobal(QPoint()))
            lighting = QRectF(self.lighting_source.rect()).translated(origin)
        paint_cd_case(painter, self, target, self.pixmap, self.sheen_key, visible=lighting, shadow=True)


class TrackListBackground(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        background = QColor(self.property('paperBackgroundColor') or '#f2efdf')
        paint_control(painter, self, button_paint_rect(self), background)


class AlbumPresentation(QWidget):
    dismissed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('albumPresentation')
        self.setStyleSheet('QWidget#albumPresentation { background: transparent; }')
        self.setMinimumSize(440, 290)
        self.progress = 1.0
        self.paper_background = None
        self.paper_palette = ()
        self.artwork_text_color = None
        self.paper_button_color = None
        self.paper_background_accent_color = None
        self.uses_global_text = True
        self.booklet = TrackListBackground(self)
        self.booklet.setObjectName('booklet')
        self.booklet_style = '''
            QWidget#booklet { background: transparent; border: none; }
            QWidget#booklet QTableWidget { background: #f2efdf; color: #24383f;
                alternate-background-color: #f2efdf; border: none; }
            QWidget#booklet QHeaderView::section { background: #dedfd2; color: #24383f; padding: 5px; }
            QWidget#booklet QTableWidget::item { padding: 4px; }
            QWidget#booklet QTableWidget::item:selected { background: #f2efdf; color: #24383f; }
            QWidget#booklet QScrollBar { background: #f2efdf; }
            QWidget#booklet QAbstractScrollArea::corner { background: #f2efdf; }
        '''
        self.update_theme()
        layout = QVBoxLayout(self.booklet)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(7)
        self.table = QTableWidget(0, 2)
        self.table.setItemDelegateForColumn(0, TrackNumberDelegate(self.table))
        self.table.setItemDelegateForColumn(1, TrackTitleDelegate(self.table))
        self.table.setAccessibleName('Paper album track list')
        self.table.verticalHeader().setDefaultSectionSize(max(42, self.table.fontMetrics().height() + 10))
        layout.addWidget(self.table, 1)
        self.paper_opacity = QGraphicsOpacityEffect(self.booklet)
        self.paper_opacity.setOpacity(1)
        self.booklet.setGraphicsEffect(self.paper_opacity)
        self.front = CaseFront(self)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(420)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finish)
        self.update_theme()

    def reveal(self, front):
        self.animation.stop()
        self.front.pixmap = front
        self.advance(0.0)
        self.front.raise_()
        self.animation.start()

    def advance(self, progress):
        self.progress = float(progress)
        self.paper_opacity.setOpacity(min(1.0, self.progress * 4))
        self.arrange()

    def finish(self):
        self.advance(1.0)

    def set_artwork(self, artwork, theme_colors=None):
        self.paper_palette = tuple(comfortable_color(color) for color in artwork_palette(artwork))
        self.paper_background = self.paper_palette[0] if self.paper_palette else None
        text_color = theme_colors.get('textColor') if theme_colors else None
        color = QColor(text_color) if text_color else QColor()
        self.artwork_text_color = color if color.isValid() else None
        self.paper_button_color = theme_colors.get('themeAccent') if theme_colors else None
        self.paper_background_accent_color = theme_colors.get('themeBackgroundAccent') if theme_colors else None
        self.uses_global_text = self.artwork_text_color is None and self.paper_background is None
        self.update_theme()

    def update_theme(self):
        app = QApplication.instance()
        families = font_family_css(str(app.property('trackListFamily') or app.font().family()))
        background = self.paper_background or QColor('#f2efdf')
        preferred = self.artwork_text_color or QColor(app.property('paperTextColor') or '#24383f')
        foreground = (preferred if self.artwork_text_color is not None or self.paper_background is None
                      else readable_paper_text(background, preferred, self.paper_palette))
        style = self.booklet_style.replace('#f2efdf', background.name()).replace('#24383f', foreground.name())
        if self.paper_background is not None:
            style = style.replace('#dedfd2', background.name())
        size = app.property('trackListFontSize') or NUMERIC_DEFAULTS['track_list_font_size']
        style += f'QTableWidget {{ font-family: {families}; font-size: {size}px; font-weight: normal; font-style: normal; }}'
        self.booklet.setStyleSheet(style)
        self.booklet.setProperty('paperBackgroundColor', background.name())
        self.booklet.update()
        if hasattr(self, 'table'):
            self.table.setProperty('paperBackgroundColor', background.name())
            self.table.setProperty('paperForegroundColor', foreground.name())
            self.table.setProperty('paperButtonColor', self.paper_button_color)
            self.table.setProperty('paperBackgroundAccentColor', self.paper_background_accent_color)
            self.table.viewport().update()
            self.table.verticalScrollBar().update()
            self.table.horizontalScrollBar().update()
            row_height = max(44, self.table.fontMetrics().height() + 12)
            spacing = app.property('trackListVerticalSpacing') or 0
            metrics = QFontMetricsF(self.table.font())
            minimum = max(20, int(metrics.tightBoundingRect('AgjÉ0123456789').height()) + 8)
            self.table.verticalHeader().setMinimumSectionSize(minimum)
            self.table.verticalHeader().setDefaultSectionSize(max(minimum, row_height + spacing))
            # Reserve the full chosen font size for every two-digit index.
            number_width = max(metrics.tightBoundingRect(str(number)).width() for number in range(100))
            self.table.setColumnWidth(0, max(row_height, int(number_width + 25)))
        if hasattr(self, 'front'):
            self.arrange()

    def hideEvent(self, event):
        self.animation.stop()
        self.finish()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def mouseReleaseEvent(self, event):
        point = event.position().toPoint()
        if event.button() == Qt.LeftButton:
            if not (self.front.geometry().contains(point) or self.booklet.geometry().contains(point)):
                self.dismissed.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def arrange(self):
        width = max(1, min(self.width() - 20, 1200))
        available_height = max(1, self.height() - 16)
        case_width = min(width * .55, available_height * CASE_WIDTH / CASE_HEIGHT, 640)
        case_height = case_width * CASE_HEIGHT / CASE_WIDTH
        paper_width = min(width - case_width + 8, case_width * .9)
        paper_height = case_height * .84
        top = 8 + (available_height - paper_height) / 2
        left = (self.width() - case_width - paper_width + 8) / 2
        scale = .94 + .06 * self.progress
        front_rect = QRectF(0, 0, case_width * scale, case_height * scale)
        front_rect.moveCenter(QRectF(left, top, case_width, paper_height).center())
        front_rect.translate(0, 6 * (1 - self.progress) - 4 * self.progress)
        self.front.setGeometry(front_rect.toRect())
        start = left + case_width - paper_width - 24
        finish = left + case_width - 8
        paper_x = start + (finish - start) * self.progress
        self.booklet.setGeometry(round(paper_x), round(top), round(paper_width), round(paper_height))
        # Reveal only the paper that has actually passed the case's right edge.
        # This also hides it through the transparent margins of the case image.
        cut = max(0, min(self.booklet.width(), round(front_rect.right() - 8 - paper_x)))
        self.booklet.setVisible(cut < self.booklet.width())
        face = control_face(button_paint_rect(self.booklet), widget=self.booklet)
        self.booklet.layout().setContentsMargins(
            round(face.left() + 16), round(face.top() + 16),
            round(self.booklet.width() - face.right() + 16),
            round(self.booklet.height() - face.bottom() + 14))
        if cut > 0:
            self.booklet.setMask(QRegion(QRect(cut, 0, self.booklet.width() - cut, self.booklet.height())))
        else:
            self.booklet.clearMask()
        self.front.update()
        self.update()
