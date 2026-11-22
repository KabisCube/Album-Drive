"""Shows Album Drive in Linux media controls (Plasma's Media Player widget, GNOME, media keys) via MPRIS.

MPRIS is a D-Bus standard: a player claims the name org.mpris.MediaPlayer2.<name> on the session bus and
publishes two interfaces at /org/mpris/MediaPlayer2. Desktops watch for such names, read the properties
and call the methods. Qt reads each adaptor property's declared type, so 'qlonglong' reaches D-Bus as the
64-bit integer MPRIS asks for. Values inside a dict are converted from Python, so mpris:length goes out as
a 32-bit integer for tracks under 35 minutes, which Plasma and GNOME read the same way.
"""

import os
import sys
import time
import zlib

from PySide6.QtCore import QCoreApplication, QObject, QUrl, Signal

from responsive import running_on_android

MPRIS_PATH = '/org/mpris/MediaPlayer2'
SERVICE_PREFIX = 'org.mpris.MediaPlayer2.'
NO_TRACK = '/org/mpris/MediaPlayer2/TrackList/NoTrack'
STATUS = {'playing': 'Playing', 'paused': 'Paused', 'stopped': 'Stopped'}
# A position this far from where steady playback would be counts as a jump, which listeners hear as Seeked.
JUMP_MS = 1000


def linux_media_supported():
	return sys.platform.startswith('linux') and not running_on_android()


class LinuxMedia(QObject):
	"""Mirrors AndroidMedia: update() publishes what is playing, command carries the desktop's requests."""

	command = Signal(str, int)

	def __init__(self, parent=None, position=lambda: 0, name='albumdrive', desktop_entry='album-drive', identity='Album Drive'):
		super().__init__(parent)
		self.position_source = position
		self.name = name
		self.desktop_entry = desktop_entry
		self.identity = identity
		self.bus = None
		self.service = None
		self.adaptors = ()
		self.state = {}
		self.properties = {}
		self.last_position = None

	def start(self):
		"""Claim an MPRIS name on the session bus; False where there is no bus to join."""
		if self.service is not None:
			return True
		if not linux_media_supported():
			return False
		try:
			from PySide6.QtDBus import QDBusConnection
		except ImportError:
			return False
		bus = QDBusConnection.sessionBus()
		if not bus.isConnected():
			return False
		self.adaptors = make_adaptors(self)
		if not bus.registerObject(MPRIS_PATH, self, QDBusConnection.ExportAdaptors):
			self.adaptors = ()
			return False
		# A second copy of the app takes the instance name the specification sets aside for that.
		for service in (SERVICE_PREFIX + self.name, f'{SERVICE_PREFIX}{self.name}.instance{os.getpid()}'):
			if bus.registerService(service):
				self.bus, self.service = bus, service
				self.properties = self.player_properties()
				app = QCoreApplication.instance()
				if app is not None:
					app.aboutToQuit.connect(self.stop)
				return True
		bus.unregisterObject(MPRIS_PATH)
		self.adaptors = ()
		return False

	def stop(self):
		"""Leave the bus straight away, so a restarted Album Drive gets the plain name back."""
		if self.service is None:
			return
		self.bus.unregisterService(self.service)
		self.bus.unregisterObject(MPRIS_PATH)
		self.bus = self.service = None

	def update(self, **state):
		"""Take the player's state: state, title, artist, album, cover, duration (ms), track, volume (0–100),
		can_next and can_previous. Only properties that changed are announced."""
		was_playing = self.playing()
		self.state = state
		if self.playing() != was_playing:
			self.position_moved(self.current_position())
		if self.service is None:
			return
		properties = self.player_properties()
		changed = {key: value for key, value in properties.items() if self.properties.get(key) != value}
		self.properties = properties
		if changed:
			self.announce('org.mpris.MediaPlayer2.Player', changed)

	def position_moved(self, position):
		"""Watch the playback position (ms) and tell listeners when it jumped rather than ran on."""
		now = time.monotonic()
		if self.last_position is not None and self.service is not None:
			start, since, running = self.last_position
			expected = start + ((now - since) * 1000 if running else 0)
			if abs(position - expected) > JUMP_MS:
				self.adaptors[1].Seeked.emit(int(position) * 1000)
		self.last_position = (position, now, self.playing())

	def playing(self):
		return self.state.get('state') == 'playing'

	def loaded(self):
		return self.state.get('state', 'stopped') != 'stopped'

	def current_position(self):
		return max(0, int(self.position_source() or 0))

	def duration(self):
		return max(0, int(self.state.get('duration') or 0))

	def track_path(self):
		if not self.loaded():
			return NO_TRACK
		key = str(self.state.get('track') or (self.state.get('album'), self.state.get('title')))
		return f'/org/albumdrive/track/t{zlib.crc32(key.encode("utf-8")):08x}'

	def metadata(self):
		from PySide6.QtDBus import QDBusObjectPath
		if not self.loaded():
			return {'mpris:trackid': QDBusObjectPath(NO_TRACK)}
		data = {'mpris:trackid': QDBusObjectPath(self.track_path())}
		if self.duration():
			data['mpris:length'] = self.duration() * 1000
		for key, field in (('title', 'xesam:title'), ('album', 'xesam:album')):
			if self.state.get(key):
				data[field] = self.state[key]
		if self.state.get('artist'):
			data['xesam:artist'] = [self.state['artist']]
		if self.state.get('cover'):
			data['mpris:artUrl'] = QUrl.fromLocalFile(self.state['cover']).toString()
		return data

	def volume(self):
		return max(0, min(100, float(self.state.get('volume', 100)))) / 100

	def player_properties(self):
		"""Every Player property that can change, as plain values that compare cleanly."""
		loaded = self.loaded()
		return {
			'PlaybackStatus': STATUS.get(self.state.get('state'), 'Stopped'),
			'Metadata': self.metadata(),
			'Volume': self.volume(),
			'CanGoNext': loaded and bool(self.state.get('can_next', True)),
			'CanGoPrevious': loaded and bool(self.state.get('can_previous', True)),
			'CanPlay': loaded,
			'CanPause': loaded,
			'CanSeek': loaded and self.duration() > 0,
		}

	def announce(self, interface, changed):
		from PySide6.QtCore import QMetaType
		from PySide6.QtDBus import QDBusArgument, QDBusMessage
		# A plain [] would travel as a list of variants; the signal needs an empty list of strings.
		invalidated = QDBusArgument()
		invalidated.beginArray(QMetaType(QMetaType.Type.QString))
		invalidated.endArray()
		message = QDBusMessage.createSignal(MPRIS_PATH, 'org.freedesktop.DBus.Properties', 'PropertiesChanged')
		message.setArguments([interface, changed, invalidated])
		self.bus.send(message)

	# What the desktop asks for, turned into the commands main.py already understands.
	def play_pause(self):
		self.command.emit('pause' if self.playing() else 'play', 0)

	def seek_by(self, offset):
		target = self.current_position() + offset // 1000
		if self.duration() and target > self.duration():
			self.command.emit('next', 0)
		else:
			self.command.emit('seek', max(0, target))

	def set_position(self, track, position):
		position //= 1000
		if track == self.track_path() and 0 <= position <= self.duration():
			self.command.emit('seek', position)

	def set_volume(self, volume):
		self.command.emit('volume', round(max(0.0, min(1.0, float(volume))) * 100))


