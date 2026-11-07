"""Shared themed controls, font scaling, control geometry and application styles."""

from pathlib import Path
from functools import lru_cache, wraps
from contextvars import ContextVar
from tempfile import TemporaryDirectory
from math import ceil
from weakref import WeakSet
import re

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap, QRegion, QTransform, QWheelEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QAbstractScrollArea, QCheckBox, QComboBox, QFrame, QLabel, QLayout, QListView, QMenu, QPushButton, QSlider, QStyle, QStyleOptionButton, QStyleOptionSlider, QStylePainter, QStyledItemDelegate, QTabBar, QToolButton, QVBoxLayout, QWidget
from button_sounds import play_button_sound
from responsive import running_on_android
from font_support import font_family_css
from color_rules import artwork_text_color, disabled_text_color, slider_rail
from shiboken6 import isValid


_asset_directory = TemporaryDirectory(prefix='music-player-theme-')
BUILDING_GRAY = '#393939'
GRASS_GREEN = '#888888'
TIMELINE_COLOR = '#888888'
CLEANING_DEFAULT = False
THEME_DEFAULT = 'chunky'
ARTWORK_THEME_DEFAULT = True
ARTWORK_THEME_MODE_DEFAULT = 'any'
UI_FONT_DEFAULT = 'AlbumRound-Bold.ttf'
ALBUM_SORT_DEFAULT = 'newest'
VOLUME_DEFAULT = 100
CONTROL_HEADROOM = 12
ANDROID_FOLDER_FONT_BOOST = 2
_control_preview = ContextVar('control_preview', default=None)
LOGO_BACKGROUND_HEIGHT = 1.8
LOGO_MAX_DEPTH = 12
LOGO_BACKGROUND_TRIM = 2
LOGO_VERTICAL_OFFSET = -2
MARKER_COLOR_DEFAULT = '#1b2834'
NUMERIC_DEFAULTS = {
    'case_open_volume': 70,
    'case_close_volume': 70,
    'theme_fade_seconds': 4.0,
    'album_scale': 102,
    'corner_roundness': 32,
    'button_font_size': 17,
    'button_size': 44,
    'ui_thickness': 100,
    'button_icon_size': 28,
    'button_sound_volume': 100,
    'main_font_size': 16,
    'secondary_font_size': 16,
    'heading_font_size': 26,
    'logo_font_size': 27,
    'folder_font_size': 14,
    'folder_vertical_spacing': -4,
    'settings_vertical_spacing': -12,
    'now_playing_font_size': 18,
    'now_playing_heading_font_size': 13,
    'dropdown_font_size': 17,
    'menu_font_size': 16,
    'settings_heading_font_size': 26,
    'handwriting_font_size': 34,
    'timeline_font_size': 20,
    'track_list_font_size': 16,
    'track_list_vertical_spacing': -16,
    'hover_rotation': 2.0,
    'hover_growth': 1.9,
    'hover_lift': 2,
    'album_horizontal_spacing': 5,
    'album_vertical_spacing': 5,
}

# Shared by the settings dialog, stylesheet, and custom-painted controls.
COLOR_SETTINGS = (
    ('Appearance', 'Accent color', 'theme_accent_color', 'themeHighlight', '#cfe10e'),
    ('Appearance', 'Button color', 'theme_highlight_color', 'themeAccent', GRASS_GREEN),
    ('Appearance', 'Background color', 'theme_background_color', 'themeBackground', BUILDING_GRAY),
    ('Appearance', 'Background accent color', 'theme_background_accent_color', 'themeBackgroundAccent', '#cfe10e'),
    ('Appearance', 'Timeline color', 'theme_timeline_color', 'timelineColor', TIMELINE_COLOR),
    ('Appearance', 'Logo background color', 'theme_brand_line_color', 'brandLineColor', '#707474'),
    ('Appearance', 'Folder arrow color', 'theme_folder_arrow_color', 'folderArrowColor', '#ffffff'),
    ('Buttons', 'Button background color', 'theme_button_fill', 'buttonFill', '#cccccc'),
    ('Buttons', 'Button icon color', 'theme_button_icon_color', 'buttonIconColor', '#000000'),
    ('Buttons', 'Button content color', 'theme_button_text_color', 'buttonTextColor', '#000000'),
    ('Buttons', 'Disabled text and icon color', 'theme_disabled_text_color', 'disabledTextColor', '#000000'),
    ('Text', 'Text color', 'theme_text_color', 'textColor', '#ffffff'),
    ('Text', 'Secondary text', 'theme_secondary_text_color', 'secondaryTextColor', '#ffffff'),
    ('Text', 'Headings', 'theme_heading_text_color', 'headingTextColor', '#ffffff'),
    ('Text', 'Album Drive logo color', 'theme_brand_text_color', 'brandTextColor', '#cfe10e'),
    ('Text', 'Selection text color', 'theme_selected_text_color', 'selectedTextColor', '#ffffff'),
    ('Text', 'Timeline text color', 'theme_timeline_text_color', 'timelineTextColor', '#ffffff'),
    ('Text', 'Track list text color', 'theme_paper_text_color', 'paperTextColor', '#393e41'),
)

# Only these colors are edited; legacy keys still travel with saved themes.
PRIMARY_COLOR_KEYS = frozenset(('theme_background_color', 'theme_accent_color',
                              'theme_text_color', 'theme_highlight_color', 'theme_background_accent_color'))


# Old keys remain readable in saved themes; the UI uses one shared control.
MERGED_NUMERIC_SETTINGS = {'secondary_font_size': 'main_font_size', 'menu_font_size': 'main_font_size',
                           'dropdown_font_size': 'button_font_size'}
MERGED_COLOR_SETTINGS = {'theme_secondary_text_color': 'theme_text_color',
                         'theme_button_icon_color': 'theme_button_text_color'}

MAX_FONT_SIZE = 25
FONT_BASE_SIZES = {key: value for key, value in NUMERIC_DEFAULTS.items() if key.endswith('_font_size')}
FONT_SCALE_KEYS = {key: key.removesuffix('_size') + '_scale' for key in FONT_BASE_SIZES if key != 'main_font_size'}
SCROLLBAR_STYLE = '''
QScrollBar:vertical { width: 60px; margin: 12px 6px; }
QScrollBar:horizontal { height: 60px; margin: 12px; }
'''


def migrate_font_settings(settings):
    if settings.value('font_scaling_version', 0, type=int) >= 1:
        return
    master = max(8, min(MAX_FONT_SIZE, settings.value('main_font_size', FONT_BASE_SIZES['main_font_size'], type=int)))
    for key, scale_key in FONT_SCALE_KEYS.items():
        canonical = MERGED_NUMERIC_SETTINGS.get(key, key)
        value = settings.value(canonical, FONT_BASE_SIZES[key], type=int)
        ratio = round(100 * value / (FONT_BASE_SIZES[key] * master / FONT_BASE_SIZES['main_font_size']))
        if canonical == key and not settings.contains(scale_key):
            settings.setValue(scale_key, max(75, min(125, ratio)))
    settings.setValue('main_font_size', master)
    settings.setValue('font_scaling_version', 1)


def font_sizes(settings):
    master = max(8, min(MAX_FONT_SIZE, settings.value('main_font_size', FONT_BASE_SIZES['main_font_size'], type=int)))
    sizes = {'main_font_size': master}
    for key in FONT_SCALE_KEYS:
        canonical = MERGED_NUMERIC_SETTINGS.get(key, key)
        scale_key = FONT_SCALE_KEYS.get(canonical)
        scalar = max(75, min(125, settings.value(scale_key, 100, type=int))) if scale_key else 100
        size = round(FONT_BASE_SIZES[key] * master / FONT_BASE_SIZES['main_font_size'] * scalar / 100)
        sizes[key] = max(8, min(MAX_FONT_SIZE, size)) if canonical == 'button_font_size' else max(6, size)
    return sizes


def signed_setting_int(value):
    """Read negative numeric preferences stored as unsigned Windows DWORDs."""
    value = int(value)
    return value - 2 ** 32 if 2 ** 31 <= value < 2 ** 32 else value


def resolve_font(fonts, identity):
    """Keep file-based font choices working when Qt reports different families."""
    return next((font for font in fonts if font['id'] == identity), None) or next(
        (font for font in fonts if font['id'].split('::')[0] == identity.split('::')[0]), None)


