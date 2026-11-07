"""Color selection with live HSV, RGB and hexadecimal controls."""

import re

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from responsive import ScreenFit
from themes import ColorSwatch, ThemeSlider, ThemedButton, corner_radius


class ColorField(QWidget):
    changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hue, self.saturation, self.value = 0., 0., 1.
        self.setMinimumSize(240, 190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName('Color saturation and brightness')
        self.setToolTip('Click or drag to choose saturation and brightness. Hue and RGB can also be adjusted with the keyboard.')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        clip = QPainterPath()
        clip.addRoundedRect(rect, corner_radius(8), corner_radius(8))
        painter.setClipPath(clip)
        gradient = QLinearGradient(rect.topLeft(), rect.topRight())
        gradient.setColorAt(0, QColor('white'))
        gradient.setColorAt(1, QColor.fromHsvF(self.hue, 1, 1))
        painter.fillRect(rect, gradient)
        shade = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        shade.setColorAt(0, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor('black'))
        painter.fillRect(rect, shade)
        point = QPointF(rect.left() + self.saturation * rect.width(), rect.bottom() - self.value * rect.height())
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor('black'), 5))
        painter.drawEllipse(point, 6, 6)
        painter.setPen(QPen(QColor('white'), 2))
        painter.drawEllipse(point, 6, 6)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(QApplication.instance().property('themeAccent') or '#95bd29'), 4))
        painter.drawPath(clip)

    def choose(self, point):
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        saturation = min(1., max(0., (point.x() - rect.left()) / rect.width()))
        value = min(1., max(0., (rect.bottom() - point.y()) / rect.height()))
        self.changed.emit(saturation, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.choose(event.position())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.choose(event.position())
            event.accept()
        else:
            super().mouseMoveEvent(event)


class ColorPickerDialog(QDialog):
    def __init__(self, initial, parent=None, title='Choose color'):
        super().__init__(parent)
        self.setWindowTitle(title)
        ScreenFit(self, 510, 590)
        self.color = QColor(initial)
        self.hue = max(0., self.color.hsvHueF())
        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(12, 12, 12, 12)
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(12)
        preview = QHBoxLayout()
        for label, name in (('Current', 'original'), ('New', 'preview')):
            column = QVBoxLayout()
            column.addWidget(QLabel(label))
            swatch = ColorSwatch(self.color, label)
            swatch.setFocusPolicy(Qt.NoFocus)
            swatch.setAttribute(Qt.WA_TransparentForMouseEvents)
            setattr(self, name, swatch)
            column.addWidget(swatch)
            preview.addLayout(column)
        outer.addLayout(preview)
        self.field = ColorField()
        self.field.changed.connect(self.choose_field)
        outer.addWidget(self.field, 1)
        form = QFormLayout()
        form.setSpacing(8)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.channels = {}
        self.values = {}
        for key, label, maximum in (('hue', 'Hue', 359), ('red', 'Red', 255), ('green', 'Green', 255), ('blue', 'Blue', 255)):
            row = QHBoxLayout()
            slider = ThemeSlider()
            slider.setRange(0, maximum)
            slider.setAccessibleName(label)
            value = QLabel()
            value.setMinimumWidth(44)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(slider, 1)
            row.addWidget(value)
            self.channels[key], self.values[key] = slider, value
            slider.valueChanged.connect(lambda value, channel=key: self.change_channel(channel, value))
            form.addRow(label, row)
        self.hex_edit = QLineEdit()
        self.hex_edit.setAccessibleName('Hexadecimal color')
        self.hex_edit.setPlaceholderText('#RRGGBB')
        self.hex_edit.textEdited.connect(self.edit_hex)
        form.addRow('Hex color', self.hex_edit)
        outer.addLayout(form)
        scroll = QScrollArea()
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.cancel_button = ThemedButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)
        self.accept_button = ThemedButton('Use color')
        self.accept_button.setDefault(True)
        self.accept_button.clicked.connect(self.accept)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.accept_button)
        root.addLayout(actions)
        app = QApplication.instance()
        self.hex_edit.setStyleSheet(f'''QLineEdit {{ background: {app.property('buttonFill') or '#eae7e2'};
            color: {app.property('buttonTextColor') or '#4c3f2f'}; border: 3px solid {app.property('themeAccent') or '#95bd29'};
            border-radius: {corner_radius(8):g}px; padding: 8px; }}''')
        self.set_color(self.color)

    def set_color(self, color, update_hex=True):
        self.color = QColor(color)
        if self.color.hsvHueF() >= 0:
            self.hue = self.color.hsvHueF()
        self.field.hue = self.hue
        self.field.saturation = self.color.hsvSaturationF()
        self.field.value = self.color.valueF()
        self.field.update()
        self.preview.set_color(self.color)
        for key, slider in self.channels.items():
            value = min(359, round(self.hue * 360)) if key == 'hue' else getattr(self.color, key)()
            with QSignalBlocker(slider):
                slider.setValue(value)
            self.values[key].setText(f'{value}°' if key == 'hue' else str(value))
        if update_hex:
            self.hex_edit.setText(self.color.name())
        self.accept_button.setEnabled(True)

    def choose_field(self, saturation, value):
        self.set_color(QColor.fromHsvF(self.hue, saturation, value))

    def change_channel(self, channel, value):
        if channel == 'hue':
            self.hue = value / 360
            self.set_color(QColor.fromHsvF(self.hue, self.field.saturation, self.field.value))
        else:
            color = QColor(self.color)
            getattr(color, 'set' + channel.title())(value)
            self.set_color(color)

    def edit_hex(self, text):
        valid = re.fullmatch(r'#?[0-9a-fA-F]{6}', text) is not None
        self.accept_button.setEnabled(valid)
        if valid:
            self.set_color(QColor('#' + text.lstrip('#')), update_hex=False)

    @staticmethod
    def getColor(initial, parent=None, title='Choose color'):
        dialog = ColorPickerDialog(initial, parent, title)
        return QColor(dialog.color) if dialog.exec() == QDialog.Accepted else QColor()
