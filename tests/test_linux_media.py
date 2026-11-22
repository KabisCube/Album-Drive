"""MPRIS: what Linux media controls read from Album Drive, and what their buttons ask it to do."""

import json
import os
import shutil
import subprocess
import time
import unittest

from PySide6.QtWidgets import QApplication

import linux_media
from linux_media import NO_TRACK, LinuxMedia

try:
	from PySide6.QtDBus import QDBusConnection
except ImportError:
	QDBusConnection = None

app = QApplication.instance() or QApplication([])
PLAYING = dict(state='playing', title='Song', artist='Band', album='Record', duration=200_000,
			track='/music/1.flac#0', volume=60, cover='/tmp/cover', can_next=True)


@unittest.skipIf(QDBusConnection is None, 'Qt was built without D-Bus')
class LinuxMediaStateTests(unittest.TestCase):
	def media(self, position=0):
		media = LinuxMedia(position=lambda: position)
		self.commands = []
		media.command.connect(lambda name, value: self.commands.append((name, value)))
		return media

	def test_metadata_describes_the_track_and_follows_it(self):
		media = self.media()
		media.update(**PLAYING)
		data = media.metadata()
		self.assertEqual(data['xesam:title'], 'Song')
		self.assertEqual(data['xesam:artist'], ['Band'])
		self.assertEqual(data['xesam:album'], 'Record')
		self.assertEqual(data['mpris:length'], 200_000_000, 'MPRIS counts microseconds')
		self.assertEqual(data['mpris:artUrl'], 'file:///tmp/cover')
		first = data['mpris:trackid'].path()
		media.update(**{**PLAYING, 'track': '/music/2.flac#0'})
		self.assertNotEqual(media.metadata()['mpris:trackid'].path(), first)
		media.update(state='stopped')
		self.assertEqual(media.metadata()['mpris:trackid'].path(), NO_TRACK)

	def test_properties_follow_the_player(self):
		media = self.media()
		self.assertEqual(media.player_properties()['PlaybackStatus'], 'Stopped')
		self.assertFalse(media.player_properties()['CanPlay'])
		media.update(**PLAYING)
		properties = media.player_properties()
		self.assertEqual(properties['PlaybackStatus'], 'Playing')
		self.assertEqual(properties['Volume'], .6)
		self.assertTrue(properties['CanPlay'] and properties['CanSeek'] and properties['CanGoNext'])
		media.update(**{**PLAYING, 'state': 'paused', 'can_next': False})
		self.assertEqual(media.player_properties()['PlaybackStatus'], 'Paused')
		self.assertFalse(media.player_properties()['CanGoNext'])

	def test_desktop_requests_become_player_commands(self):
		media = self.media(position=12_000)
		media.update(**PLAYING)
		media.play_pause()
		media.seek_by(5_000_000)
		media.seek_by(-60_000_000)
		media.seek_by(500_000_000)
		media.set_position(media.track_path(), 30_000_000)
		media.set_position('/org/albumdrive/track/other', 30_000_000)
		media.set_volume(.25)
		media.update(**{**PLAYING, 'state': 'paused'})
		media.play_pause()
		self.assertEqual(self.commands, [('pause', 0), ('seek', 17_000), ('seek', 0), ('next', 0),
										('seek', 30_000), ('volume', 25), ('play', 0)])

	def test_stays_off_the_bus_where_mpris_does_not_apply(self):
		media = LinuxMedia()
		original = linux_media.linux_media_supported
		linux_media.linux_media_supported = lambda: False
		try:
			self.assertFalse(media.start())
		finally:
			linux_media.linux_media_supported = original
		media.update(**PLAYING)
		self.assertIsNone(media.service)


def session_bus():
	if QDBusConnection is None or not linux_media.linux_media_supported() or not shutil.which('busctl'):
		return False
	return QDBusConnection.sessionBus().isConnected()


