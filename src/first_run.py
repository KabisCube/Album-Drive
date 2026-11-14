"""First-run setup for the music library, buttons, album colors and saved themes."""

import json
from pathlib import Path
from music_folders import choose_music_directory, music_directory
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QButtonGroup, QDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLayout, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from themes import CONTROL_HEADROOM, ChunkyCheckBox, ThemedButton, paint_control, shadow_color, NUMERIC_DEFAULTS
from button_sounds import play_button_sound, prepare_button_sounds
from responsive import ScreenFit, wrap_freely, wrappable_path


def needs_first_run(settings):
    if settings.value('welcome_complete', False, type=bool):
        return False
    if settings.value('welcome_started', False, type=bool):
        return True
    return not any(settings.contains(key) for key in
                   ('window_geometry', 'folder', 'browser_root', 'custom_theme_colors'))


FIXED_THEMES = {
    'fixed_dark': {
        'theme_accent_color': '#d77341', 'theme_highlight_color': '#815948', 'theme_background_color': '#2e2426',
        'theme_background_accent_color': '#4a322d', 'theme_timeline_color': '#815948',
        'theme_brand_line_color': '#2a2123', 'theme_folder_arrow_color': '#bfa799', 'theme_button_fill': '#4a322d',
        'theme_button_icon_color': '#4a322d', 'theme_button_text_color': '#4a322d',
        'theme_disabled_text_color': '#4a322d', 'theme_text_color': '#bfa799', 'theme_secondary_text_color': '#bfa799',
        'theme_heading_text_color': '#bfa799', 'theme_brand_text_color': '#d77341',
        'theme_selected_text_color': '#bfa799', 'theme_timeline_text_color': '#bfa799',
        'theme_paper_text_color': '#bfa799'},
    'fixed_light': {
        'theme_accent_color': '#da7d5d', 'theme_highlight_color': '#d6c399', 'theme_background_color': '#eee4c4',
        'theme_background_accent_color': '#816555', 'theme_timeline_color': '#d6c399',
        'theme_brand_line_color': '#d8cfb2', 'theme_folder_arrow_color': '#97774b', 'theme_button_fill': '#9f8f6e',
        'theme_button_icon_color': '#816555', 'theme_button_text_color': '#816555',
        'theme_disabled_text_color': '#816555', 'theme_text_color': '#97774b', 'theme_secondary_text_color': '#97774b',
        'theme_heading_text_color': '#97774b', 'theme_brand_text_color': '#da7d5d',
        'theme_selected_text_color': '#97774b', 'theme_timeline_text_color': '#97774b',
        'theme_paper_text_color': '#97774b'},
}
THEME_CHOICE_KEYS = (*FIXED_THEMES['fixed_light'], 'custom_theme_colors', 'selected_color_theme',
                     'artwork_theme_enabled', 'artwork_theme_mode')


def system_theme_choice():
    return {Qt.ColorScheme.Dark: 'fixed_dark', Qt.ColorScheme.Light: 'fixed_light'}.get(
        QApplication.styleHints().colorScheme(), 'any')


def apply_system_theme(settings):
    for key, value in FIXED_THEMES.get(system_theme_choice(), {}).items():
        settings.setValue(key, value)


def fixed_palette(mode):
    colors = FIXED_THEMES[mode]
    return tuple(colors[key] for key in ('theme_background_color', 'theme_text_color', 'theme_highlight_color',
                                         'theme_accent_color', 'theme_background_accent_color'))


def paint_cover(painter, rect, background, text, button, accent, rail):
    paper = max(text, rail, button, key=QColor.lightnessF) if text.lightnessF() > background.lightnessF() else background.lighter(106)
    painter.fillRect(rect, paper)
    painter.setClipRect(rect)
    painter.setPen(Qt.NoPen)
    x, y, side = rect.x(), rect.y(), rect.width()
    painter.setBrush(accent)
    painter.drawEllipse(QRectF(x + side * .56, y + side * .14, side * .26, side * .26))
    painter.setBrush(button)
    painter.drawEllipse(QRectF(x - side * .3, y + side * .5, side * 1.1, side))
    painter.setBrush(text if paper != text else rail)
    painter.drawEllipse(QRectF(x + side * .3, y + side * .66, side, side))
    painter.setClipping(False)


