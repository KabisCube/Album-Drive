"""Offscreen album scaling, saved size and built-in preference checks."""

import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QSize, Qt, QPoint, QRect, QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider

from main import PlayerWindow
from case_geometry import CASE_WIDTH, CASE_HEIGHT
from theme_settings import ThemeSettingsDialog
from themes import FONT_SCALE_KEYS, font_sizes, COLOR_SETTINGS, CONTROL_HEADROOM, NUMERIC_DEFAULTS, UI_FONT_DEFAULT, control_face
from test_library import make_wave


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for index in range(18):
        make_wave(root / 'Music' / f'Album {index:02}' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 18 and not window.scanners)
    assert window.album_size.x() < window.sort_albums.x()
    scale = NUMERIC_DEFAULTS['album_scale'] / 100
    assert window.grid.iconSize() == QSize(round(328 * scale), round(328 * CASE_HEIGHT / CASE_WIDTH * scale))
    assert window.album_size.width() == 140 + 2 * CONTROL_HEADROOM
    assert window.album_size.minimum() == 50
    assert window.album_size.maximum() == 150
    # Moving a fixed-width slider must not reuse a clipped opacity-effect cache.
    assert window.album_size.graphicsEffect() is None
    def check_knob():
        slider = window.album_size
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
        center = control_face(QRectF(handle), widget=slider).center().toPoint()
        color = slider.grab().toImage().pixelColor(center).name()
        assert (color == app.property('themeAccent')) == (slider.paint_opacity == 1)

    for opacity in (1.0, .2, 1.0):
        window.set_album_backdrop_opacity(opacity)
        assert window.album_size.paint_opacity == opacity
        for width, height in ((1420, 860), (1040, 640), (1220, 730), (980, 620), (1500, 900)):
            window.resize(width, height)
            app.processEvents()
            check_knob()
            slider = window.album_size
            assert slider.width() == 140 + 2 * CONTROL_HEADROOM
            assert slider.parentWidget().rect().contains(slider.geometry())
            area = QRect(slider.mapTo(window, QPoint()), slider.size())
            assert window.rect().contains(area)
            QTest.mouseMove(window, QPoint(1, 1))
            before_hover = window.grab(area).toImage()
            QTest.mouseMove(slider, slider.rect().center())
            app.processEvents()
            assert before_hover == window.grab(area).toImage(), 'Slider changed after hover following resize'
    window.show_album(window.albums[0], play_sound=False)
    app.processEvents()
    assert window.album_size.paint_opacity == .2
    check_knob()
    window.show_albums(play_sound=False)
    app.processEvents()
    check_knob()
    window.album_size.setValue(300)
    assert window.album_size.value() == 150
    assert int(settings.value('album_scale')) == 150
    window.album_size.setValue(0)
    assert window.album_size.value() == 50
    assert int(settings.value('album_scale')) == 50
    window.album_size.setValue(100)
    assert window.sort_albums.currentData() == 'newest'
    assert window.volume.value() == 100
    assert app.property('cornerRoundness') == NUMERIC_DEFAULTS['corner_roundness']
    assert app.property('buttonFontSize') == NUMERIC_DEFAULTS['button_font_size']
    assert app.property('trackListFamily') == 'Album Round'

    window.sort_albums.setCurrentIndex(window.sort_albums.findData('custom'))
    window.grid.move_album(0, 3)
    order = [window.grid.item(row).data(Qt.UserRole) for row in range(18)]
    window.grid.setCurrentRow(4)
    selected = window.grid.currentItem()
    for percent in (50, 150, 75, 150):
        window.album_size.setValue(percent)
        QTest.qWait(40)
        assert window.grid.iconSize() == QSize(round(328 * percent / 100), round(328 * CASE_HEIGHT / CASE_WIDTH * percent / 100))
        assert window.grid.gridSize().width() == window.grid.iconSize().width() + 12 + 5
        assert window.grid.currentItem() is selected
        assert [window.grid.item(row).data(Qt.UserRole) for row in range(18)] == order
        assert window.grid.visualItemRect(selected).intersects(window.grid.viewport().rect())
    window.close()
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    restored.show()
    wait_until(lambda: len(restored.albums) == 18 and not restored.scanners)
    assert restored.album_size.value() == 150
    assert restored.grid.iconSize() == QSize(492, round(492 * CASE_HEIGHT / CASE_WIDTH))
    assert [str(restored.albums[restored.grid.item(row).data(Qt.UserRole)].folder)
            for row in range(18)] == settings.value(restored.custom_order_key())

    dialog = ThemeSettingsDialog(settings, restored)
    dialog.applied.connect(restored.apply_settings)
    dialog.select_ui_font('AlbumRound-Bold.ttf::Album Round')
    assert dialog.ui_font_choice.currentData() == UI_FONT_DEFAULT
    for control in dialog.numbers.values():
        control.setValue(control.maximum())
    dialog.restore_defaults()
    assert dialog.ui_font_choice.currentData() == UI_FONT_DEFAULT
    assert not dialog.cleaning.isChecked()
    assert dialog.rounding_slider.value() == NUMERIC_DEFAULTS['corner_roundness']
    for key, control in dialog.numbers.items():
        assert control.value() == (100 if key in FONT_SCALE_KEYS and key not in ('secondary_font_size', 'menu_font_size') else NUMERIC_DEFAULTS[key])
    for _, _, key, _, color in COLOR_SETTINGS:
        from app_theme import simplify_color_settings
        defaults = simplify_color_settings({entry[2]: entry[4] for entry in COLOR_SETTINGS})
        assert dialog.colors[key].color().name() == defaults[key]
    dialog.apply()
    assert restored.album_size.value() == NUMERIC_DEFAULTS['album_scale']
    assert restored.grid.iconSize() == QSize(round(328 * scale), round(328 * CASE_HEIGHT / CASE_WIDTH * scale))
    dialog.close()
    restored.close()

print('PASS: album size range, stable custom order/selection, persisted scaling and complete appearance defaults')