@unittest.skipUnless(session_bus(), 'needs a D-Bus session bus and busctl')
class LinuxMediaBusTests(unittest.TestCase):
	"""Talks to the running session bus the way Plasma does, through a separate busctl process."""

	def setUp(self):
		self.position = 12_000
		self.media = LinuxMedia(position=lambda: self.position, name=f'albumdrivetest{os.getpid()}')
		self.commands = []
		self.media.command.connect(lambda name, value: self.commands.append((name, value)))
		self.assertTrue(self.media.start())
		self.addCleanup(self.media.stop)
		self.media.update(**PLAYING)

	def busctl(self, *arguments, background=False):
		command = ['busctl', '--user', *arguments]
		process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
		if background:
			return process
		return self.finish(process)

	def finish(self, process, seconds=5):
		# busctl waits for this process to answer, so keep Qt's event loop turning meanwhile.
		deadline = time.monotonic() + seconds
		while process.poll() is None and time.monotonic() < deadline:
			app.processEvents()
			time.sleep(.005)
		if process.poll() is None:
			process.kill()
		output, error = process.communicate()
		self.assertEqual(process.returncode, 0, error)
		return output

	def get(self, interface, name):
		output = self.busctl('--json=short', 'get-property', self.media.service, linux_media.MPRIS_PATH, interface, name)
		return json.loads(output)

	def call(self, interface, method, *arguments):
		self.busctl('call', self.media.service, linux_media.MPRIS_PATH, interface, method, *arguments)

	def test_publishes_spec_types(self):
		player = 'org.mpris.MediaPlayer2.Player'
		self.assertEqual(self.get('org.mpris.MediaPlayer2', 'Identity'), {'type': 's', 'data': 'Album Drive'})
		self.assertEqual(self.get('org.mpris.MediaPlayer2', 'DesktopEntry')['data'], 'album-drive')
		self.assertEqual(self.get(player, 'PlaybackStatus')['data'], 'Playing')
		self.assertEqual(self.get(player, 'Position'), {'type': 'x', 'data': 12_000_000})
		metadata = self.get(player, 'Metadata')
		self.assertEqual(metadata['type'], 'a{sv}')
		self.assertEqual(metadata['data']['mpris:trackid']['type'], 'o')
		self.assertEqual(metadata['data']['xesam:artist'], {'type': 'as', 'data': ['Band']})
		self.assertEqual(self.get(player, 'Volume')['data'], .6)

	def test_methods_reach_the_player(self):
		player = 'org.mpris.MediaPlayer2.Player'
		self.call(player, 'PlayPause')
		self.call(player, 'Next')
		self.call(player, 'Seek', 'x', '5000000')
		self.busctl('set-property', self.media.service, linux_media.MPRIS_PATH, player, 'Volume', 'd', '0.25')
		self.call('org.mpris.MediaPlayer2', 'Raise')
		self.assertEqual(self.commands, [('pause', 0), ('next', 0), ('seek', 17_000), ('volume', 25), ('raise', 0)])

	def test_changes_and_jumps_are_announced(self):
		watch = self.busctl('--json=short', 'monitor', '--match',
							f"type='signal',sender='{self.media.service}',path='{linux_media.MPRIS_PATH}'",
							background=True)
		self.addCleanup(watch.kill)
		time.sleep(.5)
		self.media.update(**{**PLAYING, 'state': 'paused'})
		self.media.position_moved(12_000)
		self.position = 90_000
		self.media.position_moved(90_000)
		deadline = time.monotonic() + 1
		while time.monotonic() < deadline:
			app.processEvents()
			time.sleep(.01)
		watch.terminate()
		output, _ = watch.communicate(timeout=5)
		signals = [json.loads(line) for line in output.splitlines() if line.startswith('{')]
		changed = next(signal for signal in signals if signal.get('member') == 'PropertiesChanged')
		self.assertEqual(changed['payload']['type'], 'sa{sv}as')
		self.assertEqual(changed['payload']['data'][1], {'PlaybackStatus': {'type': 's', 'data': 'Paused'}})
		seeked = [signal['payload'] for signal in signals if signal.get('member') == 'Seeked']
		self.assertEqual(seeked, [{'type': 'x', 'data': [90_000_000]}])


if __name__ == '__main__':
	unittest.main()
