import os
import tempfile
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QScrollBar, QStyle, QStyleOptionSlider, QWidget
from color_rules import emphasized_text, settings_title_color, slider_rail
from live_scrollbars import install_live_scrollbars
from theme_settings import SECTION_GAP, SETTING_INDENT, ThemeSettingsDialog
from themes import BUTTON_SHADOW, CONTROL_HEADROOM, ChunkyBrand, ChunkyCheckBox, ThemedButton, ThemeSlider, button_paint_rect, button_scale, chunky_style, control_face, control_shadow, text_style


app = QApplication([])
app.setStyle('Fusion')
app.setProperty('playerTheme', 'chunky')
app.setProperty('themeAccent', '#80b060')
app.setProperty('uiThickness', 0)
app.setProperty('cornerRoundness', 0)
app.setProperty('buttonTextColor', '#111111')
install_live_scrollbars(app)
with tempfile.TemporaryDirectory() as directory:
    settings = QSettings(directory + '/settings.ini', QSettings.IniFormat)
    dialog = ThemeSettingsDialog(settings)
    dialog.resize(850, 850)
    dialog.show()
    for background in ('#000000', '#393939', '#e3d2c1'):
        app.setProperty('themeBackground', background)
        text = '#b0c0d0' if QColor(background).lightnessF() < .5 else '#405060'
        app.setProperty('textColor', text)
        app.setStyleSheet(chunky_style('QWidget { background: ' + background + '; }') + text_style())
        QTest.qWait(20)
        page = dialog.tabs.widget(0).widget()
        image = page.grab().toImage()
        headings = page.findChildren(QLabel, 'settingsSection')
        assert len(headings) == 2
        assert [heading.text() for heading in headings[:2]] == ['Music library', 'Playback']
        title = dialog.library_label
        assert title.x() - headings[0].x() == SETTING_INDENT
        category_color = emphasized_text(text, background, .2)
        title_color = settings_title_color(text, background)
        assert (category_color.lightnessF() > title_color.lightnessF()) == (QColor(background).lightnessF() < .5)
        heading_image = headings[0].grab().toImage()
        assert any(heading_image.pixelColor(x, y).name() == category_color.name()
                   for y in range(heading_image.height()) for x in range(heading_image.width()))
        for index, heading in enumerate(headings):
            color = image.pixelColor(12, heading.geometry().center().y())
            assert (color.name() != background) == bool(index % 2), (index, background, color.name())
        for form in dialog.forms.values():
            for spacer in form.parentWidget().findChildren(QWidget, 'settingsSectionSpacer'):
                assert spacer.height() >= SECTION_GAP
    dialog.reject()

app.setProperty('themeBackground', '#393939')
app.setStyleSheet(chunky_style('QWidget { background: #393939; }', accent='#80b060', roundness=0) + text_style())
button = ThemedButton('')
button.resize(144, 62)
button.show()
slider = ThemeSlider()
slider.setValue(50)
slider.resize(240, 64)
slider.show()
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    QTest.qWait(10)
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
    for widget, outer in ((button, button_paint_rect(button)), (slider, QRectF(handle))):
        image = widget.grab().toImage()
        base = control_face(outer, pressed=True, widget=widget)
        face = control_face(outer, widget=widget)
        assert image.pixelColor(face.center().toPoint()) == QColor('#80b060')
        extent = round(control_shadow().y())
        x = round(base.center().x())
        y = round(base.bottom()) + max(1, extent // 2)
        shadow = image.pixelColor(x, y)
        assert (shadow.alpha() > 0 and shadow.lightness() < QColor('#393939').lightness()) == bool(thickness), (thickness, widget, shadow.name())
button.close()
slider.close()
bar = QScrollBar(Qt.Vertical)
bar.setRange(0, 100)
bar.setPageStep(20)
bar.setValue(50)
bar.resize(48, 400)
bar.show()
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    QTest.qWait(10)
    option = QStyleOptionSlider()
    bar.initStyleOption(option)
    handle = bar.style().subControlRect(QStyle.CC_ScrollBar, option, QStyle.SC_ScrollBarSlider, bar)
    face = control_face(QRectF(handle), widget=bar)
    image = bar.grab().toImage()
    assert image.pixelColor(handle.center().x(), round(face.top()) - 2) == slider_rail('#393939')
    shade = image.pixelColor(round(face.left()) - 1, handle.center().y())
    assert (shade.lightness() < QColor('#393939').lightness()) == bool(thickness)
paper = QWidget()
paper.setProperty('paperBackgroundColor', '#f2efdf')
paper.resize(80, 450)
bar.setParent(paper)
bar.setGeometry(0, 0, 48, 400)
paper.show()
bar.show()
QTest.qWait(20)
image = bar.grab().toImage()
assert image.pixelColor(24, 35) == slider_rail('#f2efdf')
assert image.pixelColor(2, 10).name() == '#f2efdf'
bar.close()
paper.close()
checkbox = ChunkyCheckBox('')
checkbox.resize(checkbox.sizeHint())
checkbox.show()
brand = ChunkyBrand('Album Drive')
font = QFont(brand.font())
font.setPixelSize(27)
brand.setFont(font)
brand.resize(320, brand.sizeHint().height())
brand.show()
for thickness in (0, 100, 300):
    app.setProperty('uiThickness', thickness)
    QTest.qWait(10)
    image = checkbox.grab().toImage()
    size = 30 * button_scale()
    outer = QRectF(0, (checkbox.height() - size - CONTROL_HEADROOM - BUTTON_SHADOW) / 2,
                   size + 2 * CONTROL_HEADROOM, size + CONTROL_HEADROOM)
    base = control_face(outer, pressed=True, widget=checkbox)
    point = base.center().toPoint()
    point.setY(round(base.bottom() + max(1, control_shadow().y() / 2)))
    assert (image.pixelColor(point).lightness() < QColor('#393939').lightness()) == bool(thickness)
    actual = brand.grab().toImage()
    with patch('themes.lettering_shadow_pixmap', return_value=QPixmap()):
        plain = brand.grab().toImage()
    assert (actual != plain) == bool(thickness)
checkbox.close()
brand.close()
print('PASS: alternating theme sections, section gaps, downward left shadows and continuous scrollbar rails')
