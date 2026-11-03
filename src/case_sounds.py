"""Independent CD-case opening/closing effects on the selected audio output."""

from app_paths import ASSETS_DIR

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtMultimedia import QMediaDevices, QSoundEffect
from PySide6.QtWidgets import QApplication
from audio_devices import selected_output
from audio_levels import volume_gain


class CaseSounds(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.shutting_down = False
        self.voices = {}
        for action in ('open', 'close'):
            voice = QSoundEffect(self)
            voice.setSource(QUrl.fromLocalFile(str(ASSETS_DIR / 'sounds' / f'case-{action}.wav')))
            self.voices[action] = voice
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self.prepare, Qt.QueuedConnection)
        self.prepare()
        app.aboutToQuit.connect(self.shutdown)

    def prepare(self):
        if self.shutting_down:
            return
        app = QApplication.instance()
        for action, voice in self.voices.items():
            device = selected_output()
            if voice.audioDevice() != device:
                voice.setAudioDevice(device)
            value = app.property(f'case{action.title()}Volume')
            voice.setVolume(.4 * volume_gain(70 if value is None else value))

    def play(self, action):
        if self.shutting_down:
            return
        self.prepare()
        voice = self.voices[action]
        if voice.volume() > 0 and voice.status() == QSoundEffect.Ready:
            voice.stop()
            voice.play()

    def shutdown(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        for voice in self.voices.values():
            voice.stop()
            voice.setSource(QUrl())


def prepare_case_sounds():
    app = QApplication.instance()
    if app is None or app.platformName() in ('offscreen', 'minimal'):
        return None
    if not hasattr(app, '_case_sounds'):
        app._case_sounds = CaseSounds(app)
    app._case_sounds.prepare()
    return app._case_sounds


def play_case_sound(action):
    bank = prepare_case_sounds()
    if bank is not None:
        bank.play(action)