def text_style():
    app = QApplication.instance()
    colors = {prop: app.property(prop) or default for _, _, _, prop, default in COLOR_SETTINGS}
    disabled_text = disabled_text_color(colors['textColor'])
    disabled_title = disabled_text_color(colors['textColor'])
    sizes = {key: int(app.property(''.join([key.split('_')[0]] + [word.title() for word in key.split('_')[1:]])) or default)
             for key, default in NUMERIC_DEFAULTS.items() if key.endswith('_font_size')}
    scale = button_scale()
    if running_on_android():
        sizes['folder_font_size'] += ANDROID_FOLDER_FONT_BOOST
    folder_spacing = app.property('folderVerticalSpacing')
    folder_spacing = 0 if folder_spacing is None else max(-12, min(40, int(folder_spacing)))
    folder_height = max(sizes['folder_font_size'] + 8, max(27, sizes['folder_font_size'] * 2 + 1) + folder_spacing)
    families = font_family_css(str(app.property('uiFontFamily') or app.font().family()))
    typography = f'''
QWidget {{ font-family: {families}; font-size: {sizes['main_font_size']}px; }}
QPushButton {{ font-size: {sizes['button_font_size']}px; }}
QComboBox, QComboBox QAbstractItemView {{ font-size: {sizes['dropdown_font_size']}px; }}
QTabBar {{ font-size: {sizes['button_font_size']}px; }}
QLabel#nowPlayingTitle {{ font-size: {sizes['now_playing_font_size']}px; }}
QLabel#nowPlayingHeading {{ font-size: {sizes['now_playing_heading_font_size']}px; }}
QLabel#muted, QStatusBar {{ font-size: {sizes['secondary_font_size']}px; }}
QLabel#heading {{ font-size: {sizes['heading_font_size']}px; }}
QLabel#brand {{ font-size: {sizes['logo_font_size']}px; }}
QLabel#settingsSection {{ font-size: {sizes['settings_heading_font_size']}px; font-weight: bold; }}
QLabel[settingsOptionTitle="true"] {{ color: {colors['textColor']}; }}
QTreeView#fileBrowser {{ font-size: {sizes['folder_font_size']}px; }}
QListWidget#opticalDiscs {{ font-size: {sizes['folder_font_size']}px; }}
QListWidget#opticalDiscs::item {{ min-height: {folder_height}px; }}
QTreeView#fileBrowser::item {{ height: {folder_height}px; }}
QMenu, QMenuBar, QToolTip {{ font-size: {sizes['menu_font_size']}px; }}
QPushButton {{ padding: {10*scale:g}px {20*scale:g}px; min-height: {24*scale:g}px; }}
QPushButton#previous, QPushButton#next {{ padding: 0px {14*scale:g}px; min-height: 0px; }}
'''
    return typography + '''
QWidget { color: TEXT; selection-color: SELECTED; }
QLabel#muted, QStatusBar { color: SECONDARY; }
QLabel#heading { color: HEADING; }
QLabel#brand { color: BRAND; }
QPushButton, QPushButton#play, QPushButton:hover, QPushButton#play:hover,
QPushButton:focus, QPushButton#play:focus, QPushButton:pressed, QPushButton#play:pressed { color: BUTTON; }
QPushButton:disabled, QPushButton#play:disabled { color: DISABLED; }
QPushButton[themeRole="highlight"], QPushButton[themeRole="highlight"]:disabled { color: HIGHLIGHTCONTENT; }
QWidget:disabled { color: TEXT; }
QDialog#themeSettings QLabel:disabled { color: LABELDIM; }
QDialog#themeSettings QLabel[settingsOptionTitle="true"]:disabled { color: OPTIONDIM; }
QDialog#themeSettings QAbstractScrollArea::corner { background: transparent; border: none; }
QTreeView::item:selected, QListWidget::item:selected, QTableWidget::item:selected,
QMenu::item:selected, QMenuBar::item:selected { color: SELECTED; }
QHeaderView::section, QMenu, QMenuBar, QToolTip { color: TEXT; }
'''.replace('LABELDIM', f'rgba{disabled_text.getRgb()}').replace('OPTIONDIM', f'rgba{disabled_title.getRgb()}').replace('SECONDARY', colors['secondaryTextColor']).replace('SELECTED', colors['selectedTextColor']).replace(
        'HEADING', colors['headingTextColor']).replace('BRAND', colors['brandTextColor']).replace(
        'BUTTON', colors['buttonTextColor']).replace('DISABLED', colors['disabledTextColor']).replace(
        'HIGHLIGHTCONTENT', colors['themeAccent']).replace('TEXT', colors['textColor']) + SCROLLBAR_STYLE


def control_property(name):
    values = _control_preview.get()
    if values is not None and name in values:
        return values[name]
    app = QApplication.instance()
    return app.property(name) if app is not None else None


def local_control_theme(cls):
    def wrap(method):
        @wraps(method)
        def invoke(self, *args, **kwargs):
            token = _control_preview.set(self.window().property('settingsPreview'))
            try:
                return method(self, *args, **kwargs)
            finally:
                _control_preview.reset(token)
        return invoke
    for name in ('paintEvent', 'sizeHint', 'minimumSizeHint', 'tabSizeHint', 'tabRect',
                 'tab_face_rect', 'button_text_regions', 'sync_popup_font', 'layout_actions', 'prepare_pages'):
        if name in cls.__dict__:
            setattr(cls, name, wrap(cls.__dict__[name]))
    return cls


def button_scale():
    return float(control_property('buttonSize') or 44) / 44


def button_size_options(options):
    if 'button_size' not in options:
        options = dict(options, button_size=max(20, min(72, round(float(options.get('button_scale', 100)) * .44))))
    return options


def migrate_button_size(settings):
    if not settings.contains('button_size'):
        settings.setValue('button_size', button_size_options({'button_scale': settings.value('button_scale', 100)})['button_size'])


def button_font_metrics(widget):
    font = QFont(widget.font())
    font.setPixelSize(NUMERIC_DEFAULTS['button_font_size'])
    return QFontMetrics(font)


def ui_depth():
    amount = control_property('uiThickness')
    return 4 * max(0, min(300, NUMERIC_DEFAULTS['ui_thickness'] if amount is None else amount)) / 100


def control_offset(widget, rect, depth):
    if not isinstance(widget, QWidget):
        return QPointF(0, depth)
    window = widget.window()
    if window.windowType() == Qt.Popup and window.parentWidget() is not None:
        window = window.parentWidget().window()
    center = widget.mapToGlobal(QPoint(0, 0)).x() - window.mapToGlobal(QPoint(0, 0)).x() + rect.center().x()
    position = max(-1, min(1, 1 - 2 * center / max(1, window.width())))
    return QPointF(position * depth, depth)


def control_face(rect, pressed=False, widget=None, depth=None):
    depth = ui_depth() if depth is None else depth
    offset = control_offset(widget, rect, depth)
    face = rect.adjusted(CONTROL_HEADROOM, CONTROL_HEADROOM, -CONTROL_HEADROOM, 0)
    return face if pressed else face.translated(-offset)


def button_paint_rect(widget):
    rect = QRectF(widget.rect()).adjusted(0, BUTTON_SHADOW, 0, -BUTTON_SHADOW)
    return rect.adjusted(0, 0, 0, -CONTROL_HEADROOM) if widget.property('centerFlatFace') else rect


@lru_cache(maxsize=256)
def control_body(width, height, radius, dx, dy):
    front = QPainterPath()
    front.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    body = QPainterPath(front)
    steps = max(1, int(max(abs(dx), abs(dy)) * 2 + 1))
    for step in range(1, steps + 1):
        body = body.united(front.translated(dx * step / steps, dy * step / steps))
    return body


@lru_cache(maxsize=256)
def control_shadow_body(width, height, radius, dx, dy, sx, sy):
    body = QPainterPath()
    body.addRoundedRect(QRectF(dx, dy, width, height), radius, radius)
    footprint = QPainterPath(body)
    steps = max(1, ceil(max(abs(sx), abs(sy)) * 2))
    for step in range(1, steps + 1):
        footprint = footprint.united(body.translated(sx * step / steps, sy * step / steps))
    return footprint


BUTTON_SHADOW = 9


def control_shadow(depth=None):
    size = min(BUTTON_SHADOW, max(0, ui_depth() if depth is None else depth) * .75)
    return QPointF(-size * 2 / 3, size)


