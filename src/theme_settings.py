"""Library, audio and appearance settings with saved color themes and Apply/Cancel."""

from pathlib import Path
import json
from uuid import uuid4
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QIconEngine, QPainter, QPen, QPixmap, QResizeEvent
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt, Signal, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QStyle, QTabWidget, QVBoxLayout, QWidget

from themes import signed_setting_int, resolve_font, THEME_DEFAULT, CLEANING_DEFAULT, COLOR_SETTINGS, NUMERIC_DEFAULTS, ChunkyCheckBox, ChunkyTabBar, ColorSwatch, ThemedButton, ThemedComboBox, ThemeSlider
from themes import ARTWORK_THEME_DEFAULT, ARTWORK_THEME_MODE_DEFAULT, UI_FONT_DEFAULT, MARKER_COLOR_DEFAULT
from settings_store import read_theme_files, write_theme_files
from color_picker import ColorPickerDialog
from color_rules import disabled_text_color
from themes import MERGED_NUMERIC_SETTINGS, MERGED_COLOR_SETTINGS
from themes import PRIMARY_COLOR_KEYS, CONTROL_HEADROOM, BUTTON_SHADOW, MAX_FONT_SIZE, FONT_SCALE_KEYS, button_scale, button_text_sizing, local_control_theme, migrate_button_size, migrate_font_settings
from app_theme import simplify_color_settings, soften_theme_colors
from scroll_shadows import paint_scroll_background


def custom_color_settings(settings):
    """Keep the user's base palette independent of selected album presets."""
    try:
        stored = json.loads(str(settings.value('custom_theme_colors', '{}')))
        if not isinstance(stored, dict):
            stored = {}
    except (ValueError, TypeError):
        stored = {}
    legacy_colors = {key: str(settings.value(key, default)) for _, _, key, _, default in COLOR_SETTINGS}
    legacy_colors['theme_background_accent_color'] = str(settings.value(
        'theme_background_accent_color', settings.value('theme_accent_color', '#cfe10e')))
    legacy_preset = not stored and any(
        all(preset['colors'][key] == color for key, color in legacy_colors.items() if key != 'theme_highlight_color')
        for preset in saved_color_themes(settings))
    colors = {}
    for _, _, key, _, default in COLOR_SETTINGS:
        # Older versions replaced these keys with preset colors. With a preset
        # selected, only a separately saved base palette can be recovered.
        fallback = default if settings.value('selected_color_theme', '') or legacy_preset else legacy_colors[key]
        migrated = stored.get(key)
        if key == 'theme_background_accent_color' and migrated is None:
            migrated = stored.get('theme_accent_color', legacy_colors[key])
        color = QColor(str(migrated if migrated is not None else fallback))
        colors[key] = color.name() if color.isValid() else default
    for alias, canonical in MERGED_COLOR_SETTINGS.items():
        colors[alias] = colors[canonical]
    return simplify_color_settings(colors)


def default_color_theme():
    return {'id': 'album-drive-default', 'name': 'Default',
            'colors': {key: default for _, _, key, _, default in COLOR_SETTINGS}}


def capture_color_theme(presets, name):
    app = QApplication.instance()
    existing = {preset['name'] for preset in presets}
    original = name
    suffix = 2
    while name in existing:
        name = f'{original} ({suffix})'
        suffix += 1
    colors = {key: str(app.property(prop) or default) for _, _, key, prop, default in COLOR_SETTINGS}
    return {'id': uuid4().hex, 'name': name, 'colors': colors, 'preserve_palette': True}


def saved_color_themes(settings):
    """Read portable preset data without trusting malformed preferences."""
    try:
        presets = getattr(settings, '_preview_color_themes', None)
        if presets is None:
            presets = read_theme_files(settings)
        if presets is None:
            presets = json.loads(str(settings.value('saved_color_themes', '[]')))
        if not isinstance(presets, list):
            return [default_color_theme()]
        keys = {key for _, _, key, _, _ in COLOR_SETTINGS}
        result = [default_color_theme()]
        for preset in presets:
            if not (isinstance(preset, dict)
                and preset.get('id') != 'album-drive-default'
                and isinstance(preset.get('id'), str) and isinstance(preset.get('name'), str)
                and isinstance(preset.get('colors'), dict)):
                continue
            colors = dict(preset['colors'])
            colors.setdefault('theme_highlight_color', colors.get('theme_brand_text_color', '#cfe10e'))
            colors.setdefault('theme_background_accent_color', colors.get('theme_accent_color', '#cfe10e'))
            if keys <= colors.keys() and all(isinstance(colors[key], str) and QColor(colors[key]).isValid() for key in keys):
                result.append({key: preset[key] for key in ('id', 'name', 'preserve_palette') if key in preset} | {'colors': colors})
        return result
    except (ValueError, TypeError):
        return [default_color_theme()]


NUMERIC_SETTINGS = (
    ('Colors', 'Theme fade duration', 'theme_fade_seconds', NUMERIC_DEFAULTS['theme_fade_seconds'], 0, 5, ' s', .1),
    ('Appearance', 'Button size', 'button_size', NUMERIC_DEFAULTS['button_size'], 20, 72, ' px', 1),
    ('Appearance', 'Button thickness', 'ui_thickness', NUMERIC_DEFAULTS['ui_thickness'], 0, 300, ' px', 25),
    ('Appearance', 'Button icon size', 'button_icon_size', NUMERIC_DEFAULTS['button_icon_size'], 8, 96, ' px', 1),
    ('Appearance', 'Button text size', 'button_font_size', NUMERIC_DEFAULTS['button_font_size'], 8, 30, ' px', 1),
    ('General', 'Button sound volume', 'button_sound_volume', NUMERIC_DEFAULTS['button_sound_volume'], 0, 100, ' %', 1),
    ('General', 'CD case opening volume', 'case_open_volume', NUMERIC_DEFAULTS['case_open_volume'], 0, 100, ' %', 1),
    ('General', 'CD case closing volume', 'case_close_volume', NUMERIC_DEFAULTS['case_close_volume'], 0, 100, ' %', 1),
    ('Text', 'Track list text size', 'track_list_font_size', NUMERIC_DEFAULTS['track_list_font_size'], 12, 48, ' px', 1),
    ('Appearance', 'Track list vertical spacing', 'track_list_vertical_spacing', NUMERIC_DEFAULTS['track_list_vertical_spacing'], -32, 48, ' px', 1),
    ('Appearance', 'File browser vertical spacing', 'folder_vertical_spacing', NUMERIC_DEFAULTS['folder_vertical_spacing'], -12, 40, ' px', 1),
    ('Appearance', 'Settings vertical spacing', 'settings_vertical_spacing', NUMERIC_DEFAULTS['settings_vertical_spacing'], -40, 40, ' px', 1),
    ('Appearance', 'Hover tilt', 'hover_rotation', NUMERIC_DEFAULTS['hover_rotation'], 0, 45, '°', 0.1),
    ('Appearance', 'Hover enlargement', 'hover_growth', NUMERIC_DEFAULTS['hover_growth'], 0, 20, ' %', 0.5),
    ('Appearance', 'Hover lift', 'hover_lift', NUMERIC_DEFAULTS['hover_lift'], 0, 40, ' px', 1),
    ('Appearance', 'Horizontal spacing', 'album_horizontal_spacing', NUMERIC_DEFAULTS['album_horizontal_spacing'], 0, 50, ' px', 1),
    ('Appearance', 'Vertical spacing', 'album_vertical_spacing', NUMERIC_DEFAULTS['album_vertical_spacing'], 0, 50, ' px', 1),
)

TEXT_SIZES = {
    'main_font_size': 'General text size',
    'secondary_font_size': 'Album count and status text',
    'logo_font_size': 'Album Drive logo text size',
    'folder_font_size': 'Folder text size',
    'dropdown_font_size': 'Dropdown text',
    'menu_font_size': 'Menus and tooltips',
    'settings_heading_font_size': 'Settings heading text size',
    'handwriting_font_size': 'Missing-art title text size',
}
NUMERIC_SETTINGS += tuple(('Text', label, key, NUMERIC_DEFAULTS[key],
                           8, 64 if key in ('logo_font_size', 'handwriting_font_size') else 40, ' px', 1)
                          for key, label in TEXT_SIZES.items())


