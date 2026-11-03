"""Low-latency button clicks that follow the visible button depth."""


from app_paths import ASSETS_DIR

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices, QSoundEffect
from PySide6.QtWidgets import QApplication
from audio_levels import volume_gain
from audio_devices import selected_output


def sound_depth():
    app = QApplication.instance()
    amount = app.property('uiThickness') if app else None
    depth = (100 if amount is None else amount) / 25
    return 0 if depth <= 0 else max(1, min(12, round(depth)))


def sound_gain():
    app = QApplication.instance()
    amount = app.property('buttonSoundVolume') if app else None
    return .22 * volume_gain(100 if amount is None else amount)


class ButtonSounds(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.depth = None
        self.shutting_down = False
        self.next_voice = 0
        self.voices = [QSoundEffect(self) for _ in range(4)]
        for voice in self.voices:
            voice.setVolume(sound_gain())
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self.update_output, Qt.QueuedConnection)
        self.update_output()
        app.aboutToQuit.connect(self.shutdown)

    def update_output(self):
        if self.shutting_down:
            return
        device = selected_output()
        for voice in self.voices:
            if voice.audioDevice() != device:
                voice.setAudioDevice(device)

    def prepare(self, depth):
        if self.shutting_down:
            return
        for voice in self.voices:
            voice.setVolume(sound_gain())
        if self.depth == depth:
            return
        self.depth = depth
        for voice in self.voices:
            voice.stop()
            if depth:
                path = ASSETS_DIR / 'sounds' / f'button-{depth:02}.wav'
                voice.setSource(QUrl.fromLocalFile(str(path)))

    def play(self):
        if self.shutting_down:
            return
        self.prepare(sound_depth() if sound_gain() > 0 else 0)
        if not self.depth:
            return
        voice = self.voices[self.next_voice]
        self.next_voice = (self.next_voice + 1) % len(self.voices)
        if voice.status() == QSoundEffect.Ready:
            voice.play()

    def shutdown(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        for voice in self.voices:
            voice.stop()
            voice.setSource(QUrl())


def sound_bank():
    app = QApplication.instance()
    # Headless verification must not produce sound on the user's speakers.
    if app is None or QGuiApplication.platformName() in ('offscreen', 'minimal'):
        return None
    if not hasattr(app, '_button_sounds'):
        app._button_sounds = ButtonSounds(app)
    return app._button_sounds


def prepare_button_sounds():
    app = QApplication.instance()
    if sound_depth() == 0 or sound_gain() == 0:
        bank = getattr(app, '_button_sounds', None)
        if bank is not None:
            bank.prepare(0)
        return
    bank = sound_bank()
    if bank is not None:
        bank.update_output()
        bank.prepare(sound_depth())


def play_button_sound():
    if sound_depth() == 0 or sound_gain() == 0:
        return
    bank = sound_bank()
    if bank is not None:
        bank.play()