def paint_control(painter, widget, rect, color, pressed=False, depth=None, rounding=None, shadow=True):
    if isinstance(widget, QWidget) and not widget.isEnabled():
        color = disabled_text_color(color)
    depth = ui_depth() if depth is None else depth
    raised = control_face(rect, widget=widget, depth=depth)
    face = control_face(rect, pressed, widget, depth)
    radius = (corner_radius(12, face.width(), face.height()) if rounding is None
              else min(face.width(), face.height()) / 2 * rounding / 100)
    front = QPainterPath()
    front.addRoundedRect(face, radius, radius)
    surface = painter
    layer = None
    shadow_offset = control_shadow(depth) if shadow else QPointF()
    if painter.opacity() < 1:
        bounds = rect.adjusted(shadow_offset.x(), 0, 0, shadow_offset.y()).toAlignedRect()
        ratio = painter.device().devicePixelRatioF()
        layer = QPixmap(QSize(round(bounds.width() * ratio), round(bounds.height() * ratio)))
        layer.setDevicePixelRatio(ratio)
        layer.fill(Qt.transparent)
        surface = QPainter(layer)
        surface.setRenderHint(QPainter.Antialiasing)
        surface.translate(-bounds.topLeft())
    body = front
    offset = QPointF()
    if not pressed:
        offset = control_offset(widget, rect, depth)
        body = control_body(raised.width(), raised.height(), radius, offset.x(), offset.y())
        body = body.translated(raised.topLeft())
    if shadow and not shadow_offset.isNull():
        footprint = control_shadow_body(face.width(), face.height(), radius, offset.x(), offset.y(),
                                        shadow_offset.x(), shadow_offset.y())
        surface.fillPath(footprint.translated(face.topLeft()), QColor(0, 0, 0, 65))
    if not pressed:
        surface.fillPath(body, QColor(color).darker(125))
    surface.fillPath(front, QColor(color))
    if layer is not None:
        surface.end()
        painter.drawPixmap(bounds.topLeft(), layer)
    return face


def corner_radius(base, width=None, height=None):
    amount = control_property('cornerRoundness')
    maximum = base * 2
    if width is not None and height is not None:
        maximum = min(maximum, width / 2, height / 2)
    return maximum * min(100, max(0, 100 if amount is None else amount)) / 100


def round_stylesheet(style, amount):
    return re.sub(r'border-radius:\s*([\d.]+)px',
                  lambda m: f'border-radius: {float(m[1]) * min(100, max(0, amount)) / 50:g}px', style)


@lru_cache(maxsize=64)
def accent_assets(accent, roundness=100, fill='#ffffff', depth=4):
    """Create scalable control artwork from one accent, including its depth."""
    color = QColor(accent)
    fill = QColor(fill).name()
    target = Path(_asset_directory.name) / f'{color.name()[1:]}-{roundness}-{fill[1:]}-{depth:g}'
    target.mkdir(exist_ok=True)
    for name in ('button-rounded.svg', 'timeline-knob.svg', 'slider-knob.svg'):
        if name == 'button-rounded.svg':
            width, height = 64, 48
            radius = 12 * min(1, roundness / 100)
        else:
            width = height = 24 if name == 'slider-knob.svg' else 36
            radius = height / 2 * min(1, roundness / 100)
        canvas_width, canvas_height = width + 2 * CONTROL_HEADROOM, height + CONTROL_HEADROOM + BUTTON_SHADOW
        top = CONTROL_HEADROOM - depth
        shadow_offset = control_shadow(depth)
        shadow = ''
        if not shadow_offset.isNull():
            steps = max(1, ceil(max(abs(shadow_offset.x()), abs(shadow_offset.y())) * 2))
            rectangles = ''.join(
                f'<rect x="{CONTROL_HEADROOM + shadow_offset.x() * step / steps:g}" '
                f'y="{CONTROL_HEADROOM + shadow_offset.y() * step / steps:g}" width="{width}" height="{height}" rx="{radius:g}"/>'
                for step in range(steps + 1))
            shadow = f'<g fill="#000000" opacity="{65 / 255:g}">{rectangles}</g>'
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
               f'viewBox="0 0 {canvas_width} {canvas_height}">'
               f'{shadow}'
               f'<rect x="{CONTROL_HEADROOM}" y="{top:g}" width="{width}" height="{height+depth:g}" '
               f'rx="{radius:g}" fill="#e57800"/>'
               f'<rect x="{CONTROL_HEADROOM}" y="{top:g}" width="{width}" height="{height}" '
               f'rx="{radius:g}" fill="#ff9800"/></svg>')
        svg = svg.replace('#ff9800', color.name()).replace('#e57800', color.darker(125).name())
        svg = svg.replace('#ffffff', fill)
        (target / name).write_text(svg, encoding='utf-8')
    (target / 'arrow.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="10" viewBox="0 0 14 10">'
        f'<path d="M2 2 L7 7 L12 2 Z" fill="{color.name()}" stroke="{color.name()}" '
        'stroke-width="3" stroke-linejoin="round"/></svg>', encoding='utf-8')
    return target.as_posix()


