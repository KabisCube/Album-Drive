import os
import unittest
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QWidget
from first_run import ThemeSavePreview, theme_save_image
from main import load_app_font
from themes import ThemedButton, ThemeSaveIcon


class SetupButtonPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_app_font()

    def test_android_preview_looks_enabled_without_enabling_the_source(self):
        window = QWidget()
        button = ThemedButton(window)
        window.save_theme_button = button
        button.setIcon(QIcon(ThemeSaveIcon()))
        button.resize(96, 64)
        expected = button.grab().toImage()
        button.setEnabled(False)
        with patch.object(QApplication, 'platformName', return_value='android'):
            image = theme_save_image(window)
            self.assertEqual(image.toImage(), expected)
            self.assertFalse(button.isEnabled())
            preview = ThemeSavePreview()
            preview.setAttribute(Qt.WA_TranslucentBackground)
            preview.resize(400, 200)
            preview.image = image.scaled(image.size() * 2)
            preview.image.setDevicePixelRatio(2)
            preview.show()
            self.app.processEvents()
            rendered = preview.grab().toImage()
            points = [(x, y) for y in range(rendered.height()) for x in range(rendered.width())
                      if rendered.pixelColor(x, y).alpha()]
            self.assertTrue(points)
            self.assertLessEqual(max(x for x, _ in points) - min(x for x, _ in points) + 1, button.width())
            self.assertLessEqual(max(y for _, y in points) - min(y for _, y in points) + 1, button.height())
            clicks = QSignalSpy(button.clicked)
            QTest.mouseClick(preview, Qt.LeftButton, pos=preview.rect().center())
            self.assertEqual(clicks.count(), 0)
            preview.close()
        window.close()