SECTION_GAP = 20
SETTING_INDENT = 16
SETTING_LABEL_WIDTH = 320


class SettingsSectionLabel(QLabel):
    def paintEvent(self, event):
        app = QApplication.instance()
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(QColor(app.property('textColor') or '#ffffff'))
        painter.drawText(self.contentsRect(), Qt.AlignLeft | Qt.AlignVCenter, self.text())


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet('QWidget[settingsRow="true"], QLabel, QSlider, QCheckBox { background: transparent; }')

    def paintEvent(self, event):
        background = QColor(QApplication.instance().property('themeBackground') or '#393939')
        painter = QPainter(self)
        painter.fillRect(self.rect(), background)
        painter.setRenderHint(QPainter.Antialiasing)
        form = self.layout()
        sections = []
        bounds = QRect()
        active = False
        for row in range(form.rowCount()):
            items = [form.itemAt(row, role) for role in (QFormLayout.LabelRole, QFormLayout.FieldRole)]
            widgets = [item.widget() for item in items if item is not None and item.widget() is not None]
            if any(widget.objectName() == 'settingsSectionSpacer' for widget in widgets):
                continue
            if any(widget.objectName() == 'settingsSection' for widget in widgets):
                if not bounds.isNull():
                    sections.append(bounds)
                    bounds = QRect()
                active = True
            if not active:
                continue
            for widget in widgets:
                bounds = bounds.united(widget.geometry())
        if not bounds.isNull():
            sections.append(bounds)
        shade = QColor(255, 255, 255, 14) if background.lightnessF() < .45 else QColor(0, 0, 0, 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shade)
        for index, bounds in enumerate(sections):
            if index % 2:
                painter.drawRoundedRect(QRectF(8, bounds.top() - 6, self.width() - 16, bounds.height() + 12), 8, 8)
        paint_scroll_background(painter, self)


class SettingsFormLayout(QFormLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setHorizontalSpacing(16)
        self.row_spacing = 0
        self.base_geometries = []

    def setVerticalSpacing(self, spacing):
        self.row_spacing = spacing
        super().setVerticalSpacing(max(0, spacing))
        self.invalidate()

    def verticalSpacing(self):
        return self.row_spacing

    def row_offsets(self):
        offsets = [0]
        for row in range(max(0, self.rowCount() - 1)):
            items = [self.itemAt(row, role) for role in (QFormLayout.LabelRole, QFormLayout.FieldRole)]
            height = max((item.sizeHint().height() for item in items if item is not None), default=0)
            section = any(item is not None and item.widget() is not None
                          and item.widget().objectName() in ('settingsSection', 'settingsSectionSpacer') for item in items)
            following = self.itemAt(row + 1, QFormLayout.SpanningRole)
            section = section or (following is not None and following.widget() is not None
                                  and following.widget().objectName() == 'settingsSectionSpacer')
            offsets.append(offsets[-1] + (0 if section else max(min(0, self.row_spacing), min(0, 1 - height))))
        return offsets

    def sizeHint(self):
        size = super().sizeHint()
        size.setWidth(size.width() + SETTING_INDENT)
        size.setHeight(max(0, size.height() + self.row_offsets()[-1]))
        return size

    def minimumSize(self):
        size = super().minimumSize()
        size.setWidth(size.width() + SETTING_INDENT)
        size.setHeight(max(0, size.height() + self.row_offsets()[-1]))
        return size

    def heightForWidth(self, width):
        height = super().heightForWidth(max(0, width - SETTING_INDENT))
        return max(0, height + self.row_offsets()[-1]) if height >= 0 else height

    def setGeometry(self, rect):
        for index, geometry in enumerate(self.base_geometries[:self.count()]):
            self.itemAt(index).setGeometry(geometry)
        offsets = self.row_offsets()
        super().setGeometry(rect.adjusted(SETTING_INDENT, 0, 0, -offsets[-1]))
        self.base_geometries = [self.itemAt(index).geometry() for index in range(self.count())]
        for index, geometry in enumerate(self.base_geometries):
            row, _ = self.getItemPosition(index)
            widget = self.itemAt(index).widget()
            if widget is not None and widget.objectName() in ('settingsSection', 'settingsSectionSpacer'):
                geometry = geometry.adjusted(-SETTING_INDENT, 0, 0, 0)
            self.itemAt(index).setGeometry(geometry.translated(0, offsets[row]))
        for row in range(self.rowCount()):
            label = self.itemAt(row, QFormLayout.LabelRole)
            field = self.itemAt(row, QFormLayout.FieldRole)
            if label is not None and field is not None and label.geometry().right() < field.geometry().left():
                geometry = label.geometry()
                geometry.moveCenter(QPoint(geometry.center().x(), field.geometry().center().y()))
                label.setGeometry(geometry)


class NumericSlider(QWidget):
    def __init__(self, default, low, high, suffix, step, display_scale=1, display_offset=0):
        super().__init__()
        self.setProperty('settingsRow', True)
        self.fractional = isinstance(default, float)
        self.display_offset = display_offset
        self.display_scale = display_scale
        self.factor = (10 if self.fractional else 1) * display_scale
        self.suffix = suffix
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = ThemeSlider()
        self.slider.setRange(round(low * self.factor), round(high * self.factor))
        self.slider.setSingleStep(max(1, round(step * self.factor)))
        self.label = QLabel()
        self.label.setFixedWidth(84)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider.valueChanged.connect(self.update_label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.label)
        self.setValue(default)

    def update_label(self):
        self.label.setText(f'{(self.value() - self.display_offset) * self.display_scale:g}{self.suffix}')

    def value(self):
        value = self.slider.value() / self.factor
        return value if self.fractional else int(value)

    def maximum(self):
        return self.slider.maximum() / self.factor

    def setValue(self, value):
        self.slider.setValue(round(value * self.factor))
        self.update_label()


class SettingResetIcon(QIconEngine):
    def clone(self):
        return SettingResetIcon()

    def paint(self, painter, rect, mode, state):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.topLeft())
        painter.scale(rect.width() / 32, rect.height() / 32)
        app = QApplication.instance()
        color = QColor(app.property('buttonIconColor') or '#101010')
        if mode == QIcon.Disabled:
            color = disabled_text_color(color)
        painter.setPen(QPen(QColor(color), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(6, 6, 20, 20), 160 * 16, -300 * 16)
        painter.drawLine(7, 5, 6, 13)
        painter.drawLine(6, 13, 14, 13)
        painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


@local_control_theme
class SettingResetButton(ThemedButton):
    def __init__(self, label):
        super().__init__('')
        self.setIcon(QIcon(SettingResetIcon()))
        self.setIconSize(QSize(20, 20))
        self.setAccessibleName(f'Reset {label.lower()} to default')
        self.setToolTip(self.accessibleName())
        self.setAutoDefault(False)
        self.setStyleSheet('QPushButton { padding: 0; min-height: 0; min-width: 0; }')
        policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)

    def sizeHint(self):
        size = max(20, round(24 * button_scale()))
        return QSize(size + 2 * CONTROL_HEADROOM, size + CONTROL_HEADROOM + 2 * BUTTON_SHADOW)


class SettingsDismissClick(QObject):
    """Consume the release too, so closing settings cannot close an album."""
    def __init__(self, window, button):
        super().__init__(QApplication.instance())
        self.window = window
        self.button = button
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish)
        QApplication.instance().installEventFilter(self)
        self.timer.start(2000)

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.MouseButtonRelease and event.button() == self.button
                and isinstance(watched, QWidget) and watched.window() is self.window):
            self.finish()
            return True
        return False

    def finish(self):
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.deleteLater()