class ThemeSaveIcon(QIconEngine):
    def clone(self):
        return ThemeSaveIcon()

    def paint(self, painter, rect, mode, state):
        app = QApplication.instance()
        color = QColor(app.property('buttonIconColor') or '#101010')
        if mode == QIcon.Disabled:
            color = disabled_text_color(color)
        if app.property('playerTheme') == 'classic':
            color = button_text_color(app.property('buttonFill') or '#cccccc', mode != QIcon.Disabled)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        scale = min(rect.width() / 48, rect.height() / 32)
        painter.translate(rect.center().x() - 24 * scale, rect.center().y() - 16 * scale)
        painter.scale(scale, scale)
        painter.setPen(QPen(QColor(color), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        disk = QPainterPath()
        disk.moveTo(2, 5)
        disk.lineTo(19, 5)
        disk.lineTo(24, 10)
        disk.lineTo(24, 27)
        disk.lineTo(2, 27)
        disk.closeSubpath()
        painter.drawPath(disk)
        painter.drawRect(QRectF(7, 18, 12, 9))
        painter.drawRect(QRectF(7, 5, 10, 7))
        brush = QPainterPath()
        brush.moveTo(37, 19)
        brush.cubicTo(39, 13, 41, 6, 44, 3)
        brush.cubicTo(45, 9, 43, 16, 40, 21)
        brush.closeSubpath()
        painter.setBrush(QColor(color))
        painter.drawPath(brush)
        tip = QPainterPath()
        tip.moveTo(37, 21)
        tip.cubicTo(33, 21, 37, 26, 34, 28)
        tip.cubicTo(40, 29, 43, 26, 40, 22)
        painter.drawPath(tip)
        painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


class KnobIcon(QIconEngine):
    """Paint slider artwork in memory, without generating an SVG per color."""

    def __init__(self, accent, rounding, depth):
        super().__init__()
        self.accent, self.rounding = QColor(accent), rounding
        self.depth = depth

    def clone(self):
        return KnobIcon(self.accent, self.rounding, self.depth)

    def paint(self, painter, rect, mode, state):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        face_size = max(1, min(rect.width() - 2 * CONTROL_HEADROOM, rect.height() - CONTROL_HEADROOM))
        canvas = QRectF(0, 0, face_size + 2 * CONTROL_HEADROOM, face_size + CONTROL_HEADROOM)
        canvas.moveCenter(QRectF(rect).center())
        rounding = control_property('cornerRoundness')
        accent = disabled_text_color(self.accent) if mode == QIcon.Disabled else self.accent
        paint_control(painter, painter.device(), canvas, accent,
                      depth=self.depth, rounding=self.rounding if rounding is None else rounding, shadow=True)
        painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


def accent_knob(accent, fill=None, size=36):
    amount = control_property('cornerRoundness')
    rounding = 100 if amount is None else amount
    return QIcon(KnobIcon(accent, rounding, ui_depth()))


def draw_centered_text(painter, rect, font, text, color, fit=False):
    """Center visible letter shapes, including fonts with uneven line metrics."""
    text = text.replace('&&', '\0').replace('&', '').replace('\0', '&')
    ink = QPainterPath()
    ink.setFillRule(Qt.WindingFill)
    ink.addText(0, 0, font, text)
    if fit and not ink.isEmpty():
        bounds = ink.boundingRect()
        scale = min(1, max(0, rect.width()) / max(1, bounds.width()), max(0, rect.height()) / max(1, bounds.height()))
        ink = QTransform.fromScale(scale, scale).map(ink)
    ink.translate(QRectF(rect).center() - ink.boundingRect().center())
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillPath(ink, QColor(color))


def button_text_rect(face, dropdown=False):
    radius = corner_radius(12, face.width(), face.height())
    padding = max(4, min(10, radius * .3 + 3))
    horizontal = min(padding, face.width() * .22)
    vertical = min(padding, face.height() * .22)
    return face.adjusted(horizontal, vertical, -horizontal - (28 if dropdown else 0), -vertical)


@lru_cache(maxsize=4096)
def button_text_bounds(font_name, text, size):
    font = QFont()
    font.fromString(font_name)
    font.setPixelSize(size)
    text = text.replace('&&', '\0').replace('&', '').replace('\0', '&')
    path = QPainterPath()
    path.addText(0, 0, font, text)
    return path.boundingRect()


class ButtonTextSizing(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.controls = WeakSet()
        self.pixel_size = min(MAX_FONT_SIZE, int(app.property('buttonFontSize') or NUMERIC_DEFAULTS['button_font_size']))
        self.signature = None
        self.updating = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.refresh)

    def register(self, widget):
        self.controls.add(widget)
        widget.installEventFilter(self)
        widget.destroyed.connect(self.schedule)
        self.schedule()

    def schedule(self, *args):
        if not self.updating:
            self.timer.start(0)

    def eventFilter(self, widget, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.Hide, QEvent.ShowToParent,
                            QEvent.FontChange, QEvent.StyleChange, QEvent.LayoutRequest, QEvent.ParentChange):
            self.schedule()
        return False

    def refresh(self):
        if any(isValid(widget) and widget.window().property('settingsPreview') for widget in tuple(self.controls)):
            return
        self.updating = True
        app = QApplication.instance()
        requested = max(1, min(MAX_FONT_SIZE, int(app.property('buttonFontSize') or NUMERIC_DEFAULTS['button_font_size'])))
        samples = []
        for widget in tuple(self.controls):
            if not isValid(widget) or not widget.window().isVisible():
                continue
            if widget.property('fitButtonTextLocally'):
                continue
            if widget.isHidden() and not widget.sizePolicy().retainSizeWhenHidden():
                continue
            font_name = widget.font().toString()
            for rect, texts in widget.button_text_regions():
                if rect.width() > 0 and rect.height() > 0:
                    samples.extend((font_name, text, rect.width(), rect.height()) for text in texts if text)
        signature = requested, tuple(sorted(samples))
        if signature != self.signature:
            self.signature = signature
            size = requested
            for font_name, text, width, height in samples:
                bounds = button_text_bounds(font_name, text, requested)
                scale = min(1, width / max(1, bounds.width()), height / max(1, bounds.height()))
                size = max(1, min(size, int(requested * scale)))
            while size > 1 and any(button_text_bounds(font, text, size).width() > width or
                                   button_text_bounds(font, text, size).height() > height
                                   for font, text, width, height in samples):
                size -= 1
            if size != self.pixel_size:
                self.pixel_size = size
                for widget in tuple(self.controls):
                    if isValid(widget):
                        widget.update()
                        if isinstance(widget, ThemedComboBox):
                            widget.sync_popup_font()
                            widget.position_popup()
        self.updating = False


def button_text_sizing():
    app = QApplication.instance()
    if not hasattr(app, '_button_text_sizing'):
        app._button_text_sizing = ButtonTextSizing(app)
    return app._button_text_sizing


def button_text_font(widget):
    font = QFont(widget.font())
    preview = widget.window().property('settingsPreview')
    font.setPixelSize(preview['buttonFontSize'] if preview else button_text_sizing().pixel_size)
    return font


def button_text_color(background=None, enabled=True, highlighted=False):
    app = QApplication.instance()
    color = app.property('themeAccent') if highlighted else app.property('themeBackgroundAccent')
    color = QColor(color or app.property('buttonTextColor') or '#101010')
    return color if enabled else disabled_text_color(color)


def accent_shade(accent, amount):
    color, background = QColor(accent), QColor('#16191e')
    return QColor(*(round(a * amount + b * (1 - amount)) for a, b in zip(
        (color.red(), color.green(), color.blue()),
        (background.red(), background.green(), background.blue())))).name()


@local_control_theme
class ThemedButton(QPushButton):
    """Paint solid button faces with connected perspective depth."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keyboard_focus = False
        self.pressed.connect(play_button_sound)
        button_text_sizing().register(self)

    def setText(self, text):
        super().setText(text)
        button_text_sizing().schedule()

    def button_text_regions(self):
        if not self.icon().isNull() or self.property('swatchColor') or not self.text():
            return []
        face = control_face(button_paint_rect(self), widget=self)
        return [(button_text_rect(face), (self.text(),))]

    def sizeHint(self):
        scale = button_scale()
        width = button_font_metrics(self).horizontalAdvance(self.text()) + 40 if self.text() else 64
        return QSize(round(width * scale) + 2 * CONTROL_HEADROOM, round(44 * scale) + CONTROL_HEADROOM + 2 * BUTTON_SHADOW)

    def minimumSizeHint(self):
        return self.sizeHint()

    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (
            Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        self.keyboard_focus = False
        self.update()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        app = QApplication.instance()
        swatch = self.property('previewSwatchColor') or self.property('swatchColor')
        highlighted = self.property('themeRole') == 'highlight'
        if app.property('playerTheme') != 'chunky' and swatch is None and not highlighted:
            option = QStyleOptionButton()
            self.initStyleOption(option)
            if self.property('centerFlatFace'):
                option.rect = control_face(button_paint_rect(self), pressed=True, widget=self, depth=0).toRect()
                size = min(option.iconSize.width(), option.rect.width(), option.rect.height())
                option.iconSize = QSize(size, size)
            if not self.keyboard_focus:
                option.state &= ~QStyle.State_HasFocus
            if self.icon().isNull():
                option.text = ''
            painter = QStylePainter(self)
            painter.drawControl(QStyle.CE_PushButton, option)
            if self.icon().isNull():
                draw_centered_text(painter, button_text_rect(QRectF(option.rect)), button_text_font(self), self.text(),
                    button_text_color(app.property('themeHighlight') if highlighted else app.property('buttonFill') or '#cccccc',
                                      self.isEnabled(), highlighted=highlighted), fit=True)
            return
        color = QColor(swatch or app.property('themeHighlight' if highlighted else 'themeAccent') or '#ff9800')
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        outer = button_paint_rect(self)
        face = paint_control(painter, self, outer, color, self.isDown(), shadow=True)
        radius = corner_radius(12, face.width(), face.height())
        if not swatch:
            clip = QPainterPath()
            clip.addRoundedRect(face, radius, radius)
            painter.setClipPath(clip, Qt.IntersectClip)
        if not swatch and not self.icon().isNull():
            size = self.iconSize()
            scale = min(1, face.width() / max(1, size.width()), face.height() / max(1, size.height()))
            icon_rect = QRectF(0, 0, size.width() * scale, size.height() * scale)
            icon_rect.moveCenter(face.center())
            self.icon().paint(painter, icon_rect.toRect(), Qt.AlignCenter,
                              QIcon.Normal if self.isEnabled() else QIcon.Disabled)
        elif not swatch:
            draw_centered_text(painter, button_text_rect(face), button_text_font(self), self.text(),
                button_text_color(color, self.isEnabled(), highlighted=True) if highlighted else
                (QColor(app.property('buttonTextColor') or '#352719') if self.isEnabled() else
                 disabled_text_color(app.property('buttonTextColor') or '#352719')), fit=True)
        if self.hasFocus() and self.keyboard_focus:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color.darker(170), 1, Qt.DotLine))
            painter.drawRoundedRect(face.adjusted(2, 2, -2, -2), corner_radius(3), corner_radius(3))
        painter.end()


@lru_cache(maxsize=32)
def lettering_shadow(font_name, text, depth):
    shadow = QPainterPath()
    shadow.setFillRule(Qt.WindingFill)
    offset = control_shadow(depth)
    if offset.isNull():
        return shadow
    font = QFont()
    font.fromString(font_name)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    body = QPainterPath(path)
    body.setFillRule(Qt.WindingFill)
    for step in range(1, max(1, round(depth * 2)) + 1):
        body.addPath(path.translated(0, min(depth, step * .5)))
    steps = max(1, ceil(max(abs(offset.x()), abs(offset.y())) * 2))
    for step in range(steps + 1):
        shadow.addPath(body.translated(offset * (step / steps)))
    return shadow


@lru_cache(maxsize=32)
def lettering_shadow_pixmap(font_name, text, depth, width, height, ratio, x, y):
    layer = QPixmap(ceil(width * ratio), ceil(height * ratio))
    layer.setDevicePixelRatio(ratio)
    layer.fill(Qt.transparent)
    painter = QPainter(layer)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillPath(lettering_shadow(font_name, text, depth).translated(x, y), QColor(0, 0, 0, 65))
    painter.end()
    return layer


class ChunkyBrand(QLabel):
    def sizeHint(self):
        size = super().sizeHint()
        return QSize(size.width(), ceil(self.background_rect().height() + LOGO_BACKGROUND_TRIM + control_shadow(LOGO_MAX_DEPTH).y()))

    def minimumSizeHint(self):
        return self.sizeHint()

    def background_rect(self):
        path = QPainterPath()
        path.addText(0, 0, self.font(), self.text())
        height = ceil(path.boundingRect().height() * LOGO_BACKGROUND_HEIGHT + LOGO_MAX_DEPTH) - LOGO_BACKGROUND_TRIM
        return QRectF(0, 0, self.width(), height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addText(0, 0, self.font(), self.text())
        bounds = path.boundingRect()
        app = QApplication.instance()
        depth = ui_depth()
        stripe = self.background_rect()
        position = QPointF(self.width() / 2 - bounds.center().x(),
                           stripe.center().y() + LOGO_BACKGROUND_TRIM / 2 - depth - bounds.center().y() + LOGO_VERTICAL_OFFSET)
        path.translate(position)
        color = QColor(app.property('brandTextColor') or '#afbe0c')
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(QApplication.instance().property('brandLineColor') or '#f7f5f1'))
        painter.drawRoundedRect(stripe, corner_radius(6, stripe.width(), stripe.height()),
                               corner_radius(6, stripe.width(), stripe.height()))
        if depth:
            painter.drawPixmap(0, 0, lettering_shadow_pixmap(
                self.font().toString(), self.text(), depth, self.width(), self.height(),
                self.devicePixelRatioF(), position.x(), position.y()))
            painter.setBrush(color.darker(150))
            for step in range(1, max(1, round(depth * 2)) + 1):
                painter.drawPath(path.translated(0, min(depth, step * .5)))
        painter.setBrush(color)
        painter.drawPath(path)


def scroll_past_control(widget, event):
    """Scroll the surrounding page without changing the control's value."""
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            viewport = parent.viewport()
            forwarded = QWheelEvent(QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint())),
                                    event.globalPosition(), event.pixelDelta(), event.angleDelta(),
                                    event.buttons(), event.modifiers(), event.phase(), event.inverted())
            QApplication.sendEvent(viewport, forwarded)
            event.setAccepted(forwarded.isAccepted())
            return
        parent = parent.parentWidget()
    event.ignore()