def make_adaptors(media):
	"""Build the two MPRIS interfaces. They are defined here, so QtDBus is only loaded where it is used."""
	from PySide6.QtCore import ClassInfo, Property, Slot
	from PySide6.QtDBus import QDBusAbstractAdaptor, QDBusObjectPath

	@ClassInfo({'D-Bus Interface': 'org.mpris.MediaPlayer2'})
	class Root(QDBusAbstractAdaptor):
		CanQuit = Property(bool, lambda self: True, constant=True)
		CanRaise = Property(bool, lambda self: True, constant=True)
		HasTrackList = Property(bool, lambda self: False, constant=True)
		Identity = Property(str, lambda self: media.identity, constant=True)
		DesktopEntry = Property(str, lambda self: media.desktop_entry, constant=True)
		SupportedUriSchemes = Property('QStringList', lambda self: [], constant=True)
		SupportedMimeTypes = Property('QStringList', lambda self: [], constant=True)

		@Slot()
		def Raise(self):
			media.command.emit('raise', 0)

		@Slot()
		def Quit(self):
			media.command.emit('quit', 0)

	@ClassInfo({'D-Bus Interface': 'org.mpris.MediaPlayer2.Player'})
	class Player(QDBusAbstractAdaptor):
		Seeked = Signal('qlonglong')
		PlaybackStatus = Property(str, lambda self: media.properties.get('PlaybackStatus', 'Stopped'))
		Metadata = Property('QVariantMap', lambda self: media.metadata())
		Volume = Property(float, lambda self: media.volume(), lambda self, volume: media.set_volume(volume))
		Position = Property('qlonglong', lambda self: media.current_position() * 1000)
		Rate = Property(float, lambda self: 1.0)
		MinimumRate = Property(float, lambda self: 1.0, constant=True)
		MaximumRate = Property(float, lambda self: 1.0, constant=True)
		CanGoNext = Property(bool, lambda self: media.properties.get('CanGoNext', False))
		CanGoPrevious = Property(bool, lambda self: media.properties.get('CanGoPrevious', False))
		CanPlay = Property(bool, lambda self: media.properties.get('CanPlay', False))
		CanPause = Property(bool, lambda self: media.properties.get('CanPause', False))
		CanSeek = Property(bool, lambda self: media.properties.get('CanSeek', False))
		CanControl = Property(bool, lambda self: True, constant=True)

		@Slot()
		def Play(self):
			media.command.emit('play', 0)

		@Slot()
		def Pause(self):
			media.command.emit('pause', 0)

		@Slot()
		def PlayPause(self):
			media.play_pause()

		@Slot()
		def Stop(self):
			media.command.emit('pause', 0)

		@Slot()
		def Next(self):
			media.command.emit('next', 0)

		@Slot()
		def Previous(self):
			media.command.emit('previous', 0)

		@Slot('qlonglong')
		def Seek(self, offset):
			media.seek_by(offset)

		@Slot(QDBusObjectPath, 'qlonglong')
		def SetPosition(self, track, position):
			media.set_position(track.path(), position)

		@Slot(str)
		def OpenUri(self, uri):
			pass

	return Root(media), Player(media)
