import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QScroller, QScrollerProperties, QWidget

import touch_input
from touch_input import TouchGestures

app = QApplication.instance() or QApplication([])


class Point:
    def __init__(self, x, y):
        self.local = QPointF(x, y)

    def position(self):
        return self.local

    def globalPosition(self):
        return self.local


class Touch:
    def __init__(self, x, y, timestamp):
        self.items = [Point(x, y)]
        self.time = timestamp

    def points(self):
        return self.items

    def timestamp(self):
        return self.time


class TouchReleaseTests(unittest.TestCase):
    def setUp(self):
        self.widget = QWidget()
        self.widget.resize(300, 600)
        self.gestures = TouchGestures(self.widget, scrolls=True)
        self.inputs = []
        self.gestures.scroller = MagicMock()
        self.gestures.scroller.state.return_value = QScroller.Inactive
        self.gestures.scroller.handleInput.side_effect = (
            lambda phase, position, timestamp: self.inputs.append((phase, position.y())))

    def test_lift_that_jitters_back_releases_at_the_last_move(self):
        self.gestures.begin(Touch(100, 500, 0))
        for step, y in enumerate(range(480, 199, -20), start=1):
            self.gestures.update_touch(Touch(100, y, step * 11))
        self.gestures.finish(Touch(100, 201, 170))
        phase, y = self.inputs[-1]
        self.assertEqual(phase, QScroller.InputRelease)
        self.assertEqual(y, 200)

    def test_tap_releases_where_the_finger_lifted(self):
        self.gestures.tap = MagicMock()
        self.gestures.begin(Touch(100, 300, 0))
        self.gestures.finish(Touch(100, 303, 50))
        self.assertEqual(self.inputs[-1], (QScroller.InputRelease, 303))
        self.gestures.tap.assert_called_once()

    def test_scroller_starts_dragging_almost_immediately(self):
        widget = QWidget()
        gestures = TouchGestures(widget, scrolls=True)
        start = gestures.scroller.scrollerProperties().scrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance)
        self.assertAlmostEqual(start, touch_input.SCROLL_START_METRES)


if __name__ == '__main__':
    unittest.main()
