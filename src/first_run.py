"""First-run setup for the music library, buttons, album colors and saved themes."""

from pathlib import Path
from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, QSizeF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QRadioButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from themes import CONTROL_HEADROOM, ThemedButton, ThemeSaveIcon, button_paint_rect, button_scale, control_face, corner_radius, paint_control, NUMERIC_DEFAULTS
from button_sounds import prepare_button_sounds


def needs_first_run(settings):
    if settings.value('welcome_complete', False, type=bool):
        return False
    if settings.value('welcome_started', False, type=bool):
        return True
    return not any(settings.contains(key) for key in
                   ('window_geometry', 'folder', 'browser_root', 'custom_theme_colors'))


def example_image(mode):
    """Draw illustrative app previews, with the same cover in each palette."""
    palettes = {
        'any': ('#456e76', '#e9a36b', '#e5e8df', '#ffffff'),
        'dark': ('#202b3b', '#7899bc', '#b9cad5', '#ffffff'),
        'light': ('#e8ddd0', '#b06e4a', '#fff9ed', '#242833'),
        'off': ('#393939', '#888888', '#cccccc', '#ffffff'),
    }
    background, accent, fill, text = map(QColor, palettes[mode])
    pixmap = QPixmap(512, 512)
    pixmap.fill(background)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillRect(QRectF(0, 0, 112, 448), background.darker(115))
    painter.setPen(text)
    font = QFont(QApplication.font())
    font.setPixelSize(20)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(132, 18, 150, 30), 'Albums')
    font.setPixelSize(12)
    painter.setFont(font)
    painter.drawText(QRectF(12, 20, 100, 24), 'Album Drive')
    for y, width in ((82, 90), (112, 72), (142, 85), (172, 63), (202, 77)):
        painter.setPen(QPen(text, 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(20, y), QPointF(width, y))
    for x, y in ((132, 86), (316, 86), (132, 262), (316, 262)):
        painter.setPen(QPen(accent, 3))
        painter.setBrush(background.lighter(120))
        painter.drawRoundedRect(QRectF(x, y, 164, 148), corner_radius(3), corner_radius(3))
        painter.fillRect(QRectF(x + 14, y + 7, 134, 134), QColor('#e7ac83'))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#466a77'))
        painter.drawEllipse(QRectF(x + 40, y + 30, 82, 82))
        painter.setBrush(QColor('#f4debc'))
        painter.drawEllipse(QRectF(x + 64, y + 54, 34, 34))
        painter.setPen(QPen(background.darker(150), 3))
        painter.drawLine(QPointF(x + 8, y + 5), QPointF(x + 8, y + 142))
    painter.setPen(QPen(accent, 3))
    for rect in (QRectF(378, 20, 104, 32), QRectF(18, 462, 44, 32)):
        paint_control(painter, pixmap, rect.adjusted(-CONTROL_HEADROOM, -CONTROL_HEADROOM, CONTROL_HEADROOM, 0), fill)
    painter.setPen(Qt.NoPen)
    painter.setBrush(background.darker(130))
    painter.drawRoundedRect(QRectF(132, 475, 350, 8), 3, 3)
    painter.setBrush(accent)
    painter.drawRoundedRect(QRectF(132, 475, 130, 8), 3, 3)
    painter.end()
    return pixmap


class ColorChoice(QFrame):
    def __init__(self, mode, title, description, parent=None, compact=False):
        super().__init__(parent)
        self.setObjectName('welcomeColorChoice')
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        self.radio = QRadioButton(title)
        self.radio.setAccessibleName(title)
        image = QLabel()
        image.setPixmap(example_image(mode).scaled(104, 104,
                                                  Qt.KeepAspectRatio, Qt.SmoothTransformation))
        image.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        image.setAccessibleName(f'{title}: example album colors')
        image.setAttribute(Qt.WA_TransparentForMouseEvents)
        caption = QLabel(description)
        caption.setWordWrap(True)
        caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        if compact:
            row = QHBoxLayout()
            row.addWidget(image)
            text = QVBoxLayout()
            text.addWidget(self.radio)
            text.addWidget(caption)
            row.addLayout(text, 1)
            layout.addLayout(row)
        else:
            layout.addWidget(self.radio)
            layout.addWidget(image)
            layout.addWidget(caption)
        self.radio.toggled.connect(self.update_border)
        self.update_border()

    def update_border(self):
        app = QApplication.instance()
        accent = app.property('themeAccent') or '#888888'
        text = app.property('textColor') or '#ffffff'
        self.setStyleSheet(f'''
QFrame#welcomeColorChoice {{ border: 2px solid {accent if self.radio.isChecked() else 'transparent'}; border-radius: 8px; }}
QRadioButton {{ color: {text}; font-weight: bold; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border: 2px solid {accent}; border-radius: 8px; }}
QRadioButton::indicator:checked {{ background: {accent}; }}
''')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.radio.setChecked(True)
        super().mousePressEvent(event)


def theme_save_image(window):
    while window is not None and not hasattr(window, 'save_theme_button'):
        window = window.parentWidget()
    button = getattr(window, 'save_theme_button', None)
    if button is not None:
        area = button.parentWidget()
        width = min(800, area.width())
        crop = QRect(max(0, min(button.x() - 420, area.width() - width)), 0,
                     width, min(area.height(), max(160, button.geometry().bottom() + 90)))
        image = area.grab(crop)
        target = control_face(button_paint_rect(button), widget=button).translated(button.pos() - crop.topLeft())
    else:
        app = QApplication.instance()
        image = QPixmap(512, 180)
        image.fill(QColor(app.property('themeBackground') or '#393939'))
        button = ThemedButton()
        button.setIcon(QIcon(ThemeSaveIcon()))
        size = round(app.property('buttonIconSize') or 20)
        button.setIconSize(QSize(round(size * 1.5), size))
        button.resize(round(64 * button_scale()) + 2 * CONTROL_HEADROOM, button.sizeHint().height())
        position = QPointF((image.width() - button.width()) / 2, 12)
        painter = QPainter(image)
        painter.drawPixmap(position, button.grab())
        painter.end()
        target = control_face(button_paint_rect(button), widget=button).translated(position)
        button.deleteLater()
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    app = QApplication.instance()
    color = QColor(app.property('textColor') or '#ffffff')
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(color, 2))
    painter.drawRoundedRect(target.adjusted(-4, -4, 4, 4), 6, 6)
    x, y = target.center().x(), target.bottom() + 8
    painter.drawLine(QPointF(x, y + 26), QPointF(x, y))
    painter.drawLine(QPointF(x, y), QPointF(x - 5, y + 7))
    painter.drawLine(QPointF(x, y), QPointF(x + 5, y + 7))
    label = QRectF(max(0, min(x - 75, image.width() - 150)), y + 30, 150, 30)
    painter.fillRect(label, QColor(app.property('themeBackground') or '#393939'))
    painter.setPen(color)
    painter.drawText(label, Qt.AlignCenter, 'Save theme')
    painter.end()
    return image


class ThemeSavePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QPixmap()
        self.source_window = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(40)
        self.refresh_timer.timeout.connect(self.refresh)
        QApplication.instance().installEventFilter(self)
        self.setAccessibleName('Save theme button in the top right of the Albums view, beside Refresh')
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def sizeHint(self):
        return QSize(720, 200)

    def capture(self, window):
        self.source_window = window
        self.image = theme_save_image(window)
        self.update()

    def refresh(self):
        if self.isVisible():
            self.capture(self.source_window)

    def eventFilter(self, watched, event):
        if watched is QApplication.instance() and event.type() == QEvent.DynamicPropertyChange:
            if bytes(event.propertyName()) in (b'themeBackground', b'themeAccent', b'textColor', b'buttonFill',
                                               b'buttonIconColor', b'playerTheme', b'uiThickness', b'cornerRoundness',
                                               b'buttonSize', b'buttonIconSize') and self.isVisible():
                if not self.refresh_timer.isActive():
                    self.refresh_timer.start()
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        self.refresh_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        if self.image.isNull():
            return
        target = QRectF(0, 0, self.image.width(), self.image.height())
        target.setSize(QSizeF(self.image.size().scaled(self.size(), Qt.KeepAspectRatio)))
        target.moveCenter(QRectF(self.rect()).center())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, self.image, QRectF(self.image.rect()))


class FirstRunDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle('First time setup — Album Drive')
        self.setModal(True)
        self.resize(900, 680)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(10)
        self.step_label = QLabel()
        self.step_label.setObjectName('muted')
        outer.addWidget(self.step_label)
        self.heading = QLabel()
        self.heading.setObjectName('heading')
        outer.addWidget(self.heading)
        self.subheading = QLabel('Let Album Drive change theme colors to match the playing album.')
        self.subheading.setWordWrap(True)
        outer.addWidget(self.subheading)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages)
        self.library_folder = str(settings.value('browser_root', settings.value('folder', '')))
        library_page = QWidget()
        library_layout = QVBoxLayout(library_page)
        library_layout.setContentsMargins(0, 0, 0, 0)
        explanation = QLabel('Choose your music library root. This is usually the root folder where you store your music, with artist and album folders inside.')
        explanation.setWordWrap(True)
        library_layout.addWidget(explanation)
        self.library_button = ThemedButton('Choose music folder')
        self.library_button.clicked.connect(self.choose_library)
        library_layout.addWidget(self.library_button)
        self.library_label = QLabel(self.library_folder or 'No folder selected. You can choose one later in settings.')
        self.library_label.setWordWrap(True)
        library_layout.addWidget(self.library_label)
        library_layout.addStretch()
        self.pages.addWidget(library_page)
        from theme_settings import NumericSlider
        self.original_button_properties = {prop: QApplication.instance().property(prop)
                                           for prop in ('uiThickness', 'cornerRoundness', 'buttonSoundVolume')}
        button_page = QWidget()
        button_layout = QVBoxLayout(button_page)
        button_layout.setContentsMargins(0, 0, 0, 0)
        explanation = QLabel('Choose how your buttons look and sound. Click the preview to try them.')
        explanation.setWordWrap(True)
        button_layout.addWidget(explanation)
        button_form = QFormLayout()
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
        button_layout.addWidget(QLabel('0 px makes buttons flat and silent. Set volume to 0% to mute clicks.'))
        button_layout.addStretch()
        self.pages.addWidget(button_page)
        choices_page = QWidget()
        categories = QHBoxLayout(choices_page)
        categories.setContentsMargins(0, 0, 0, 0)
        categories.setSpacing(14)
        self.dynamic_category = QWidget()
        dynamic = QVBoxLayout(self.dynamic_category)
        dynamic.setContentsMargins(0, 0, 0, 0)
        dynamic_heading = QLabel('Dynamic colors')
        dynamic_heading.setObjectName('settingsSection')
        dynamic.addWidget(dynamic_heading)
        self.fixed_category = QWidget()
        fixed = QVBoxLayout(self.fixed_category)
        fixed.setContentsMargins(0, 0, 0, 0)
        fixed_heading = QLabel('Fixed colors')
        fixed_heading.setObjectName('settingsSection')
        fixed.addWidget(fixed_heading)
        categories.addWidget(self.dynamic_category, 1)
        categories.addWidget(self.fixed_category, 1)
        self.group = QButtonGroup(self)
        self.choices = {}
        options = (
            ('any', 'any', 'Use light or dark colors to match each album.'),
            ('dark', 'dark', 'Favor deeper, darker colors.'),
            ('light', 'light', 'Favor softer, lighter colors.'),
            ('off', 'no dynamic colors', 'Keep a steady, neutral theme.'),
        )
        for mode, title, description in options:
            card = ColorChoice(mode, title, description, compact=True)
            self.choices[mode] = card.radio
            self.group.addButton(card.radio)
            (fixed if mode == 'off' else dynamic).addWidget(card)
        dynamic.addStretch()
        fixed.addStretch()
        self.choices['any'].setChecked(True)
        self.pages.addWidget(choices_page)
        tutorial = QWidget()
        instructions = QVBoxLayout(tutorial)
        instructions.setContentsMargins(0, 0, 0, 0)
        instructions.setSpacing(14)
        text = QLabel()
        self.instructions_label = text
        text.setWordWrap(True)
        instructions.addWidget(text)
        self.save_preview = ThemeSavePreview()
        instructions.addWidget(self.save_preview, 1)
        saved = QLabel('Find saved themes at the top of Settings → Style.\n'
                       'Choose it anytime to bring those colors back.')
        saved.setWordWrap(True)
        instructions.addWidget(saved)
        instructions.addStretch()
        self.pages.addWidget(tutorial)
        reminder = QLabel('You can change this anytime in Settings → General.')
        self.reminder = reminder
        reminder.setWordWrap(True)
        outer.addWidget(reminder)
        actions = QHBoxLayout()
        self.back_button = ThemedButton('Back')
        self.back_button.clicked.connect(lambda: self.set_step(max(0, self.pages.currentIndex() - 1)))
        actions.addWidget(self.back_button)
        actions.addStretch()
        self.next_button = ThemedButton('Next')
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self.advance)
        actions.addWidget(self.next_button)
        outer.addLayout(actions)
        self.button_volume_title = button_form.labelForField(self.button_volume)
        self.button_volume_title.setProperty('settingsOptionTitle', True)
        self.preview_buttons()
        self.set_step(0)

    def selected_mode(self):
        return next(mode for mode, radio in self.choices.items() if radio.isChecked())

    def set_step(self, index):
        self.pages.setCurrentIndex(index)
        self.step_label.setText(f'Step {index + 1} of 4')
        self.heading.setText(('Choose your music library', 'Make it feel right', 'Dynamic theming', 'Keep a color theme you love')[index])
        self.subheading.setVisible(index == 2)
        self.back_button.setVisible(index > 0)
        self.next_button.setText('Start listening' if index == 3 else 'Skip for now' if index == 0 and not self.library_folder else 'Next')
        self.reminder.setText('Change button shape in Settings → Style and sound volume in Settings → Audio.'
                              if index == 1 else 'Find saved themes and appearance in Settings → Style.')
        if index == 3:
            first = ('1. Choose your colors in Settings → Style.' if self.selected_mode() == 'off'
                     else '1. Play an album and let its colors appear.')
            self.instructions_label.setText(first + '\n2. In the Albums view, press the paintbrush and save button beside Refresh.\n'
                                            'Your theme is saved immediately, named after the playing album.')
            self.save_preview.capture(self.parentWidget())

    def advance(self):
        if self.pages.currentIndex() < 3:
            self.set_step(self.pages.currentIndex() + 1)
        else:
            self.accept()

    def accept(self):
        if self.selected_mode() == 'off':
            from theme_settings import custom_color_settings
            for key, value in custom_color_settings(self.settings).items():
                self.settings.setValue(key, value)
        if self.library_folder and Path(self.library_folder).is_dir():
            self.settings.setValue('browser_root', self.library_folder)
            self.settings.setValue('folder', self.library_folder)
        self.settings.setValue('ui_thickness', self.button_thickness.value())
        self.settings.setValue('corner_roundness', self.button_roundness.value())
        self.settings.setValue('button_sound_volume', self.button_volume.value())
        mode = self.selected_mode()
        self.settings.setValue('artwork_theme_enabled', mode != 'off')
        self.settings.setValue('artwork_theme_mode', mode if mode != 'off' else 'any')
        self.settings.setValue('selected_color_theme', '')
        self.settings.setValue('welcome_complete', True)
        self.settings.sync()
        super().accept()

    def choose_library(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choose music library root', self.library_folder or str(Path.home() / 'Music'))
        if folder:
            self.library_folder = folder
            self.library_label.setText(folder)
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
        super().reject()
