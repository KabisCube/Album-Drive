"""Shared music and sound-effect output selection with OS-default fallback."""

from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QApplication


def selected_output():
    app = QApplication.instance()
    identity = app.property('audioOutputDevice') if app else ''
    if identity:
        device = next((device for device in QMediaDevices.audioOutputs()
                       if bytes(device.id()).hex() == identity), None)
        if device is not None:
            return device
    return QMediaDevices.defaultAudioOutput()