@local_control_theme
class ThemeSettingsDialog(QDialog):
    applied = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName('themeSettings')
        migrate_button_size(settings)
        migrate_font_settings(settings)
        self.original_settings = {key: settings.value(key) for key in settings.allKeys()}
        self.preview_keys = set(NUMERIC_DEFAULTS) | {key for _, _, key, _, _ in COLOR_SETTINGS} | {
            'theme', 'artwork_theme_enabled', 'artwork_theme_mode', 'selected_color_theme',
            'audio_output_device', 'continuous_playback', 'ui_font',
            'i_like_cleaning', 'folder', 'browser_root', 'custom_theme_colors', 'custom_theme_options',
            'welcome_complete', 'welcome_started', 'marker_text_color'}
        self.preview_keys.update(FONT_SCALE_KEYS.values())
        self.transaction_open = True
        self.previewing = False
        self.preview_applied = False
        self.active_sliders = set()
        self.slider_preview_pending = False
        self.preview_stylesheet = None
        self.restoring = False
        self.original_library_state = (parent.files.filePath(parent.tree.rootIndex()), parent.current_folder) if parent is not None and hasattr(parent, 'files') else None
        self.presets = saved_color_themes(settings)
        self.persisted_presets = json.dumps(self.presets, sort_keys=True)
        self.custom_colors = custom_color_settings(settings)
        self.reset_album_size = False
        self.reset_font_scales = False
        self.setWindowTitle('Settings')
        self.resize(1040, 680)
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.tabs.setTabBar(ChunkyTabBar(self.tabs))
        self.tabs.tabBar().setProperty('maximumTabWidth', 300)
        outer.addWidget(self.tabs)
        forms = {}
        for name in ('General', 'Appearance', 'Colors', 'Text'):
            page = SettingsPage()
            form = SettingsFormLayout(page)
            form.setContentsMargins(16, 16, 16, 16)
            form.setSpacing(12)
            form.setRowWrapPolicy(QFormLayout.DontWrapRows)
            forms[name] = form
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, name)
        self.theme_name = str(settings.value('theme', THEME_DEFAULT))
        self.artwork_theme = ChunkyCheckBox('Use dynamic theme')
        self.artwork_theme.setChecked(settings.value('artwork_theme_enabled', ARTWORK_THEME_DEFAULT, type=bool))
        self.artwork_theme.setToolTip('Match app colors to the playing album.')
        forms['Colors'].addRow(self.artwork_theme)
        self.continuous_playback = ChunkyCheckBox('Continuous playback')
        self.continuous_playback.setChecked(settings.value('continuous_playback', True, type=bool))
        self.continuous_playback.setToolTip('At the end of an album, jump to the next one in the folder.')
        forms['General'].addRow(self.continuous_playback)
        self.artwork_theme_mode = ThemedComboBox()
        self.artwork_theme_mode.setAccessibleName('Dynamic theme brightness')
        for label, value in (('any', 'any'), ('dark', 'dark'), ('light', 'light')):
            self.artwork_theme_mode.addItem(label, value)
        self.artwork_theme_mode.setCurrentIndex(max(0, self.artwork_theme_mode.findData(
            str(settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT)))))
        self.artwork_theme_mode.setToolTip('Choose light, dark, or any album colors.')
        self.artwork_theme_mode.setEnabled(self.artwork_theme.isChecked())
        self.artwork_theme.toggled.connect(self.artwork_theme_mode.setEnabled)
        forms['Colors'].addRow('Dynamic theme brightness', self.artwork_theme_mode)
        self.guide_button = ThemedButton('Start')
        self.guide_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.guide_button.setObjectName('firstTimeSetupButton')
        self.guide_button.setAccessibleName('Open first time setup')
        self.guide_button.setToolTip('Run first time setup.')
        self.guide_button.clicked.connect(self.open_quick_start)
        self.saved_theme_choice = ThemedComboBox()
        self.saved_theme_choice.setAccessibleName('Saved color themes')
        for preset in self.presets:
            self.saved_theme_choice.addItem(preset['name'], preset['id'])
        self.saved_theme_choice.setCurrentIndex(max(0, self.saved_theme_choice.findData(str(settings.value('selected_color_theme', '')))))
        self.active_color_choice = str(settings.value('selected_color_theme', ''))
        self.saved_theme_choice.setToolTip('Use a saved theme when dynamic colors are off or artwork is unavailable.')
        forms['Appearance'].addRow('Saved color themes', self.saved_theme_choice)
        self.library_folder = str(settings.value('browser_root', settings.value('folder', '')))
        self.original_library = self.library_folder
        self.library_button = ThemedButton('Choose')
        self.library_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.library_button.setAccessibleName('Set music library root')
        self.library_button.clicked.connect(self.choose_library)
        forms['General'].addRow('First time setup', self.guide_button)
        forms['General'].addRow('Set music library root', self.library_button)
        self.library_label = QLabel('Currently: ' + self.library_folder)
        self.library_label.setWordWrap(True)
        forms['General'].addRow(self.library_label)
        self.audio_output_choice = ThemedComboBox()
        self.audio_output_choice.setAccessibleName('Audio output')
        self.refresh_audio_devices(str(settings.value('audio_output_device', '')))
        self.audio_output_choice.setToolTip('Choose speakers or headphones for all audio.')
        self.audio_devices = QMediaDevices(self)
        self.audio_devices.audioOutputsChanged.connect(lambda: self.refresh_audio_devices())
        forms['General'].addRow('Audio output', self.audio_output_choice)
        self.ui_font_choice = ThemedComboBox()
        self.ui_font_choice.setAccessibleName('Interface font')
        self.ui_font_choice.addItem('Album Round (default)', UI_FONT_DEFAULT)
        catalog = QApplication.instance().property('availableFonts') or []
        default_font = resolve_font(catalog, UI_FONT_DEFAULT)
        bundled_families = {default_font['family']} if default_font else set()
        for font in catalog:
            if font['family'] not in bundled_families:
                self.ui_font_choice.addItem(font['family'], font['id'])
                bundled_families.add(font['family'])
        for family in QFontDatabase.families():
            if family not in bundled_families:
                self.ui_font_choice.addItem(family, 'system:' + family)
        self.select_ui_font(str(settings.value('ui_font', UI_FONT_DEFAULT)))
        self.ui_font_choice.setToolTip('Choose the interface font.')
        forms['Text'].addRow('Interface font', self.ui_font_choice)
        self.colors = {}
        self.numbers = {}
        rounding_row = QHBoxLayout()
        self.rounding_row = rounding_row
        self.rounding_slider = ThemeSlider()
        self.rounding_slider.setObjectName('corner_roundness')
        self.rounding_slider.setAccessibleName('Corner roundness')
        self.rounding_slider.setRange(0, 100)
        rounding_value = QLabel()
        rounding_value.setFixedWidth(84)
        rounding_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.rounding_slider.valueChanged.connect(lambda value: rounding_value.setText(f'{value}%'))
        self.rounding_slider.setValue(int(settings.value('corner_roundness', NUMERIC_DEFAULTS['corner_roundness'])))
        rounding_value.setText(f'{self.rounding_slider.value()}%')
        self.rounding_slider.setToolTip('0%: square corners. 100%: fully rounded.')
        rounding_row.addWidget(self.rounding_slider, 1)
        rounding_row.addWidget(rounding_value)
        forms['Appearance'].addRow('Corner roundness', rounding_row)
        self.cleaning = ChunkyCheckBox('I like cleaning')
        self.cleaning.setObjectName('i_like_cleaning')
        self.cleaning.setToolTip('Keep albums tilted until you tidy up.')
        self.cleaning.setChecked(settings.value('i_like_cleaning', CLEANING_DEFAULT, type=bool))
        forms['Appearance'].addRow(self.cleaning)
        for category, label, key, prop, default in COLOR_SETTINGS:
            if key in MERGED_COLOR_SETTINGS:
                continue
            button = ColorSwatch(self.custom_colors[key] if not self.active_color_choice else str(settings.value(key, default)), label, self)
            button.setObjectName(key)
            button.clicked.connect(lambda checked=False, target=button, title=label: self.choose_color(target, title))
            self.colors[key] = button
            if key in PRIMARY_COLOR_KEYS:
                forms['Colors'].addRow(label, button)
            else:
                button.hide()
        self.marker_color = ColorSwatch(str(settings.value('marker_text_color', MARKER_COLOR_DEFAULT)), 'Text color', self)
        self.marker_color.setObjectName('marker_text_color')
        self.marker_color.clicked.connect(self.choose_marker_color)
        forms['Colors'].addRow('Text color', self.marker_color)
        for definition in NUMERIC_SETTINGS:
            self.add_numeric(forms, definition)
        self.colors.update({alias: self.colors[canonical] for alias, canonical in MERGED_COLOR_SETTINGS.items()})
        self.sync_color_roles()
        self.numbers.update({alias: self.numbers[canonical] for alias, canonical in MERGED_NUMERIC_SETTINGS.items()})
        self.scroll_anchor_slider = None
        self.pending_scroll_anchor = None
        self.scroll_anchor_passes = 0
        self.scroll_anchor_timer = QTimer(self)
        self.scroll_anchor_timer.setSingleShot(True)
        self.scroll_anchor_timer.timeout.connect(self.restore_scroll_anchor)
        for control in set(self.numbers.values()):
            control.slider.valueChanged.connect(lambda value, slider=control.slider: self.track_scroll_anchor(slider))
        self.tabs.currentChanged.connect(lambda index: self.track_scroll_anchor(None))
        self.numbers['main_font_size'].setToolTip('Control all text sizes while keeping their default proportions.')
        self.numbers['button_size'].setToolTip('Standard button height in pixels. Also sizes dropdowns, tabs, and checkboxes.')
        self.numbers['button_font_size'].setToolTip('Resize button, dropdown, and tab text.')
        self.numbers['ui_thickness'].setToolTip('Set button depth. 0 px makes buttons flat and silent.')
        self.numbers['button_sound_volume'].setToolTip('Adjust click volume. 0% mutes clicks.')
        self.numbers['handwriting_font_size'].setToolTip('Resize titles on covers without artwork.')
        self.numbers['hover_rotation'].setToolTip('Set how far albums tilt on hover.')
        self.prepare_setting_resets()
        self.organize_settings(forms)
        self.update_reset_buttons()
        self.forms = forms
        self.artwork_theme.toggled.connect(self.update_dependencies)
        self.numbers['ui_thickness'].slider.valueChanged.connect(self.update_dependencies)
        self.color_preview_timer = QTimer(self)
        self.color_preview_timer.setInterval(100)
        self.color_preview_timer.timeout.connect(self.update_dynamic_swatches)
        self.color_preview_timer.start()
        self.update_dependencies()
        self.update_vertical_spacing()
        self.saved_theme_choice.currentIndexChanged.connect(self.select_saved_theme)
        self.saved_theme_choice.activated.connect(self.select_saved_theme)
        actions = QGridLayout()
        reset = ThemedButton('Restore defaults')
        cancel = ThemedButton('Cancel')
        accept = ThemedButton('OK')
        accept.setProperty('themeRole', 'highlight')
        reset.clicked.connect(self.restore_defaults)
        cancel.clicked.connect(self.reject)
        accept.clicked.connect(self.accept)
        accept.setDefault(True)
        self.action_buttons = (reset, cancel, accept)
        self.actions = actions
        self.action_columns = 0
        self.layout_actions()
        outer.addLayout(actions)
        for control in self.findChildren(QWidget):
            if isinstance(control, (ThemedButton, ThemedComboBox)):
                control.setMaximumWidth(300)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(60)
        self.preview_timer.timeout.connect(self.apply)
        self.slider_preview_timer = QTimer(self)
        self.slider_preview_timer.setSingleShot(True)
        self.slider_preview_timer.setInterval(16)
        self.slider_preview_timer.timeout.connect(self.update_slider_preview)
        self.page_layout_timer = QTimer(self)
        self.page_layout_timer.setSingleShot(True)
        self.page_layout_timer.timeout.connect(self.prepare_pages)
        self.tabs.currentChanged.connect(lambda _: self.page_layout_timer.start(0))
        self.view_restore_timer = QTimer(self)
        self.view_restore_timer.setSingleShot(True)
        self.view_restore_timer.timeout.connect(self.restore_view_state)
        try:
            state = json.loads(str(settings.value('settings_view_state', '{}')))
        except (ValueError, TypeError):
            state = {}
        self.pending_view_state = state if isinstance(state, dict) else {}
        index = next((index for index in range(self.tabs.count())
                      if self.tabs.tabText(index) == self.pending_view_state.get('tab')), 0)
        self.tabs.setCurrentIndex(index)
        for control in set(self.numbers.values()):
            control.slider.valueChanged.connect(self.queue_preview)
        for button in set(self.colors.values()):
            button.colorChanged.connect(self.queue_preview)
        self.marker_color.colorChanged.connect(self.queue_preview)
        for control in (self.artwork_theme, self.continuous_playback, self.cleaning):
            control.toggled.connect(self.queue_preview)
        for control in (self.saved_theme_choice, self.artwork_theme_mode, self.ui_font_choice,
                        self.audio_output_choice):
            control.currentIndexChanged.connect(self.queue_preview)
        self.rounding_slider.valueChanged.connect(self.queue_preview)
        for slider in {control.slider for control in self.numbers.values()} | {self.rounding_slider}:
            slider.sliderPressed.connect(self.begin_slider_drag)
            slider.sliderReleased.connect(self.end_slider_drag)

    def organize_settings(self, forms):
        """Group related rows with quiet headings and space between sections."""
        groups = {
            'General': ('Music library', 'Playback'),
            'Style': ('Theme', 'Interface', 'Buttons', 'Settings window'),
            'Audio': ('Output device', 'Button sounds', 'CD case sounds'),
            'File browser': ('Folders', 'Album Drive logo'),
            'Album list': ('Grid', 'Select animation', 'Missing-art sleeves'),
            'Track list': ('Tracks',),
        }
        special = {
            self.rounding_row: ('Style', 'Interface'),
            self.guide_button: ('General', 'Music library'),
            self.library_button: ('General', 'Music library'), self.library_label: ('General', 'Music library'),
            self.continuous_playback: ('General', 'Playback'),
            self.artwork_theme: ('Style', 'Theme'), self.artwork_theme_mode: ('Style', 'Theme'),
            self.saved_theme_choice: ('Style', 'Theme'),
            self.cleaning: ('Album list', 'Select animation'),
            self.ui_font_choice: ('Style', 'Interface'),
            self.audio_output_choice: ('Audio', 'Output device'),
        }
        elements = {
            'theme_fade_seconds': ('Style', 'Theme'),
            'main_font_size': ('Style', 'Interface'), 'theme_text_color': ('Style', 'Interface'),
            'corner_roundness': ('Style', 'Interface'), 'ui_thickness': ('Style', 'Interface'),
            'theme_accent_color': ('Style', 'Interface'), 'theme_background_color': ('Style', 'Interface'),
            'theme_highlight_color': ('Style', 'Interface'),
            'theme_background_accent_color': ('Style', 'Interface'),
            'theme_selected_text_color': ('Style', 'Interface'), 'menu_font_size': ('Style', 'Interface'),
            'button_font_size': ('Style', 'Buttons'), 'dropdown_font_size': ('Style', 'Buttons'),
            'theme_button_text_color': ('Style', 'Buttons'), 'theme_disabled_text_color': ('Style', 'Buttons'),
            'button_icon_size': ('Style', 'Buttons'), 'theme_button_icon_color': ('Style', 'Buttons'),
            'theme_button_fill': ('Style', 'Buttons'), 'button_sound_volume': ('Audio', 'Button sounds'),
            'case_open_volume': ('Audio', 'CD case sounds'), 'case_close_volume': ('Audio', 'CD case sounds'),
            'folder_font_size': ('File browser', 'Folders'), 'folder_vertical_spacing': ('File browser', 'Folders'),
            'theme_folder_arrow_color': ('File browser', 'Arrows'),
            'handwriting_font_size': ('Album list', 'Missing-art sleeves'), 'marker_text_color': ('Album list', 'Missing-art sleeves'),
            'track_list_font_size': ('Track list', 'Tracks'), 'track_list_vertical_spacing': ('Track list', 'Tracks'),
            'theme_paper_text_color': ('Track list', 'Tracks'),
            'logo_font_size': ('File browser', 'Album Drive logo'), 'theme_brand_text_color': ('File browser', 'Album Drive logo'),
            'theme_brand_line_color': ('File browser', 'Album Drive logo'),
            'settings_vertical_spacing': ('Style', 'Settings window'), 'settings_heading_font_size': ('Style', 'Settings window'),
        }
        short_labels = {
            'theme_fade_seconds': 'Fade duration', 'button_size': 'Size', 'ui_thickness': 'Thickness',
            'button_icon_size': 'Icon size', 'button_font_size': 'Text scale',
            'button_sound_volume': 'Volume', 'case_open_volume': 'Opening volume', 'case_close_volume': 'Closing volume',
            'track_list_font_size': 'Text scale', 'track_list_vertical_spacing': 'Vertical spacing',
            'folder_vertical_spacing': 'Vertical spacing', 'folder_font_size': 'Text scale',
            'settings_vertical_spacing': 'Vertical spacing', 'settings_heading_font_size': 'Heading text scale',
            'main_font_size': 'Text size', 'logo_font_size': 'Text scale',
            'handwriting_font_size': 'Text scale', 'hover_rotation': 'Random rotation', 'hover_growth': 'Zoom',
            'hover_lift': 'Lift', 'album_vertical_spacing': 'Vertical spacing',
            'theme_button_fill': 'Background color', 'theme_button_text_color': 'Content color',
        }
        control_labels = {
            self.library_button: 'Root folder', self.continuous_playback: 'Continuous',
            self.saved_theme_choice: 'Saved themes', self.artwork_theme_mode: 'Brightness',
            self.ui_font_choice: 'Font', self.audio_output_choice: 'Device',
        }
        self.option_labels = {}
        rows = {category: {group: [] for group in sections} for category, sections in groups.items()}
        for category, form in forms.items():
            while form.rowCount():
                row = form.takeRow(0)
                field = row.fieldItem.widget() or row.fieldItem.layout()
                label = row.labelItem.widget() if row.labelItem else None
                if isinstance(field, ChunkyCheckBox) and label is None:
                    label = QLabel(field.text())
                    label.setBuddy(field)
                    label.setToolTip(field.toolTip())
                    label.installEventFilter(self)
                    field.setAccessibleName(field.text())
                    field.setText('')
                    field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                key = field.objectName()
                destination = special.get(field)
                if destination is None:
                    destination = elements.get(key)
                    if destination is None:
                        destination = (('Album list', 'Select animation') if key.startswith('hover_') else
                                       ('Album list', 'Grid') if key.startswith('album_') else
                                       ('Style', 'Buttons'))
                if label is not None:
                    label.setProperty('settingFullName', label.text())
                    label.setText(control_labels.get(field, short_labels.get(key, label.text())))
                    label.setProperty('settingsOptionTitle', True)
                    label.installEventFilter(self)
                    if isinstance(field, QWidget):
                        self.option_labels[field] = label
                        label.setEnabled(field.isEnabled())
                        field.installEventFilter(self)
                rows[destination[0]][destination[1]].append((label, field))
        # Replace the construction pages with the interface-area pages.
        old_pages = [self.tabs.widget(index) for index in range(self.tabs.count())]
        self.tabs.clear()
        forms.clear()
        for category in groups:
            page = SettingsPage()
            form = SettingsFormLayout(page)
            form.setContentsMargins(16, 16, 16, 16)
            form.setRowWrapPolicy(QFormLayout.DontWrapRows)
            forms[category] = form
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, category)
        self.tabs.setUsesScrollButtons(False)
        for old_page in old_pages:
            old_page.deleteLater()
        for category, sections in groups.items():
            form = forms[category]
            for index, section in enumerate(sections):
                if index:
                    spacer = QWidget()
                    spacer.setProperty('settingsRow', True)
                    spacer.setObjectName('settingsSectionSpacer')
                    spacer.setFixedHeight(SECTION_GAP)
                    form.addRow(spacer)
                heading = SettingsSectionLabel(section)
                heading.setObjectName('settingsSection')
                form.addRow(heading)
                section_rows = rows[category][section]
                slider_order = {'button_size': 0, 'button_icon_size': 1, 'button_font_size': 2} if section == 'Buttons' else {}
                def row_order(row):
                    field = row[1]
                    if field is self.rounding_row:
                        return -4, 0
                    if field is self.numbers['ui_thickness']:
                        return -3, 0
                    if field is self.artwork_theme:
                        return -3, 0
                    if field is self.artwork_theme_mode:
                        return -2, 0
                    if field is self.saved_theme_choice:
                        return -1, 0
                    if field is self.guide_button:
                        return -1, 0
                    if field is self.ui_font_choice:
                        return -2, 0
                    if field is self.numbers['main_font_size']:
                        return -1, 0
                    if isinstance(field, NumericSlider) or field is self.rounding_row:
                        key = self.reset_specs[field][0]
                        return 3, slider_order.get(key, 99)
                    if isinstance(field, ColorSwatch):
                        return 2, 0
                    if isinstance(field, ChunkyCheckBox):
                        return 1, 0
                    return (0, 0) if isinstance(field, ThemedComboBox) else (4, 0)
                for label, field in sorted(section_rows, key=row_order):
                    field = self.wrap_setting_reset(field, label)
                    if label is not None:
                        form.addRow(label, field)
                    else:
                        form.addRow(field)

    def prepare_setting_resets(self):
        self.reset_specs = {}
        self.reset_buttons = {}
        self.reset_bindings = []
        for key, control in self.numbers.items():
            if key not in MERGED_NUMERIC_SETTINGS:
                self.reset_specs[control] = (key, 100 if key in FONT_SCALE_KEYS else NUMERIC_DEFAULTS[key], control.value, control.setValue, control.slider.valueChanged)
        defaults = simplify_color_settings({key: default for _, _, key, _, default in COLOR_SETTINGS})
        for key in PRIMARY_COLOR_KEYS:
            button = self.colors[key]
            self.reset_specs[button] = (key, defaults[key], lambda target=button: target.color().name(),
                                        lambda color, target=button: self.set_setting_color(target, QColor(color)), button.colorChanged)
        self.reset_specs[self.marker_color] = ('marker_text_color', MARKER_COLOR_DEFAULT,
                                               lambda: self.marker_color.color().name(), self.marker_color.set_color,
                                               self.marker_color.colorChanged)
        self.reset_specs[self.rounding_row] = ('corner_roundness', NUMERIC_DEFAULTS['corner_roundness'],
                                               self.rounding_slider.value, self.rounding_slider.setValue, self.rounding_slider.valueChanged)
        for key, field, default in (('artwork_theme_enabled', self.artwork_theme, ARTWORK_THEME_DEFAULT),
                                    ('continuous_playback', self.continuous_playback, True),
                                    ('i_like_cleaning', self.cleaning, CLEANING_DEFAULT)):
            self.reset_specs[field] = (key, default, field.isChecked, field.setChecked, field.toggled)
        for key, field, default, setter in (
                ('ui_font', self.ui_font_choice, UI_FONT_DEFAULT, self.select_ui_font),
                ('audio_output_device', self.audio_output_choice, '', None),
                ('artwork_theme_mode', self.artwork_theme_mode, ARTWORK_THEME_MODE_DEFAULT, None)):
            getter = (lambda target=field: str(target.currentData()).split('::')[0]) if key.endswith('font') else field.currentData
            setter = setter or (lambda value, target=field: target.setCurrentIndex(max(0, target.findData(value))))
            self.reset_specs[field] = (key, default, getter, setter, field.currentIndexChanged)

    def wrap_setting_reset(self, field, label):
        spec = self.reset_specs.get(field)
        if spec is None:
            return field
        key, default, getter, setter, signal = spec
        title = (label.property('settingFullName') or label.text()) if label is not None else field.text()
        row = QWidget()
        row.setProperty('settingsRow', True)
        row.setObjectName(key + 'Row')
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        if isinstance(field, QWidget):
            if isinstance(field, (ThemedButton, ThemedComboBox, ChunkyCheckBox)):
                layout.addWidget(field)
                layout.addStretch(1)
            else:
                layout.addWidget(field, 1)
            field.installEventFilter(self)
            enabled = field.isEnabled
        else:
            layout.addLayout(field, 1)
            enabled = self.rounding_slider.isEnabled
        button = SettingResetButton(title)
        button.setObjectName(key + 'Reset')
        button.clicked.connect(lambda checked=False: setter(default))
        signal.connect(self.update_reset_buttons)
        layout.addWidget(button)
        self.reset_buttons[key] = button
        self.reset_bindings.append((button, default, getter, enabled))
        return row

    def update_reset_buttons(self, *args):
        for button, default, getter, enabled in self.reset_bindings:
            button.setVisible(enabled() and getter() != default)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.FontChange and watched.property('settingsOptionTitle') and hasattr(self, 'page_layout_timer'):
            self.page_layout_timer.start(0)
        if isinstance(watched, QLabel) and event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            checkbox = watched.buddy()
            if isinstance(checkbox, ChunkyCheckBox) and checkbox.isEnabled():
                checkbox.setFocus(Qt.MouseFocusReason)
                checkbox.click()
                return True
        if (event.type() == QEvent.MouseButtonPress and self.isVisible()
                and isinstance(watched, QWidget) and self.parentWidget() is not None
                and watched.window() is self.parentWidget().window()
                and QApplication.activeModalWidget() is None):
            SettingsDismissClick(self.parentWidget().window(), event.button())
            self.accept()
            return True
        if event.type() == QEvent.EnabledChange:
            label = self.option_labels.get(watched)
            if label is not None:
                label.setEnabled(watched.isEnabled())
            if hasattr(self, 'reset_bindings'):
                self.update_reset_buttons()
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        self.prepare_pages()
        self.page_layout_timer.start(0)
        self.view_restore_timer.start(0)
        self.color_preview_timer.start()
        QApplication.instance().installEventFilter(self)

    def restore_view_state(self):
        if not self.isVisible() or not self.pending_view_state:
            return
        self.prepare_pages()
        positions = self.pending_view_state.get('scroll', {})
        if isinstance(positions, dict):
            for index in range(self.tabs.count()):
                position = positions.get(self.tabs.tabText(index))
                if not isinstance(position, list) or len(position) != 2:
                    continue
                area = self.tabs.widget(index)
                for bar, value in zip((area.horizontalScrollBar(), area.verticalScrollBar()), position):
                    if isinstance(value, int):
                        bar.setValue(max(bar.minimum(), min(bar.maximum(), value)))
        self.pending_view_state = {}

    def save_view_state(self):
        if not self.isVisible():
            return
        self.restore_view_state()
        state = {'tab': self.tabs.tabText(self.tabs.currentIndex()),
                 'scroll': {self.tabs.tabText(index): [self.tabs.widget(index).horizontalScrollBar().value(),
                                                     self.tabs.widget(index).verticalScrollBar().value()]
                            for index in range(self.tabs.count())}}
        self.settings.setValue('settings_view_state', json.dumps(state))

    def closeEvent(self, event):
        self.accept()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
            event.accept()
            return
        super().keyPressEvent(event)

    def done(self, result):
        self.view_restore_timer.stop()
        self.save_view_state()
        self.page_layout_timer.stop()
        self.hide()
        if self.transaction_open:
            pending = self.preview_timer.isActive() or self.slider_preview_pending
            self.preview_timer.stop()
            self.clear_slider_preview()
            self.active_sliders.clear()
            self.transaction_open = False
            if result == QDialog.Accepted:
                self.save()
                if hasattr(self.settings, '_preview_color_themes'):
                    del self.settings._preview_color_themes
                if pending or not self.preview_applied:
                    self.applied.emit()
            else:
                if hasattr(self.settings, '_preview_color_themes'):
                    del self.settings._preview_color_themes
                for key in self.preview_keys:
                    if key in self.original_settings:
                        self.settings.setValue(key, self.original_settings[key])
                    else:
                        self.settings.remove(key)
                if self.preview_applied:
                    self.restoring = True
                    self.applied.emit()
                    self.restoring = False
        self.scroll_anchor_timer.stop()
        self.page_layout_timer.stop()
        self.color_preview_timer.stop()
        self.pending_scroll_anchor = None
        QApplication.instance().removeEventFilter(self)
        self.settings.sync()
        super().done(result)

    def refresh_audio_devices(self, identity=None):
        identity = self.audio_output_choice.currentData() if identity is None else identity
        self.audio_output_choice.clear()
        self.audio_output_choice.addItem('OS default', '')
        for device in QMediaDevices.audioOutputs():
            self.audio_output_choice.addItem(device.description(), bytes(device.id()).hex())
        index = self.audio_output_choice.findData(identity or '')
        if index < 0:
            self.audio_output_choice.addItem('Unavailable device (using OS default)', identity)
            index = self.audio_output_choice.count() - 1
        self.audio_output_choice.setCurrentIndex(index)

    def open_quick_start(self):
        from first_run import FirstRunDialog
        guide = FirstRunDialog(self.settings, self)
        mode = self.artwork_theme_mode.currentData() if self.artwork_theme.isChecked() else 'off'
        guide.choices.get(mode, guide.choices['any']).setChecked(True)
        if guide.exec() == QDialog.Accepted:
            self.preview_applied = True
            self.library_folder = str(self.settings.value('browser_root', self.library_folder))
            self.library_label.setText('Currently: ' + self.library_folder)
            self.rounding_slider.setValue(self.settings.value('corner_roundness', NUMERIC_DEFAULTS['corner_roundness'], type=int))
            for key in ('ui_thickness', 'button_sound_volume'):
                self.numbers[key].setValue(self.settings.value(key, NUMERIC_DEFAULTS[key], type=int))
            self.saved_theme_choice.setCurrentIndex(max(0, self.saved_theme_choice.findData(
                self.settings.value('selected_color_theme', ''))))
            self.artwork_theme.setChecked(self.settings.value('artwork_theme_enabled', ARTWORK_THEME_DEFAULT, type=bool))
            self.artwork_theme_mode.setCurrentIndex(max(0, self.artwork_theme_mode.findData(
                str(self.settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT)))))
            self.applied.emit()

    def update_vertical_spacing(self, spacing=None):
        if spacing is None:
            spacing = signed_setting_int(self.settings.value('settings_vertical_spacing', NUMERIC_DEFAULTS['settings_vertical_spacing']))
        spacing = max(-40, min(40, spacing))
        if spacing == getattr(self, '_applied_vertical_spacing', None):
            return
        self._applied_vertical_spacing = spacing
        for form in self.forms.values():
            form.setVerticalSpacing(spacing)
            for spacer in form.parentWidget().findChildren(QWidget, 'settingsSectionSpacer'):
                spacer.setFixedHeight(SECTION_GAP + max(0, spacing))
            form.parentWidget().update()

    def layout_actions(self):
        for button in self.action_buttons:
            button.setFixedHeight(button.sizeHint().height())
        columns = 3 if sum(min(button.sizeHint().width(), button.maximumWidth()) for button in self.action_buttons) + 48 <= self.width() else 2
        height = max(button.sizeHint().height() for button in self.action_buttons)
        if columns != self.action_columns or height != getattr(self, 'action_height', None):
            self.action_columns = columns
            self.action_height = height
            for button in self.action_buttons:
                self.actions.removeWidget(button)
            for row in range(self.actions.rowCount()):
                self.actions.setRowMinimumHeight(row, 0)
            for index, button in enumerate(self.action_buttons):
                self.actions.addWidget(button, index // columns, index % columns)
                self.actions.setRowMinimumHeight(index // columns, height)
        self.tabs.setMinimumHeight(self.tabs.tabBar().sizeHint().height() + 32)

    def event(self, event):
        if event.type() in (QEvent.LayoutRequest, QEvent.Resize) and hasattr(self, 'action_buttons'):
            self.layout_actions()
        if event.type() == QEvent.Resize and hasattr(self, 'page_layout_timer'):
            self.page_layout_timer.start(0)
        return super().event(event)

    def prepare_pages(self):
        if not self.isVisible():
            return
        labels = []
        for form in self.forms.values():
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.LabelRole)
                if item is not None and item.widget() is not None:
                    label = item.widget()
                    label.ensurePolished()
                    labels.append(label)
        for label in labels:
            label.setWordWrap(True)
            if label.minimumWidth() != SETTING_LABEL_WIDTH or label.maximumWidth() != SETTING_LABEL_WIDTH:
                label.setFixedWidth(SETTING_LABEL_WIDTH)
        current = self.tabs.currentWidget()
        for index in range(self.tabs.count()):
            area = self.tabs.widget(index)
            area.ensurePolished()
            if area is not current:
                area.setGeometry(current.geometry())
                QApplication.sendEvent(area, QResizeEvent(area.size(), area.size()))
            page = area.widget()
            page.ensurePolished()
            width = area.contentsRect().width()
            width = max(width, page.minimumSizeHint().width())
            height = page.layout().heightForWidth(width)
            if height > area.contentsRect().height():
                width -= area.style().pixelMetric(QStyle.PM_ScrollBarExtent)
                height = page.layout().heightForWidth(width)
            page.resize(width, max(area.viewport().height(), height))
            page.layout().setGeometry(page.rect())
            for widget in page.findChildren(QWidget):
                widget.ensurePolished()
                if widget.layout() is not None:
                    widget.layout().setGeometry(widget.rect())
            if area is not current:
                extent = area.style().pixelMetric(QStyle.PM_ScrollBarExtent)
                available = area.contentsRect().size()
                viewport_height = available.height()
                for _ in range(2):
                    viewport_width = available.width() - (extent if page.height() > viewport_height else 0)
                    viewport_height = available.height() - (extent if page.width() > viewport_width else 0)
                for bar, total, visible in ((area.horizontalScrollBar(), page.width(), viewport_width),
                                            (area.verticalScrollBar(), page.height(), viewport_height)):
                    bar.setRange(0, max(0, total - visible))
                    bar.setPageStep(max(0, visible))
        button_text_sizing().refresh()

    def add_numeric(self, forms, definition):
        category, label, key, default, low, high, suffix, step = definition
        if key in MERGED_NUMERIC_SETTINGS:
            return
        scalable = key in FONT_SCALE_KEYS
        if scalable:
            label = label.replace('size', 'scale')
            default, low, high, suffix, step = 100, 75, 125, ' %', 1
        elif key == 'main_font_size':
            high = MAX_FONT_SIZE
        # Keep existing percentage-based preferences and saved themes intact,
        # while showing and stepping button depth in actual pixels.
        control = NumericSlider(default, low, high, suffix, step, display_scale=.04 if key == 'ui_thickness' else 1,
                                display_offset=NUMERIC_DEFAULTS[key] if key in ('settings_vertical_spacing', 'folder_vertical_spacing', 'track_list_vertical_spacing') else 0)
        control.setObjectName(key)
        control.slider.setAccessibleName(label)
        setting_key = FONT_SCALE_KEYS[key] if scalable else key
        control.setValue(float(self.settings.value(setting_key, default)) if isinstance(default, float)
                         else signed_setting_int(self.settings.value(setting_key, default)))
        if scalable:
            control.setToolTip('Adjust the default proportion relative to the main text size. 100% keeps the default size ratio.')
        self.numbers[key] = control
        forms[category].addRow(label, control)

    def choose_marker_color(self):
        selected = ColorPickerDialog.getColor(self.marker_color.color(), self, 'Text color')
        if selected.isValid():
            self.marker_color.set_color(selected)

    def choose_color(self, button, title):
        selected = ColorPickerDialog.getColor(button.color(), self, title)
        if selected.isValid():
            self.set_setting_color(button, selected)

    def set_setting_color(self, button, color):
        self.saved_theme_choice.blockSignals(True)
        self.saved_theme_choice.setCurrentIndex(0)
        self.saved_theme_choice.blockSignals(False)
        self.active_color_choice = ''
        self.artwork_theme.setChecked(False)
        button.set_color(color)
        self.sync_color_roles()
        self.queue_preview()

    def sync_color_roles(self):
        selected = next((preset for preset in self.presets if preset['id'] == self.active_color_choice), None)
        if selected is not None and selected.get('preserve_palette') is True:
            colors = soften_theme_colors({prop: self.colors[key].color().name() for _, _, key, prop, _ in COLOR_SETTINGS})
            for _, _, key, prop, _ in COLOR_SETTINGS:
                self.colors[key].set_color(colors[prop])
            return
        colors = simplify_color_settings({key: button.color().name() for key, button in self.colors.items()})
        for key, button in self.colors.items():
            button.set_color(colors[key])

    def update_dependencies(self):
        dynamic = self.artwork_theme.isChecked()
        self.saved_theme_choice.setEnabled(not dynamic)
        self.artwork_theme_mode.setEnabled(dynamic)
        for key, button in self.colors.items():
            button.setEnabled(not dynamic)
            button.setToolTip('Set by dynamic theming' if not button.isEnabled()
                              else 'Choose ' + button.accessibleName().lower())
            if key == 'theme_selected_text_color' and button.isEnabled():
                button.setToolTip('Text on selected rows and menu items.')
        sound = self.numbers['button_sound_volume']
        sound.setEnabled(self.numbers['ui_thickness'].value() > 0)
        sound.setToolTip('Flat buttons are silent.' if not sound.isEnabled() else '')
        self.update_dynamic_swatches()

    def update_dynamic_swatches(self):
        app = QApplication.instance()
        dynamic = self.artwork_theme.isChecked() and app.property('artworkTheme')
        for _, _, key, prop, _ in COLOR_SETTINGS:
            button = self.colors[key]
            preview = app.property(prop) if dynamic and not button.isEnabled() else None
            if button.property('previewSwatchColor') != preview:
                button.setProperty('previewSwatchColor', preview)
                button.update()

    def select_ui_font(self, identity):
        font = resolve_font(QApplication.instance().property('availableFonts') or [], identity)
        if font and not identity.startswith('system:'):
            identity = UI_FONT_DEFAULT if font['id'].split('::')[0] == UI_FONT_DEFAULT else font['id']
        self.ui_font_choice.setCurrentIndex(max(0, self.ui_font_choice.findData(identity)))

    def select_saved_theme(self):
        if not self.active_color_choice:
            self.custom_colors = {key: button.color().name() for key, button in self.colors.items()}
        identity = self.saved_theme_choice.currentData()
        preset = next((preset for preset in self.presets if preset['id'] == identity), None)
        if preset is not None or not identity:
            colors = preset['colors'] if preset is not None else self.custom_colors
            for key, button in self.colors.items():
                button.set_color(colors[MERGED_COLOR_SETTINGS.get(key, key)])
            self.artwork_theme.setChecked(False)
        self.active_color_choice = identity
        self.sync_color_roles()
        self.queue_preview()

    def save_current_colors(self):
        if not self.active_color_choice:
            self.custom_colors = {key: button.color().name() for key, button in self.colors.items()}
        parent = self.parentWidget()
        album = (parent.queue[parent.queue_index][1] if parent is not None
                 and hasattr(parent, 'queue') and 0 <= parent.queue_index < len(parent.queue) else None)
        name = album.title if album is not None else 'Custom colors'
        preset = capture_color_theme(self.presets, name)
        colors, name = preset['colors'], preset['name']
        self.presets.append(preset)
        self.saved_theme_choice.blockSignals(True)
        self.saved_theme_choice.addItem(name, preset['id'])
        self.saved_theme_choice.setCurrentIndex(self.saved_theme_choice.count() - 1)
        self.saved_theme_choice.blockSignals(False)
        self.active_color_choice = preset['id']
        for key, button in self.colors.items():
            button.set_color(colors[key])
        self.queue_preview()

    def choose_library(self):
        folder = QFileDialog.getExistingDirectory(self, 'Set music library root', self.library_folder or str(Path.home() / 'Music'))
        if folder:
            self.library_folder = folder
            self.library_label.setText(folder)
            self.queue_preview()

    def queue_preview(self, *args):
        if self.isVisible() and self.transaction_open and not self.previewing:
            if self.active_sliders:
                self.slider_preview_pending = True
                if not self.slider_preview_timer.isActive():
                    self.slider_preview_timer.start()
                return
            if not self.preview_timer.isActive():
                self.preview_timer.start()

    def begin_slider_drag(self):
        if not self.active_sliders:
            self.slider_preview_pending = self.preview_timer.isActive()
            self.preview_timer.stop()
            self.preview_stylesheet = self.styleSheet()
        self.active_sliders.add(self.sender())
        self.track_scroll_anchor(self.sender())
        self.update_slider_preview()

    def end_slider_drag(self):
        self.active_sliders.discard(self.sender())
        if not self.active_sliders and self.transaction_open:
            pending = self.slider_preview_pending
            self.clear_slider_preview()
            if pending:
                self.apply()

    def update_slider_preview(self):
        if not self.active_sliders or not self.transaction_open:
            return
        anchor = self.capture_scroll_anchor()
        master = self.numbers['main_font_size'].value()
        def font_size(key):
            size = round(NUMERIC_DEFAULTS[key] * master / NUMERIC_DEFAULTS['main_font_size'] * self.numbers[key].value() / 100)
            return max(8, min(MAX_FONT_SIZE, size)) if key == 'button_font_size' else max(6, size)
        requested_font = font_size('button_font_size')
        applied_font = QApplication.instance().property('buttonFontSize') or NUMERIC_DEFAULTS['button_font_size']
        button_font = min(requested_font, max(1, round(button_text_sizing().pixel_size * requested_font / applied_font)))
        values = {'buttonSize': self.numbers['button_size'].value(),
                  'uiThickness': self.numbers['ui_thickness'].value(),
                  'cornerRoundness': self.rounding_slider.value(), 'buttonFontSize': button_font}
        changed = values != self.property('settingsPreview')
        self.setProperty('settingsPreview', values)
        style = (self.preview_stylesheet or '') + f'''
QWidget {{ font-size: {master}px; }}
QPushButton, QComboBox, QTabBar {{ font-size: {button_font}px; }}
QLabel#settingsSection {{ font-size: {font_size('settings_heading_font_size')}px; font-weight: bold; }}
'''
        if self.styleSheet() != style:
            self.setStyleSheet(style)
            changed = True
        spacing = self.numbers['settings_vertical_spacing'].value()
        changed = changed or spacing != self._applied_vertical_spacing
        self.update_vertical_spacing(spacing)
        if changed:
            for widget in self.findChildren(QWidget):
                widget.updateGeometry()
                widget.update()
            self.layout_actions()
            self.layout().activate()
            self.prepare_pages()
            if anchor is not None:
                self.pending_scroll_anchor = anchor
                self.scroll_anchor_passes = 8
                self.restore_scroll_anchor()

    def clear_slider_preview(self):
        self.slider_preview_timer.stop()
        self.setProperty('settingsPreview', None)
        if self.preview_stylesheet is not None:
            self.setStyleSheet(self.preview_stylesheet)
            self.preview_stylesheet = None
        self.slider_preview_pending = False
        self.update_vertical_spacing()
        button_text_sizing().schedule()

    def apply(self):
        self.preview_timer.stop()
        if self.active_sliders:
            self.slider_preview_pending = True
            self.update_slider_preview()
            return
        self.previewing = True
        anchor = self.capture_scroll_anchor()
        before = {key: self.settings.value(key) for key in self.preview_keys}
        try:
            self.settings._preview_color_themes = self.presets
            self.save(persist_themes=False)
            self.changed_keys = {key for key, value in before.items() if self.settings.value(key) != value}
            self.preview_applied = True
            self.applied.emit()
        finally:
            self.previewing = False
        if self.changed_keys & (set(FONT_SCALE_KEYS.values()) | {'main_font_size', 'ui_font', 'button_size', 'ui_thickness', 'settings_vertical_spacing'}):
            self.layout_actions()
            self.layout().activate()
            self.page_layout_timer.start(0)
        if anchor is not None and self.isVisible():
            self.pending_scroll_anchor = anchor
            self.scroll_anchor_passes = 8
            self.restore_scroll_anchor()

    def track_scroll_anchor(self, slider):
        self.scroll_anchor_slider = slider if slider is not None and slider.isVisible() else None

    def capture_scroll_anchor(self):
        slider = self.scroll_anchor_slider
        area = self.tabs.currentWidget()
        if slider is None or not self.isVisible() or not isinstance(area, QScrollArea) or not area.isAncestorOf(slider):
            return None
        viewport = area.viewport()
        origin = slider.mapTo(viewport, QPoint())
        if not viewport.rect().intersects(QRect(origin, slider.size())):
            return None
        return area, slider, slider.mapTo(self, QPoint(0, slider.height() // 2)).y()

    def restore_scroll_anchor(self):
        if self.pending_scroll_anchor is None:
            return
        area, slider, y = self.pending_scroll_anchor
        if not self.isVisible() or self.tabs.currentWidget() is not area or not slider.isVisible():
            self.pending_scroll_anchor = None
            return
        area.widget().layout().activate()
        current_y = slider.mapTo(self, QPoint(0, slider.height() // 2)).y()
        bar = area.verticalScrollBar()
        bar.setValue(bar.value() + current_y - y)
        self.scroll_anchor_passes -= 1
        if self.scroll_anchor_passes:
            self.scroll_anchor_timer.start(8)
        else:
            self.pending_scroll_anchor = None

    def restore_defaults(self):
        self.reset_album_size = True
        self.reset_font_scales = True
        self.theme_name = THEME_DEFAULT
        self.select_ui_font(UI_FONT_DEFAULT)
        self.rounding_slider.setValue(NUMERIC_DEFAULTS['corner_roundness'])
        self.cleaning.setChecked(CLEANING_DEFAULT)
        self.continuous_playback.setChecked(True)
        self.audio_output_choice.setCurrentIndex(0)
        self.saved_theme_choice.setCurrentIndex(0)
        self.artwork_theme.setChecked(ARTWORK_THEME_DEFAULT)
        self.artwork_theme_mode.setCurrentIndex(self.artwork_theme_mode.findData(ARTWORK_THEME_MODE_DEFAULT))
        self.marker_color.set_color(MARKER_COLOR_DEFAULT)
        for _, _, key, _, default in COLOR_SETTINGS:
            if key not in MERGED_COLOR_SETTINGS:
                self.colors[key].set_color(default)
        self.custom_colors = {key: default for _, _, key, _, default in COLOR_SETTINGS}
        for _, _, key, default, *_ in NUMERIC_SETTINGS:
            if key not in MERGED_NUMERIC_SETTINGS:
                self.numbers[key].setValue(100 if key in FONT_SCALE_KEYS else default)
        self.sync_color_roles()

    def save(self, persist_themes=True):
        self.sync_color_roles()
        if not self.active_color_choice:
            self.custom_colors = {key: button.color().name() for key, button in self.colors.items()}
        self.settings.setValue('custom_theme_colors', json.dumps(self.custom_colors))
        self.settings.remove('custom_theme_options')
        selected = next((preset for preset in self.presets if preset['id'] == self.active_color_choice), None)
        if selected is not None and selected['id'] != 'album-drive-default':
            selected['colors'] = {key: button.color().name() for key, button in self.colors.items()}
        if self.reset_album_size:
            self.settings.setValue('album_scale', NUMERIC_DEFAULTS['album_scale'])
            self.reset_album_size = False
        if self.reset_font_scales:
            for key in FONT_SCALE_KEYS.values():
                self.settings.setValue(key, 100)
            self.reset_font_scales = False
        self.settings.setValue('theme', self.theme_name)
        self.settings.setValue('marker_text_color', self.marker_color.color().name())
        self.settings.setValue('artwork_theme_enabled', self.artwork_theme.isChecked())
        self.settings.setValue('audio_output_device', self.audio_output_choice.currentData())
        self.settings.setValue('continuous_playback', self.continuous_playback.isChecked())
        self.settings.setValue('artwork_theme_mode', self.artwork_theme_mode.currentData())
        if persist_themes:
            signature = json.dumps(self.presets, sort_keys=True)
            if signature != self.persisted_presets or (len(self.presets) > 1 and not self.settings.value('theme_files_version', 0, type=int)):
                write_theme_files(self.settings, self.presets)
                self.persisted_presets = signature
        self.settings.setValue('selected_color_theme', self.active_color_choice)
        self.settings.setValue('ui_font', self.ui_font_choice.currentData())
        if self.library_folder and self.library_folder != self.original_library:
            self.settings.setValue('browser_root', self.library_folder)
            self.settings.setValue('folder', self.library_folder)
            self.original_library = self.library_folder
        self.settings.setValue('corner_roundness', self.rounding_slider.value())
        self.settings.setValue('i_like_cleaning', self.cleaning.isChecked())
        for key, button in self.colors.items():
            self.settings.setValue(key, button.color().name())
        for key, spin in self.numbers.items():
            if key not in MERGED_NUMERIC_SETTINGS:
                self.settings.setValue(FONT_SCALE_KEYS.get(key, key), spin.value())
        self.update_vertical_spacing()
