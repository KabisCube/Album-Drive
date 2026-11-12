import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QRectF, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider

from main import PlayerWindow
from themes import button_paint_rect, control_face


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', directory)
    settings.setValue('theme_fade_seconds', 0)
    window = PlayerWindow(settings)
    window.show()
    buttons = (window.sort_albums, window.save_theme_button, window.settings_button)
    try:
        for theme in ('chunky', 'classic'):
            settings.setValue('theme', theme)
            for size in (20, 44, 72):
                settings.setValue('button_size', size)
                for dimensions in ((1000, 700), (1400, 900)):
                    window.resize(*dimensions)
                    previous = None
                    for thickness in (0, 100, 300):
                        settings.setValue('ui_thickness', thickness)
                        window.apply_settings()
                        QTest.qWait(20)
                        centers = [button.mapTo(window, QPoint()).y()
                                   + control_face(button_paint_rect(button), widget=button, depth=0).center().y()
                                   for button in buttons]
                        slider = window.album_size
                        option = QStyleOptionSlider()
                        slider.initStyleOption(option)
                        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
                        flat = control_face(QRectF(handle), widget=slider, depth=0)
                        raised = control_face(QRectF(handle), widget=slider)
                        centers.append(slider.mapTo(window, QPoint()).y() + flat.center().y())
                        centers.append(slider.mapTo(window, QPoint()).y() + slider.height() / 2)
                        assert max(centers) - min(centers) <= 1, (theme, size, thickness, centers)
                        assert abs(flat.top() - raised.top() - thickness * .04) <= .001
                        geometry = [widget.mapTo(window, QPoint()).y() for widget in buttons + (slider,)]
                        if previous is not None:
                            assert geometry == previous
                        previous = geometry
    finally:
        window.close()
        while window.scanners:
            QTest.qWait(10)
print('PASS: album slider rail and flat knob align with header buttons at every size and remain stationary as thickness changes')