@local_control_theme
class ThemeSlider(QSlider):
    """Rounded settings/volume slider with click-anywhere dragging."""

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.click_seeking = False
        self.paint_opacity = 1.0
        self.setMinimumHeight(48)
        self.setStyleSheet('''
QSlider::groove:horizontal { height: 8px; }
QSlider::handle:horizontal { width: 48px; height: 36px; margin: -20px 0 -8px 0; border: none; background: transparent; }
''')

    def set_paint_opacity(self, opacity):
        opacity = max(0.0, min(1.0, float(opacity)))
        if opacity != self.paint_opacity:
            self.paint_opacity = opacity
            self.update()

    def wheelEvent(self, event):
        scroll_past_control(self, event)

    def value_at(self, position):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        span = max(1, self.width() - handle.width())
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                             round(position.x() - handle.width() / 2), span, option.upsideDown)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.click_seeking = True
            self.setFocus(Qt.MouseFocusReason)
            self.setSliderDown(True)
            self.setValue(self.value_at(event.position()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.click_seeking:
            self.setValue(self.value_at(event.position()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.click_seeking:
            self.setValue(self.value_at(event.position()))
            self.click_seeking = False
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        app = QApplication.instance()
        layer = None
        if self.paint_opacity < 1:
            ratio = self.devicePixelRatioF()
            layer = QPixmap(self.size() * ratio)
            layer.setDevicePixelRatio(ratio)
            layer.fill(Qt.transparent)
        painter = QPainter(layer if layer is not None else self)
        painter.setRenderHint(QPainter.Antialiasing)
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        groove = QRectF(12, (self.height() - 8) / 2, max(1, self.width() - 24), 8)
        clip = QPainterPath()
        radius = corner_radius(4, groove.width(), groove.height())
        clip.addRoundedRect(groove, radius, radius)
        painter.save()
        painter.setClipPath(clip, Qt.IntersectClip)
        rail = QColor(app.property('themeBackgroundAccent') or
                      slider_rail(app.property('themeBackground') or BUILDING_GRAY))
        accent = QColor(app.property('themeAccent') or GRASS_GREEN)
        painter.fillRect(groove, rail if self.isEnabled() else disabled_text_color(rail))
        fill = QRectF(groove)
        if option.upsideDown:
            fill.setLeft(handle.center().x())
        else:
            fill.setRight(handle.center().x())
        painter.fillRect(fill, accent if self.isEnabled() else disabled_text_color(accent))
        painter.restore()
        accent_knob(app.property('themeAccent') or GRASS_GREEN,
                    app.property('buttonFill') or '#f7f5f1', size=24).paint(
                        painter, handle, Qt.AlignCenter, QIcon.Normal if self.isEnabled() else QIcon.Disabled)
        if layer is not None:
            painter.end()
            painter = QPainter(self)
            painter.setOpacity(self.paint_opacity)
            painter.drawPixmap(0, 0, layer)


@local_control_theme
class ChunkyCheckBox(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pressed.connect(play_button_sound)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + round(42 * button_scale()) + 2 * CONTROL_HEADROOM,
                     max(round(36 * button_scale()), self.fontMetrics().height() + 6) + CONTROL_HEADROOM + BUTTON_SHADOW)

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        app = QApplication.instance()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        accent = QColor(app.property('themeAccent') or GRASS_GREEN)
        size = 30 * button_scale()
        outer = QRectF(0, (self.height() - size - CONTROL_HEADROOM - BUTTON_SHADOW) / 2,
                       size + 2 * CONTROL_HEADROOM, size + CONTROL_HEADROOM)
        painter.setPen(Qt.NoPen)
        face = paint_control(painter, self, outer, accent, self.isDown(),
                             rounding=corner_radius(7, size, size) / (size / 2) * 100)
        if self.isChecked():
            painter.save()
            painter.translate(face.topLeft())
            painter.scale(size / 30, size / 30)
            tick = QPainterPath()
            tick.moveTo(8, 13.5)
            tick.lineTo(13, 18.5)
            tick.lineTo(22, 8.5)
            color = QColor(app.property('buttonIconColor') or '#483d34')
            painter.setPen(QPen(color if self.isEnabled() else disabled_text_color(color), 3,
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(tick)
            painter.restore()
        color = QColor(app.property('textColor') or '#e9edf3')
        painter.setPen(color if self.isEnabled() else disabled_text_color(color))
        painter.drawText(self.rect().adjusted(round(40 * button_scale()) + 2 * CONTROL_HEADROOM, CONTROL_HEADROOM, 0, -BUTTON_SHADOW),
                         Qt.AlignVCenter | Qt.AlignLeft, self.text())


@local_control_theme
class TabScrollButton(ThemedButton):
    def __init__(self, direction, parent):
        super().__init__(parent)
        self.direction = direction
        self.setAccessibleName('Scroll tabs left' if direction < 0 else 'Scroll tabs right')
        self.setToolTip(self.accessibleName())
        self.setAutoRepeat(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        app = QApplication.instance()
        painter.fillRect(self.rect(), QColor(app.property('themeBackground') or BUILDING_GRAY))
        outer = button_paint_rect(self).translated(0, -CONTROL_HEADROOM / 2)
        face = paint_control(painter, self, outer, app.property('themeAccent') or GRASS_GREEN, self.isDown(), shadow=True)
        size = min(face.width(), face.height()) * .45
        center = face.center()
        arrow = QPainterPath()
        arrow.moveTo(center.x() + self.direction * size / 2, center.y())
        arrow.lineTo(center.x() - self.direction * size / 2, center.y() - size / 2)
        arrow.lineTo(center.x() - self.direction * size / 2, center.y() + size / 2)
        arrow.closeSubpath()
        painter.fillPath(arrow, QColor(app.property('buttonIconColor') or '#000000'))


@local_control_theme
class ChunkyTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.ElideNone)
        self.scroll_offset = 0
        self.scroll_left = TabScrollButton(-1, self)
        self.scroll_right = TabScrollButton(1, self)
        self.scroll_left.clicked.connect(lambda: self.scroll_tabs(-1))
        self.scroll_right.clicked.connect(lambda: self.scroll_tabs(1))
        self.scroll_left.hide()
        self.scroll_right.hide()
        self.scroll_update_timer = QTimer(self)
        self.scroll_update_timer.setSingleShot(True)
        self.scroll_update_timer.timeout.connect(self.update_scroll_buttons)
        self.tabBarClicked.connect(self.play_tab_sound)
        self.currentChanged.connect(self.ensure_current_visible)
        button_text_sizing().register(self)
        self.hide_native_scroll_buttons()

    def hide_native_scroll_buttons(self):
        for button in self.findChildren(QToolButton):
            button.hide()
            button.setFixedSize(0, 0)
            button.setFocusPolicy(Qt.NoFocus)
            button.installEventFilter(self)

    def eventFilter(self, widget, event):
        if isinstance(widget, QToolButton) and widget.parentWidget() is self:
            if event.type() in (QEvent.Show, QEvent.ShowToParent):
                widget.hide()
                return True
            if event.type() == QEvent.Paint:
                return True
        return super().eventFilter(widget, event)

    def button_text_regions(self):
        return [(button_text_rect(control_face(self.tab_face_rect(index), widget=self)), (self.tabText(index),))
                for index in range(self.count()) if self.isTabVisible(index)]

    def scroll_button_width(self):
        return round(32 * button_scale()) + 2 * CONTROL_HEADROOM

    def content_width(self):
        return sum(self.tabSizeHint(index).width() for index in range(self.count()) if self.isTabVisible(index))

    def maximum_scroll(self):
        total = self.content_width()
        return max(0, total - max(1, self.width() - self.scroll_button_width())) if total > self.width() else 0

    def tab_viewport(self):
        maximum = self.maximum_scroll()
        left = self.scroll_button_width() if self.scroll_offset > 0 else 0
        right = self.scroll_button_width() if self.scroll_offset < maximum else 0
        return self.rect().adjusted(left, 0, -right, 0)

    def tabRect(self, index):
        if not 0 <= index < self.count() or not self.isTabVisible(index):
            return self.rect().adjusted(0, 0, -self.width(), -self.height())
        x = self.tab_viewport().left() - self.scroll_offset
        x += sum(self.tabSizeHint(i).width() for i in range(index) if self.isTabVisible(i))
        return self.rect().adjusted(x, 0, x + self.tabSizeHint(index).width() - self.width(), 0)

    def tabAt(self, position):
        if self.tab_viewport().contains(position):
            return next((index for index in range(self.count()) if self.tabRect(index).contains(position)), -1)
        return -1

    def minimumSizeHint(self):
        return QSize(3 * self.scroll_button_width(), self.tabSizeHint(0).height())

    def update_scroll_buttons(self):
        if not hasattr(self, 'scroll_left'):
            return
        self.hide_native_scroll_buttons()
        maximum = self.maximum_scroll()
        self.scroll_offset = max(0, min(self.scroll_offset, maximum))
        width = self.scroll_button_width()
        self.scroll_left.setGeometry(0, 0, width, self.height())
        self.scroll_right.setGeometry(self.width() - width, 0, width, self.height())
        self.scroll_left.setVisible(self.scroll_offset > 0)
        self.scroll_right.setVisible(self.scroll_offset < maximum)
        self.scroll_left.raise_()
        self.scroll_right.raise_()
        self.update()

    def scroll_tabs(self, direction):
        step = max(1, round(self.tab_viewport().width() * .75))
        self.scroll_offset = max(0, min(self.maximum_scroll(), self.scroll_offset + direction * step))
        self.update_scroll_buttons()

    def ensure_current_visible(self, index=None):
        index = self.currentIndex() if index is None else index
        if 0 <= index < self.count():
            for _ in range(2):
                rect = self.tabRect(index)
                viewport = self.tab_viewport()
                if rect.left() < viewport.left():
                    self.scroll_offset += rect.left() - viewport.left()
                elif rect.right() > viewport.right():
                    self.scroll_offset += rect.right() - viewport.right()
                self.scroll_offset = max(0, min(self.maximum_scroll(), self.scroll_offset))
        self.update_scroll_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scroll_buttons()
        self.ensure_current_visible()

    def tabLayoutChange(self):
        super().tabLayoutChange()
        if self.usesScrollButtons():
            self.setUsesScrollButtons(False)
        if hasattr(self, 'scroll_update_timer'):
            self.scroll_update_timer.start(0)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        index = self.tabAt(event.position().toPoint())
        if index >= 0 and self.isTabEnabled(index):
            self.setFocus(Qt.MouseFocusReason)
            self.setCurrentIndex(index)
            self.tabBarClicked.emit(index)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().x() or event.angleDelta().y()
        if delta and self.maximum_scroll():
            self.scroll_tabs(-1 if delta > 0 else 1)
            event.accept()
        else:
            event.ignore()

    def play_tab_sound(self, index):
        if index >= 0 and self.isTabEnabled(index):
            play_button_sound()

    def keyPressEvent(self, event):
        previous = self.currentIndex()
        super().keyPressEvent(event)
        if self.currentIndex() != previous:
            play_button_sound()

    def tabSizeHint(self, index):
        width = round((button_font_metrics(self).horizontalAdvance(self.tabText(index)) + 36) * button_scale()) + 2 * CONTROL_HEADROOM
        return QSize(min(width, self.property('maximumTabWidth') or width), round(50 * button_scale()) + CONTROL_HEADROOM + 2 * (BUTTON_SHADOW - 3))

    def tab_face_rect(self, index):
        outer = QRectF(self.tabRect(index)).adjusted(3, BUTTON_SHADOW, -5, -BUTTON_SHADOW)
        outer.translate(0, -CONTROL_HEADROOM / 2)
        return outer

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        app = QApplication.instance()
        painter.fillRect(self.rect(), QColor(app.property('themeBackground') or BUILDING_GRAY))
        painter.setClipRect(self.tab_viewport())
        for index in range(self.count()):
            if not self.isTabVisible(index):
                continue
            selected = index == self.currentIndex()
            accent = QColor(app.property('themeHighlight' if selected else 'themeAccent') or GRASS_GREEN)
            outer = self.tab_face_rect(index)
            painter.setPen(Qt.NoPen)
            face = paint_control(painter, self, outer, accent, shadow=True)
            painter.setPen(QColor(app.property('buttonTextColor') or '#4c3f2f'))
            painter.setFont(self.font())
            painter.save()
            clip = QPainterPath()
            radius = corner_radius(12, face.width(), face.height())
            clip.addRoundedRect(face, radius, radius)
            painter.setClipPath(clip, Qt.IntersectClip)
            draw_centered_text(painter, button_text_rect(face), button_text_font(self), self.tabText(index),
                               button_text_color(accent, self.isEnabled(), highlighted=True) if selected else
                               app.property('buttonTextColor') or '#4c3f2f', fit=True)
            painter.restore()


class ThemedMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMouseTracking(True)
        self.update_style(QPointF())

    def update_style(self, offset):
        size = button_text_font(self).pixelSize()
        self.setStyleSheet(f'''
QMenu {{ background: transparent; border: none; font-size: {size}px;
    padding: {CONTROL_HEADROOM + 6 - offset.y() + BUTTON_SHADOW:g}px {CONTROL_HEADROOM + 6 + offset.x():g}px
             {6 + offset.y() + BUTTON_SHADOW:g}px {CONTROL_HEADROOM + 6 - offset.x():g}px; }}
QMenu::item {{ padding: 8px 14px; background: transparent; }}
''')

    def showEvent(self, event):
        self.update_style(control_offset(self, button_paint_rect(self), ui_depth()))
        super().showEvent(event)

    def paintEvent(self, event):
        app = QApplication.instance()
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.Antialiasing)
        background = QColor(app.property('themeBackground') or BUILDING_GRAY).darker(110)
        paint_control(painter, self, button_paint_rect(self), background)
        painter.setFont(button_text_font(self))
        for action in self.actions():
            if not action.isVisible():
                continue
            rect = self.actionGeometry(action).adjusted(14, 0, -14, 0)
            if action.isSeparator():
                painter.setPen(QPen(QColor(app.property('themeAccent') or GRASS_GREEN), 1))
                painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
                continue
            color = QColor(app.property('textColor') or '#ffffff')
            painter.setPen(color if action.isEnabled() else disabled_text_color(color))
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeading, action.text())
            if action is self.activeAction() and action.isEnabled():
                painter.setPen(QPen(QColor(app.property('themeAccent') or GRASS_GREEN), 3, Qt.SolidLine, Qt.FlatCap))
                width = min(rect.width(), painter.fontMetrics().horizontalAdvance(action.text()))
                y = min(rect.bottom() - 3, rect.center().y() + painter.fontMetrics().height() / 2 + 1)
                left = rect.right() - width if self.layoutDirection() == Qt.RightToLeft else rect.left()
                painter.drawLine(QPointF(left, y), QPointF(left + width, y))


class DropdownDelegate(QStyledItemDelegate):
    """Plain menu text with the file browser's three-pixel underline."""

    def sizeHint(self, option, index):
        font = self.parent().fontMetrics()
        return QSize(font.horizontalAdvance(str(index.data() or '')) + 24, font.height() + 18)

    def paint(self, painter, option, index):
        app = QApplication.instance()
        painter.save()
        painter.setFont(self.parent().font())
        painter.setPen(QColor(app.property('textColor') or '#ffffff'))
        rect = option.rect.adjusted(10, 0, -10, 0)
        text = option.fontMetrics.elidedText(str(index.data() or ''), Qt.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeading, text)
        view = self.parent()
        mouse = view.viewport().mapFromGlobal(QCursor.pos())
        hovered = view.indexAt(mouse) if view.viewport().rect().contains(mouse) and not view.property('keyboardNavigation') else None
        underline = (hovered == index if hovered is not None and hovered.isValid()
                     else bool(option.state & QStyle.State_Selected))
        if underline:
            painter.setPen(QPen(QColor(app.property('themeAccent') or GRASS_GREEN), 3, Qt.SolidLine, Qt.FlatCap))
            width = min(rect.width(), option.fontMetrics.horizontalAdvance(text))
            y = min(rect.bottom() - 3, rect.center().y() + option.fontMetrics.height() / 2 + 1)
            left = rect.right() - width if option.direction == Qt.RightToLeft else rect.left()
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))
        painter.restore()


@local_control_theme
class ThemedComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep this independent of Qt's private combo popup: that container
        # clamps its height and adds mouse-edge scrolling on Windows.
        self.popup = None
        self.popup_position_timer = QTimer(self)
        self.popup_position_timer.setSingleShot(True)
        self.popup_position_timer.timeout.connect(self.position_popup)
        self.menu_view = QListView(self)
        self.menu_view.setObjectName('albumDriveDropdownView')
        self.menu_view.hide()
        self.menu_view.setAutoScroll(False)
        self.menu_view.clicked.connect(self.choose_menu_index)
        self.menu_view.installEventFilter(self)
        self.menu_view.viewport().installEventFilter(self)
        self.setStyleSheet('QComboBox { combobox-popup: 0; }')
        self.setMaxVisibleItems(10)
        self.view().setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.view().setItemDelegate(DropdownDelegate(self.view()))
        self.view().setMouseTracking(True)
        self.view().viewport().setMouseTracking(True)
        self.popup = None
        button_text_sizing().register(self)
        self.currentTextChanged.connect(button_text_sizing().schedule)

    def button_text_regions(self):
        face = control_face(button_paint_rect(self), widget=self)
        return [(button_text_rect(face, dropdown=True), (self.currentText(),))]

    def sync_popup_font(self):
        size = button_text_font(self).pixelSize()
        if self.menu_view.property('sharedButtonTextSize') != size:
            self.menu_view.setProperty('sharedButtonTextSize', size)
            self.menu_view.setStyleSheet(f'QListView {{ background: transparent; border: none; outline: none; font-size: {size}px; }}')

    def view(self):
        return self.menu_view

    def choose_menu_index(self, index):
        if not index.isValid() or not index.flags() & Qt.ItemIsEnabled:
            return
        self.hidePopup()
        self.setCurrentIndex(index.row())
        self.activated.emit(index.row())
        self.textActivated.emit(self.currentText())

    def hidePopup(self):
        self.popup_position_timer.stop()
        if self.popup is not None:
            self.popup.hide()
        super().hidePopup()
        self.update()

    def hideEvent(self, event):
        self.hidePopup()
        super().hideEvent(event)

    def showPopup(self):
        if not self.isEnabled() or not self.count():
            return
        if self.popup is not None and self.popup.isVisible():
            self.hidePopup()
            return
        play_button_sound()
        app = QApplication.instance()
        view = self.view()
        if self.popup is None:
            self.popup = QFrame(self, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            layout = QVBoxLayout(self.popup)
            layout.setSpacing(0)
            view.setParent(self.popup)
            layout.addWidget(view)
            self.popup.setAttribute(Qt.WA_TranslucentBackground)
            self.popup.setAttribute(Qt.WA_NoSystemBackground)
            self.popup.setAttribute(Qt.WA_NoMouseReplay)
            self.popup.setAutoFillBackground(False)
            self.popup.setObjectName('albumDriveDropdown')
            self.popup.setStyleSheet('QFrame#albumDriveDropdown { background: transparent; border: none; }')
            self.popup.setFrameShape(QFrame.NoFrame)
            self.popup.installEventFilter(self)
        self.popup.setUpdatesEnabled(False)
        if self.popup.layout():
            self.popup.layout().setSizeConstraint(QLayout.SetNoConstraint)
            self.popup.layout().setContentsMargins(CONTROL_HEADROOM + 6, CONTROL_HEADROOM + 6 + BUTTON_SHADOW,
                                                  CONTROL_HEADROOM + 6, 6 + BUTTON_SHADOW)
        self.sync_popup_font()
        view.viewport().setAutoFillBackground(False)
        view.setModel(self.model())
        view.setModelColumn(self.modelColumn())
        view.setRootIndex(self.rootModelIndex())
        view.setCurrentIndex(self.model().index(self.currentIndex(), self.modelColumn(), self.rootModelIndex()))
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        view.show()
        self.popup.show()
        self.position_popup()
        view.setFocus(Qt.PopupFocusReason)
        self.popup.setUpdatesEnabled(True)
        self.popup_position_timer.start(0)

    def position_popup(self):
        if self.popup is None or not self.popup.isVisible():
            return
        available = self.screen().availableGeometry()
        origin = self.mapToGlobal(QPoint(0, self.height() + 2))
        row_height = max(self.view().sizeHintForRow(0), self.view().fontMetrics().height() + 18)
        margin = CONTROL_HEADROOM + 16 + 2 * BUTTON_SHADOW
        desired = row_height * min(self.count(), self.maxVisibleItems()) + margin
        below = available.bottom() - origin.y() + 1
        button_top = self.mapToGlobal(QPoint()).y() - 2
        above = button_top - available.top()
        if below >= desired or below >= above:
            height = min(desired, below)
            y = origin.y()
        else:
            height = min(desired, max(1, above))
            y = button_top - height
        width = min(available.width(), max(self.width(), self.view().sizeHintForColumn(0) + margin + 24 + CONTROL_HEADROOM))
        x = max(available.left(), min(origin.x(), available.right() - width + 1))
        self.popup.setMinimumSize(0, 0)
        self.popup.setMaximumSize(16777215, 16777215)
        self.popup.setGeometry(x, y, width, min(height, available.bottom() - y + 1))
        padding = 6
        offset = control_offset(self.popup, QRectF(self.popup.rect()), ui_depth())
        self.popup.layout().setContentsMargins(round(padding + CONTROL_HEADROOM - offset.x()),
                                              round(padding + CONTROL_HEADROOM - offset.y()) + BUTTON_SHADOW,
                                              round(padding + CONTROL_HEADROOM + offset.x()),
                                              round(padding + offset.y()) + BUTTON_SHADOW)
        path = QPainterPath()
        radius = corner_radius(12, width, height)
        path.addRoundedRect(QRectF(self.popup.rect()), radius, radius)
        self.popup.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self.view().scrollToTop()
        self.view().scrollTo(self.model().index(self.currentIndex(), self.modelColumn(), self.rootModelIndex()),
                             QAbstractItemView.EnsureVisible)

    def eventFilter(self, watched, event):
        if watched is self.menu_view or watched is self.menu_view.viewport():
            if event.type() == QEvent.KeyPress:
                self.menu_view.setProperty('keyboardNavigation', True)
                self.menu_view.viewport().update()
            elif event.type() == QEvent.MouseMove and self.menu_view.property('keyboardNavigation'):
                self.menu_view.setProperty('keyboardNavigation', False)
                self.menu_view.viewport().update()
        if watched is self.menu_view and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.choose_menu_index(self.menu_view.currentIndex())
                return True
            if event.key() == Qt.Key_Escape:
                self.hidePopup()
                self.setFocus(Qt.PopupFocusReason)
                return True
        if watched is self.popup and event.type() == QEvent.Paint:
            app = QApplication.instance()
            painter = QPainter(watched)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(watched.rect(), Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            outer = button_paint_rect(watched)
            background = QColor(app.property('themeBackground') or BUILDING_GRAY).darker(110)
            paint_control(painter, watched, outer, background)
            painter.end()
            return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event):
        scroll_past_control(self, event)

    def minimumSizeHint(self):
        metrics = button_font_metrics(self)
        width = max((metrics.horizontalAdvance(self.itemText(index)) for index in range(self.count())), default=0)
        return QSize(round(max(160, width + 56) * button_scale()) + 2 * CONTROL_HEADROOM,
                     round(44 * button_scale()) + CONTROL_HEADROOM + 2 * BUTTON_SHADOW)

    def sizeHint(self):
        return self.minimumSizeHint()

    def paintEvent(self, event):
        app = QApplication.instance()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outer = button_paint_rect(self)
        accent = QColor(app.property('themeAccent') or GRASS_GREEN)
        painter.setPen(Qt.NoPen)
        face = paint_control(painter, self, outer, accent, shadow=True)
        clip = QPainterPath()
        radius = corner_radius(12, face.width(), face.height())
        clip.addRoundedRect(face, radius, radius)
        painter.setClipPath(clip, Qt.IntersectClip)
        color = QColor(app.property('buttonTextColor') or '#4c3f2f')
        if not self.isEnabled():
            color = disabled_text_color(color)
        draw_centered_text(painter, button_text_rect(face, dropdown=True), button_text_font(self), self.currentText(), color, fit=True)
        arrow = QPainterPath()
        x, y = face.right() - 16, face.center().y()
        arrow.moveTo(x-4, y-2)
        arrow.lineTo(x, y+2)
        arrow.lineTo(x+4, y-2)
        painter.setPen(QPen(color, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(arrow)


class ColorSwatch(ThemedButton):
    colorChanged = Signal(str)

    def __init__(self, color, label, parent=None):
        super().__init__('', parent)
        self.setMinimumWidth(120 + 2 * CONTROL_HEADROOM)
        self.setAccessibleName(label)
        self.setToolTip(f'Choose {label.lower()}')
        self.set_color(color)

    def set_color(self, color):
        color = QColor(color)
        if color.isValid() and color.name() != self.property('swatchColor'):
            self.setProperty('swatchColor', color.name())
            self.update()
            self.colorChanged.emit(color.name())

    def color(self):
        return QColor(self.property('swatchColor'))


def chunky_style(base, accent=GRASS_GREEN, background=BUILDING_GRAY, timeline=TIMELINE_COLOR, roundness=100):
    color = QColor(accent)
    if not color.isValid():
        color = QColor('#ff9800')
    accent = color.name()
    app = QApplication.instance()
    fill = app.property('buttonFill') if app is not None else None
    assets = accent_assets(accent, roundness, fill=fill or '#cccccc', depth=ui_depth())
    background_color = QColor(background)
    background = background_color.name() if background_color.isValid() else BUILDING_GRAY
    timeline_assets = accent_assets(timeline, roundness, fill=fill or '#cccccc', depth=ui_depth())
    # Keep the surfaces related to the sampled building gray.
    for original, replacement in {
        '#16191e': background,
        '#1c2128': QColor(background).darker(110).name(),
        '#191d23': QColor(background).darker(119).name(),
        '#222831': QColor(background).darker(115).name(),
        '#242b32': QColor(background).darker(110).name(),
        '#262e38': QColor(background).darker(120).name(),
        '#303945': QColor(background).lighter(115).name(),
        '#38424d': QColor(background).darker(130).name(),
        '#94a0ae': '#d0dce2',
    }.items():
        base = base.replace(original, replacement)
    return base + """
QLabel#brand { color: #ff9800; }
QPushButton, QPushButton#play {
    background: transparent; color: #352719;
    border: none; border-radius: 0px;
    padding: 10px 20px; min-height: 24px; font-weight: 700;
}
QPushButton:hover, QPushButton#play:hover { color: #b84c00; }
QPushButton:focus, QPushButton#play:focus { color: #a44100; text-decoration: underline; }
QPushButton:pressed, QPushButton#play:pressed {
    padding-top: 4px; padding-bottom: 0px; color: #b84c00;
}
QPushButton:disabled, QPushButton#play:disabled { color: #929292; }
QPushButton#previous, QPushButton#next {
    padding: 0px 14px; min-height: 0px;
}
QLineEdit { border: 2px solid #73502c; padding: 9px; }
QLineEdit:focus { border-color: #ff9800; }
QTreeView::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
    background: #67401e; color: #ffffff;
}
QListWidget::item:hover { background: #352a20; }
QSlider:horizontal { min-height: 48px; }
QSlider#timeline { min-height: 60px; }
QSlider::groove:horizontal {
    height: 8px; background: #38424d; border-radius: 4px;
}
QSlider::sub-page:horizontal { background: #ff9800; border-radius: 4px; }
QSlider::handle:horizontal {
    image: url("ASSETS/slider-knob.svg");
    background: transparent; border: none; border-radius: 0px;
    width: 48px; height: 36px; margin: -20px 0 -8px 0;
}
QSlider::handle:horizontal:hover { background: transparent; }
QSlider::sub-page:horizontal:disabled { background: #68727e; }
QSlider#timeline::handle:horizontal {
    image: none; background: transparent; border: none;
    border-image: url("ASSETS/timeline-knob.svg") 0 0 0 0 stretch stretch;
    width: 60px; height: 48px; margin: -14px 0 -2px 0; border-radius: 0px;
}
QScrollBar:vertical {
    background: transparent; width: 48px; margin: 0px;
}
QScrollBar:horizontal {
    background: transparent; height: 36px; margin: 0px;
}
QScrollBar::handle {
    background: transparent; border: 12px solid transparent;
    border-image: url("ASSETS/button-rounded.svg") 12 12 12 12 stretch stretch;
}
QScrollBar::handle:vertical { min-height: 36px; }
QScrollBar::handle:horizontal { min-width: 48px; }
QScrollBar::sub-page:vertical {
    background: #38424d; margin: 0px 8px; border-radius: 2px;
}
QScrollBar::add-page:vertical {
    background: #ff9800; margin: -6px 8px 0px 8px; border-radius: 2px;
}
QScrollBar::sub-page:horizontal {
    background: #ff9800; margin: 8px 0px; border-radius: 2px;
}
QScrollBar::add-page:horizontal {
    background: #38424d; margin: 8px 0px; border-radius: 2px;
}
QScrollBar::add-line,
QScrollBar::sub-line { width: 0px; height: 0px; background: transparent; border: none; }
QAbstractScrollArea::corner { background: #1c2128; }
QMenuBar { background: #1c2128; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected, QMenu::item:selected { background: #67401e; }
QMenu { background: #222831; border: 1px solid #73502c; }
QMenu::item { padding: 8px 24px; }
QHeaderView::down-arrow { image: url("ASSETS/arrow.svg"); width: 14px; height: 10px; }
QWidget { selection-background-color: #67401e; selection-color: #ffffff; }
""".replace('ASSETS', assets).replace(
        f'{assets}/timeline-knob.svg', f'{timeline_assets}/timeline-knob.svg').replace('#ff9800', accent).replace(
        '#67401e', accent_shade(accent, 0.32)).replace('#352a20', accent_shade(accent, 0.12)).replace(
        '#73502c', accent_shade(accent, 0.45)).replace('#b84c00', color.darker(160).name()).replace(
        '#a44100', color.darker(180).name()).replace('#1c2128', QColor(background).darker(110).name()).replace(
        '#222831', QColor(background).darker(115).name()).replace('#38424d', QColor(background).darker(130).name()) + SCROLLBAR_STYLE
