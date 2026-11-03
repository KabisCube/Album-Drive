import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from status_bar import FadingStatusBar


class StatusBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bar = FadingStatusBar()

    def tearDown(self):
        self.bar.close()
        self.bar.deleteLater()

    def test_message_fades_then_clears(self):
        self.bar.showMessage('Folder inaccessible')
        self.assertEqual(self.bar.message_timer.interval(), 15000)
        self.assertTrue(self.bar.message_timer.isActive())
        self.bar.message_timer.timeout.emit()
        self.bar.fade.setCurrentTime(250)
        self.assertAlmostEqual(self.bar.opacity.opacity(), .5)
        self.bar.fade.setCurrentTime(500)
        self.assertEqual(self.bar.currentMessage(), '')
        self.assertTrue(self.bar.isHidden())

    def test_new_message_cancels_old_fade(self):
        self.bar.showMessage('First error')
        self.bar.message_timer.timeout.emit()
        self.bar.fade.setCurrentTime(250)
        self.bar.showMessage('Next error')
        self.assertEqual(self.bar.currentMessage(), 'Next error')
        self.assertEqual(self.bar.opacity.opacity(), 1)
        self.assertTrue(self.bar.message_timer.isActive())

    def test_progress_stays_until_cleared(self):
        self.bar.showMessage('Reading CD', 0)
        self.assertFalse(self.bar.message_timer.isActive())
        self.bar.clearMessage()
        self.assertEqual(self.bar.currentMessage(), '')
        self.assertTrue(self.bar.isHidden())
