import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import android_media
from android_media import AndroidMedia


class AndroidMediaTests(unittest.TestCase):
    def media(self):
        media = AndroidMedia()
        media.connection = MagicMock()
        return media

    def test_does_nothing_off_android(self):
        with patch('android_media.running_on_android', return_value=False), \
                patch('android_media.socket.socket') as make:
            AndroidMedia().update(state='playing')
        make.assert_not_called()

    def test_sends_each_change_once_as_one_line(self):
        media = self.media()
        with patch('android_media.running_on_android', return_value=True):
            media.update(state='playing', title='Song')
            media.update(state='playing', title='Song')
            media.update(state='paused', title='Song')
        sent = [call.args[0] for call in media.connection.send.call_args_list]
        self.assertEqual(len(sent), 2)
        self.assertTrue(all(line.endswith(b'\n') and line.count(b'\n') == 1 for line in sent))
        self.assertEqual(json.loads(sent[0])['title'], 'Song')

    def test_lost_connection_retries_the_same_state(self):
        media = self.media()
        media.connection.send.side_effect = OSError
        with patch('android_media.running_on_android', return_value=True), \
                patch.object(AndroidMedia, 'connect') as reconnect:
            media.update(state='playing')
            self.assertIsNone(media.connection)
            def connected():
                media.connection = MagicMock()
            reconnect.side_effect = connected
            media.update(state='playing')
        media.connection.send.assert_called_once()

    def test_commands_arrive_whole_across_reads(self):
        media = self.media()
        heard = []
        media.command.connect(lambda name, value: heard.append((name, value)))
        media.connection.recv.side_effect = [b'pause\nse', b'ek 1500\nnext\n']
        media.read()
        media.read()
        self.assertEqual(heard, [('pause', 0), ('seek', 1500), ('next', 0)])

    def test_closed_socket_disconnects(self):
        media = self.media()
        media.connection.recv.return_value = b''
        media.read()
        self.assertIsNone(media.connection)

    def test_cover_file_replaces_the_previous_album(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch('android_media.QStandardPaths.writableLocation', return_value=folder):
            media = AndroidMedia()
            first = Path(media.cover_file(b'first'))
            self.assertEqual(first.read_bytes(), b'first')
            self.assertEqual(Path(media.cover_file(b'first')), first)
            second = Path(media.cover_file(b'second'))
            self.assertFalse(first.exists())
            self.assertTrue(second.is_file())
            self.assertEqual(media.cover_file(b''), '')


if __name__ == '__main__':
    unittest.main()