def paint_case(painter, x, y, side, background, text, button, accent, rail):
    spine = side * .13
    edge = side * .035
    painter.setPen(Qt.NoPen)
    painter.setBrush(shadow_color(70, background))
    painter.drawRoundedRect(QRectF(x - 4, y + 3, side + 4, side + 5), 4, 4)
    painter.setBrush(QColor('#d6d6d2'))
    painter.drawRoundedRect(QRectF(x, y, side, side), 4, 4)
    painter.fillRect(QRectF(x + 3, y + 3, spine, side - 6), QColor('#2f332f'))
    paint_cover(painter, QRectF(x + spine + edge, y + edge, side - spine - edge * 2, side - edge * 2),
                background, text, button, accent, rail)


def example_image(mode):
    """Draw a small Albums view in the option's colors, with the app's chunky controls and CD cases."""
    palettes = {
        'any': ('#7f8459', '#e8dfc4', '#465640', '#f0883a', '#c7b27a'),
        'dark': ('#26242c', '#e9efec', '#8a9656', '#d85a42', '#3d4c67'),
        'light': ('#fadcc7', '#592430', '#886e91', '#de6c71', '#e4988a'),
        'fixed_dark': fixed_palette('fixed_dark'),
        'fixed_light': fixed_palette('fixed_light'),
    }
    background, text, button, accent, rail = map(QColor, palettes[mode])
    panel = background
    pixmap = QPixmap(512, 512)
    pixmap.fill(background)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(panel)
    painter.drawRoundedRect(QRectF(16, 16, 164, 54), 6, 6)
    painter.drawRoundedRect(QRectF(16, 82, 164, 214), 6, 6)
    font = QFont(QApplication.font())
    font.setPixelSize(27)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(accent.darker(150))
    painter.drawText(QRectF(18, 19, 164, 54), Qt.AlignCenter, 'Album Drive')
    painter.setPen(accent)
    painter.drawText(QRectF(16, 16, 164, 54), Qt.AlignCenter, 'Album Drive')
    for row, width in enumerate((98, 74, 110, 84, 66)):
        y = 106 + row * 38
        painter.setPen(Qt.NoPen)
        painter.setBrush(text)
        painter.drawConvexPolygon([QPointF(30, y - 9), QPointF(30, y + 9), QPointF(44, y)])
        painter.setPen(QPen(text, 9, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(58, y), QPointF(58 + width, y))
    paint_case(painter, 44, 308, 112, background, text, button, accent, rail)
    paint_case(painter, 206, 96, 286, background, text, button, accent, rail)
    for left in (344, 424):
        paint_control(painter, pixmap, QRectF(left - CONTROL_HEADROOM, 16 - CONTROL_HEADROOM,
                                              72 + 2 * CONTROL_HEADROOM, 50 + CONTROL_HEADROOM), button,
                      depth=7, rounding=30)
    painter.setPen(Qt.NoPen)
    painter.setBrush(rail)
    painter.drawRoundedRect(QRectF(100, 456, 392, 34), 5, 5)
    painter.setBrush(button)
    painter.drawRoundedRect(QRectF(100, 456, 200, 34), 5, 5)
    paint_control(painter, pixmap, QRectF(16 - CONTROL_HEADROOM, 446 - CONTROL_HEADROOM,
                                          66 + 2 * CONTROL_HEADROOM, 50 + CONTROL_HEADROOM), accent,
                  depth=7, rounding=30)
    paint_control(painter, pixmap, QRectF(284 - CONTROL_HEADROOM, 448 - CONTROL_HEADROOM,
                                          36 + 2 * CONTROL_HEADROOM, 46 + CONTROL_HEADROOM), button,
                  depth=7, rounding=30)
    painter.setBrush(background)
    painter.drawRect(QRectF(39, 460, 7, 20))
    painter.drawRect(QRectF(52, 460, 7, 20))
    painter.end()
    return pixmap


CARD_SPACING = 6
CARD_TEXT_GAP = 4


class ColorChoice(QFrame):
    def __init__(self, mode, title, description, parent=None, compact=False):
        super().__init__(parent)
        self.setObjectName('welcomeColorChoice')
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        self.radio = ChunkyCheckBox(title)
        self.radio.setAccessibleName(title)
        image = QLabel()
        self.preview = example_image(mode)
        image.setPixmap(self.preview.scaled(104, 104, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        image.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        image.setAccessibleName(f'{title}: example album colors')
        image.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.image = image
        caption = QLabel(description)
        caption.setWordWrap(True)
        caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        if compact:
            row = QHBoxLayout()
            row.setSpacing(CARD_SPACING)
            row.addWidget(image)
            text = QVBoxLayout()
            text.setSpacing(CARD_TEXT_GAP)
            text.addWidget(self.radio)
            caption.setContentsMargins(CONTROL_HEADROOM, 0, 0, 0)
            text.addWidget(caption)
            text.addStretch()
            row.addLayout(text, 1)
            layout.addLayout(row)
        else:
            layout.addWidget(self.radio)
            layout.addWidget(image)
            layout.addWidget(caption)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            play_button_sound()
            self.radio.setChecked(True)
        super().mousePressEvent(event)


class StepPage(QWidget):
    """A setup step; hidden steps report no height so the stack fits only the visible one."""

    def heightForWidth(self, width):
        return -1 if self.isHidden() else super().heightForWidth(width)


class FirstRunDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle('First time setup — Album Drive')
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setSizeConstraint(QLayout.SetNoConstraint)
        outer.setContentsMargins(12, 12, 12, 12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)
        self.step_label = QLabel()
        self.step_label.setObjectName('muted')
        body.addWidget(self.step_label)
        self.heading = QLabel()
        self.heading.setObjectName('heading')
        self.heading.setWordWrap(True)
        body.addWidget(self.heading)
        self.subheading = QLabel('Let Album Drive change theme colors to match the playing album.')
        self.subheading.setWordWrap(True)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.library_folder = str(settings.value('browser_root', settings.value('folder', music_directory())))
        library_page = StepPage()
        library_layout = QVBoxLayout(library_page)
        library_layout.setContentsMargins(0, 0, 0, 0)
        explanation = QLabel('Choose your music library root. This is the root folder where you store your music, with artist and album folders inside.')
        explanation.setWordWrap(True)
        library_layout.addWidget(explanation)
        self.library_button = ThemedButton('Choose music folder')
        self.library_button.clicked.connect(self.choose_library)
        library_layout.addWidget(self.library_button)
        self.library_label = QLabel(wrappable_path(self.library_folder) or 'No folder selected. You can choose one later in settings.')
        self.library_label.setWordWrap(True)
        library_layout.addWidget(self.library_label)
        library_layout.addStretch()
        self.pages.addWidget(library_page)
        from theme_settings import NumericSlider
        self.original_button_properties = {prop: QApplication.instance().property(prop)
                                           for prop in ('uiThickness', 'cornerRoundness', 'buttonSoundVolume')}
        button_page = StepPage()
        button_layout = QVBoxLayout(button_page)
        button_layout.setContentsMargins(0, 0, 0, 0)
        explanation = QLabel('Choose how your buttons look and sound.')
        explanation.setWordWrap(True)
        button_layout.addWidget(explanation)
        button_form = QFormLayout()
        self.button_form = button_form
        self.button_thickness = NumericSlider(NUMERIC_DEFAULTS['ui_thickness'], 0, 300, ' px', 25, display_scale=.04)
        self.button_roundness = NumericSlider(NUMERIC_DEFAULTS['corner_roundness'], 0, 100, ' %', 1)
        self.button_volume = NumericSlider(NUMERIC_DEFAULTS['button_sound_volume'], 0, 100, ' %', 1)
        for label, key, control in (('Button thickness', 'ui_thickness', self.button_thickness),
                                    ('Corner roundness', 'corner_roundness', self.button_roundness),
                                    ('Button sound volume', 'button_sound_volume', self.button_volume)):
            control.setValue(settings.value(key, NUMERIC_DEFAULTS[key], type=int))
            control.slider.setAccessibleName(label)
            button_form.addRow(label, control)
            control.slider.valueChanged.connect(self.preview_buttons)
        button_layout.addLayout(button_form)
        self.button_preview = ThemedButton('Try a button')
        button_layout.addWidget(self.button_preview, alignment=Qt.AlignHCenter)
        hint = QLabel('0 px makes buttons flat and silent. Set volume to 0% to mute clicks.')
        hint.setWordWrap(True)
        button_layout.addWidget(hint)
        button_layout.addStretch()
        self.pages.addWidget(button_page)
        choices_page = StepPage()
        categories = QHBoxLayout(choices_page)
        self.categories = categories
        categories.setContentsMargins(0, 0, 0, 0)
        categories.setSpacing(14)
        self.dynamic_category = QWidget()
        dynamic = QVBoxLayout(self.dynamic_category)
        dynamic.setContentsMargins(0, 0, 0, 0)
        dynamic_heading = QLabel('Dynamic colors')
        dynamic_heading.setObjectName('settingsSection')
        dynamic.addWidget(dynamic_heading)
        dynamic.addWidget(self.subheading)
        self.fixed_category = QWidget()
        fixed = QVBoxLayout(self.fixed_category)
        fixed.setContentsMargins(0, 0, 0, 0)
        fixed_heading = QLabel('Fixed colors')
        fixed_heading.setObjectName('settingsSection')
        fixed.addWidget(fixed_heading)
        fixed_hint = QLabel('You can manually tune the colors in the Settings')
        fixed_hint.setWordWrap(True)
        fixed.addWidget(fixed_hint)
        categories.addWidget(self.dynamic_category, 1)
        categories.addWidget(self.fixed_category, 1)
        self.group = QButtonGroup(self)
        self.choices = {}
        options = (
            ('any', 'any', 'Use what fits the album art.'),
            ('dark', 'dark', 'Favor darker colors.'),
            ('light', 'light', 'Favor lighter colors.'),
            ('fixed_dark', 'dark', 'Warm, dark colors.'),
            ('fixed_light', 'light', 'Soft, light colors.'),
        )
        for mode, title, description in options:
            card = ColorChoice(mode, title, description, compact=True)
            self.choices[mode] = card.radio
            self.group.addButton(card.radio)
            (fixed if mode in FIXED_THEMES else dynamic).addWidget(card)
        dynamic.addStretch(1)
        fixed.addStretch(1)
        self.original_theme = {key: settings.value(key) for key in THEME_CHOICE_KEYS if settings.contains(key)}
        self.kept_choice = None
        self.previewing = False
        self.choices['any'].setChecked(True)
        self.group.buttonToggled.connect(self.choice_toggled)
        self.pages.insertWidget(1, choices_page)
        reminder = QLabel('You can change this anytime in Settings → General.')
        self.reminder = reminder
        reminder.setWordWrap(True)
        body.addWidget(reminder)
        actions = QHBoxLayout()
        self.back_button = ThemedButton('Back')
        self.back_button.clicked.connect(lambda: self.set_step(max(0, self.pages.currentIndex() - 1)))
        actions.addWidget(self.back_button)
        actions.addStretch()
        self.next_button = ThemedButton('Next')
        self.next_button.setProperty('themeRole', 'highlight')
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self.advance)
        actions.addWidget(self.next_button)
        outer.addLayout(actions)
        self.button_volume_title = button_form.labelForField(self.button_volume)
        self.button_volume_title.setProperty('settingsOptionTitle', True)
        self.preview_buttons()
        self.set_step(0)
        for label in content.findChildren(QLabel):
            if label.wordWrap():
                label.setMinimumWidth(0)
                wrap_freely(label)
        ScreenFit(self, 900, 680)
        self.update_layout()

    def update_layout(self):
        narrow = self.width() < 640
        index = self.pages.currentIndex()
        self.library_button.setText('Browse' if narrow else 'Choose music folder')
        self.next_button.setText(('Start' if narrow else 'Start listening') if index == self.pages.count() - 1 else
                                 ('Skip' if narrow else 'Skip for now') if index == 0 and not self.library_folder else 'Next')
        self.categories.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self.button_form.setRowWrapPolicy(QFormLayout.WrapAllRows if narrow else QFormLayout.DontWrapRows)
        for radio in self.choices.values():
            card = radio.parentWidget()
            size = 72 if narrow else 104
            card.image.setPixmap(card.preview.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout()

    def selected_mode(self):
        return next(mode for mode, radio in self.choices.items() if radio.isChecked())

    def set_step(self, index):
        for page_index in range(self.pages.count()):
            self.pages.widget(page_index).setSizePolicy(
                QSizePolicy.Preferred if page_index == index else QSizePolicy.Ignored,
                QSizePolicy.Preferred if page_index == index else QSizePolicy.Ignored)
        self.pages.setCurrentIndex(index)
        self.pages.updateGeometry()
        self.step_label.setText(f'Step {index + 1} of {self.pages.count()}')
        self.heading.setText(('Choose your music library', '', 'Make it feel right')[index])
        self.heading.setVisible(index != 1)
        self.back_button.setVisible(index > 0)
        self.update_layout()
        self.reminder.setText('Change button shape in Settings → Style and sound volume in Settings → Audio.'
                              if index == 2 else 'Find saved themes in Settings → Style.')
        self.reminder.setVisible(index != 1)
        self.scroll.verticalScrollBar().setValue(0)

    def advance(self):
        if self.pages.currentIndex() < self.pages.count() - 1:
            self.set_step(self.pages.currentIndex() + 1)
        else:
            self.accept()

    def keep_current_colors(self):
        self.kept_choice = self.selected_mode()

    def choice_colors(self):
        mode = self.selected_mode()
        if mode == self.kept_choice:
            return None
        base = {'any': system_theme_choice(), 'dark': 'fixed_dark', 'light': 'fixed_light'}.get(mode, mode)
        return FIXED_THEMES.get(base)

    def store_choice_colors(self):
        colors = self.choice_colors()
        if colors is None:
            self.restore_original_theme()
            return
        for key, value in colors.items():
            self.settings.setValue(key, value)
        self.settings.setValue('custom_theme_colors', json.dumps(colors))
        self.settings.setValue('selected_color_theme', '')
        mode = self.selected_mode()
        self.settings.setValue('artwork_theme_enabled', mode not in FIXED_THEMES)
        self.settings.setValue('artwork_theme_mode', mode.removeprefix('fixed_'))

    def restore_original_theme(self):
        for key in THEME_CHOICE_KEYS:
            if key in self.original_theme:
                self.settings.setValue(key, self.original_theme[key])
            else:
                self.settings.remove(key)

    def choice_toggled(self, _button, checked):
        if checked:
            self.preview_choice()

    def player_window(self):
        window = self.parent()
        while window is not None and not hasattr(window, 'apply_settings'):
            window = window.parent()
        return window

    def preview_choice(self):
        window = self.player_window()
        if window is None or not self.isVisible():
            return
        self.previewing = True
        self.store_choice_colors()
        window.apply_settings()
        self.preview_buttons()

    def accept(self):
        self.store_choice_colors()
        if self.library_folder and Path(self.library_folder).is_dir():
            self.settings.setValue('browser_root', self.library_folder)
            self.settings.setValue('folder', self.library_folder)
        self.settings.setValue('ui_thickness', self.button_thickness.value())
        self.settings.setValue('corner_roundness', self.button_roundness.value())
        self.settings.setValue('button_sound_volume', self.button_volume.value())
        mode = self.selected_mode()
        self.settings.setValue('artwork_theme_enabled', mode not in FIXED_THEMES)
        self.settings.setValue('artwork_theme_mode', mode.removeprefix('fixed_'))
        self.settings.setValue('selected_color_theme', '')
        self.settings.setValue('welcome_complete', True)
        self.settings.sync()
        super().accept()

    def choose_library(self):
        folder = choose_music_directory(self, 'Choose music library root', self.library_folder or music_directory())
        if folder:
            self.library_folder = folder
            self.library_label.setText(wrappable_path(folder))
            self.next_button.setText('Next')

    def preview_buttons(self):
        app = QApplication.instance()
        app.setProperty('uiThickness', self.button_thickness.value())
        app.setProperty('cornerRoundness', self.button_roundness.value())
        app.setProperty('buttonSoundVolume', self.button_volume.value())
        self.button_volume.setEnabled(self.button_thickness.value() > 0)
        self.button_volume_title.setEnabled(self.button_volume.isEnabled())
        prepare_button_sounds()
        for widget in self.findChildren(QWidget):
            widget.update()

    def reject(self):
        app = QApplication.instance()
        for prop, value in self.original_button_properties.items():
            app.setProperty(prop, value)
        prepare_button_sounds()
        if self.previewing:
            self.restore_original_theme()
            self.player_window().apply_settings()
        super().reject()
