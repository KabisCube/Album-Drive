import unittest
from unittest.mock import MagicMock, patch

import haptics


class HapticTests(unittest.TestCase):
    def setUp(self):
        haptics._connection = None

    def test_only_runs_on_android(self):
        with patch('haptics.running_on_android', return_value=False), patch('haptics.socket.socket') as make:
            haptics.press_haptic()
        make.assert_not_called()

    def test_reuses_one_connection(self):
        connection = MagicMock()
        with patch('haptics.running_on_android', return_value=True), \
                patch('haptics.socket.AF_UNIX', 1, create=True), \
                patch('haptics.socket.socket', return_value=connection) as make:
            haptics.press_haptic()
            haptics.press_haptic()
        make.assert_called_once()
        connection.connect.assert_called_once_with(haptics.HAPTIC_SOCKET)
        self.assertEqual(connection.send.call_count, 2)

    def test_lost_connection_reconnects_without_raising(self):
        connection = MagicMock()
        connection.send.side_effect = [OSError, None]
        with patch('haptics.running_on_android', return_value=True), \
                patch('haptics.socket.AF_UNIX', 1, create=True), \
                patch('haptics.socket.socket', return_value=connection) as make:
            haptics.press_haptic()
            haptics.press_haptic()
        self.assertEqual(make.call_count, 2)

    def test_full_buffer_keeps_the_connection(self):
        connection = MagicMock()
        connection.send.side_effect = BlockingIOError
        with patch('haptics.running_on_android', return_value=True), \
                patch('haptics.socket.AF_UNIX', 1, create=True), \
                patch('haptics.socket.socket', return_value=connection):
            haptics.press_haptic()
        connection.close.assert_not_called()
