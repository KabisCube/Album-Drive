import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout, QFormLayout
from first_run import FirstRunDialog
from main import STYLE


app = QApplication([])
font_id = QFontDatabase.addApplicationFont('assets/fonts/AlbumRound-Bold.ttf')
app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 10))
app.setStyleSheet(STYLE)
Path('build').mkdir(exist_ok=True)

with TemporaryDirectory() as directory:
    settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
    guide = FirstRunDialog(settings)
    guide.show()
    for width, height in ((900, 680), (393, 780), (320, 600), (600, 320), (900, 680)):
        guide.resize(width, height)
        for step in range(3):
            guide.set_step(step)
            QTest.qWait(30)
            assert guide.width() == width, (width, step, guide.size())
            assert guide.height() == height, (height, step, guide.size())
            assert guide.rect().contains(guide.next_button.geometry())
            assert guide.next_button.geometry().top() > guide.scroll.geometry().bottom()
            assert guide.scroll.widget().width() <= guide.scroll.viewport().width()
            assert guide.categories.direction() == (QBoxLayout.TopToBottom if width < 640 else QBoxLayout.LeftToRight)
            assert guide.button_form.rowWrapPolicy() == (QFormLayout.WrapAllRows if width < 640 else QFormLayout.DontWrapRows)
            if step == 1 and width < 640:
                assert guide.fixed_category.y() > guide.dynamic_category.geometry().bottom()
                guide.scroll.ensureWidgetVisible(guide.choices['fixed_light'])
                QTest.qWait(20)
                assert guide.choices['fixed_light'].visibleRegion().boundingRect().height() > 0
            guide.grab().save(f'build/setup-{width}-{height}-{step}.png')
    guide.reject()

print('PASS: all setup steps fit phone portrait, short landscape and desktop sizes')
