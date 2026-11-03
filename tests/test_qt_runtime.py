import sys
import unittest

from PySide6.QtGui import QColor


class QtRuntimeTests(unittest.TestCase):
    def test_void_calls_preserve_none_references(self):
        color = QColor('red')
        for _ in range(16):
            color.setRed(128)
        before = sys.getrefcount(None)
        for _ in range(128):
            color.setRed(128)
        after = sys.getrefcount(None)
        self.assertGreaterEqual(after, before - 4, 'Qt calls are consuming references to None; use a compatible PySide6 release')
