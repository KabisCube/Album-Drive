import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QRectF, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider

from main import PlayerWindow
from themes import button_paint_rect, control_face


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'Music').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('theme_fade_seconds', 0)
    window = PlayerWindow(settings)
    window.show()
    deadline = time.monotonic() + 8
    while window.scanners and time.monotonic() < deadline:
        QTest.qWait(10)
    assert not window.scanners
    buttons = (window.play, window.previous, window.next)
    sliders = (window.volume, window.seek)
    try:
        for theme in ('chunky', 'classic'):
            settings.setValue('theme', theme)
            for size in (20, 44, 72):
                settings.setValue('button_size', size)
                for dimensions in ((1000, 700), (1400, 900)):
                    window.resize(*dimensions)
                    previous_geometry = None
                    for thickness in (0, 100, 300):
                        settings.setValue('ui_thickness', thickness)
                        window.apply_settings()
                        QTest.qWait(20)
                        centers = []
                        for widget in buttons:
                            rect = button_paint_rect(widget)
                            flat = control_face(rect, widget=widget, depth=0)
                            face = control_face(rect, widget=widget)
                            assert face.size() == flat.size()
                            assert face.top() == flat.top() - thickness * .04
                            assert face.top() >= 0
                            centers.append(widget.mapTo(window, QPoint()).y() + flat.center().y())
                        for widget in sliders:
                            option = QStyleOptionSlider()
                            widget.initStyleOption(option)
                            handle = widget.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, widget)
                            flat = control_face(QRectF(handle), widget=widget, depth=0)
                            centers.append(widget.mapTo(window, QPoint()).y() + flat.center().y())
                        assert max(centers) - min(centers) <= 1, (theme, size, thickness, centers)
                        timestamp = window.seek.mapTo(window, QPoint()).y() + window.seek.timestamp_path().boundingRect().center().y()
                        assert abs(timestamp - centers[0]) <= 1
                        geometry = [widget.geometry() for widget in buttons + sliders]
                        if previous_geometry is not None:
                            assert geometry == previous_geometry
                        previous_geometry = geometry
        settings.setValue('theme', 'chunky')
        settings.setValue('button_size', 44)
        settings.setValue('ui_thickness', 0)
        window.apply_settings()
        QTest.qWait(20)
        window.grab().save('build/bottom-alignment-flat.png')
        settings.setValue('ui_thickness', 300)
        window.apply_settings()
        QTest.qWait(20)
        window.grab().save('build/bottom-alignment-raised.png')
    finally:
        window.close()
        QTest.qWait(50)
print('PASS: common flat baseline, centered timestamp and knobs, upward depth without reflow in both themes and all sizes')
