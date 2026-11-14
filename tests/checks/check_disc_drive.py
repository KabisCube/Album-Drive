"""Drive styling, insertion animation and releasing playback before eject."""
import hashlib
import os
from pathlib import Path
import tempfile
import time
from dataclasses import replace
from threading import Event
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow, cd_case_pixmap
from optical_discs import Disc, DiscReader
from test_library import make_wave


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    make_wave(root / 'Library/Album/1.wav')
    make_wave(root / 'Disc/Album/1.wav')
    artwork = root / 'Disc/Album/cover.png'
    Image.new('RGB', (100, 100), '#456b85').save(artwork)
    checksum = hashlib.sha256(artwork.read_bytes()).hexdigest()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Library'))
    settings.setValue('browser_root', str(root / 'Library'))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    window.show()
    try:
        wait_until(lambda: window.albums and not window.scanners)
        disc = Disc(str(root / 'Disc'), 'Example music CD', 'test-disc')
        window.update_optical_discs([disc])
        window.disc_panel.animation.pause()
        assert window.disc_panel.height() == 0
        window.disc_panel.animation.setCurrentTime(140)
        assert 0 < window.disc_panel.height() < window.disc_panel.content_height
        assert window.disc_list.y() < 0
        window.disc_panel.animation.setCurrentTime(280)
        app.processEvents()
        assert window.disc_list.y() == 0
        # The drive rows and the folder browser sit on raised faces that line up.
        rows, browser = window.disc_list, window.tree
        assert rows.mapTo(window, rows.rect().topLeft()).x() == browser.mapTo(window, browser.rect().topLeft()).x()
        assert rows.width() == browser.width()
        assert window.disc_list.item(0).text().startswith('Disc Drive')
        window.disc_list.setCurrentRow(0)
        wait_until(lambda: not window.scanners and window.albums[0].folder == root / 'Disc/Album')
        button = window.disc_list.buttons[str(root / 'Disc')]
        assert button.isVisible()
        assert button.geometry().right() >= window.disc_list.viewport().width() - 4
        Path('build').mkdir(exist_ok=True)
        window.disc_panel.grab().save('build/disc-drive-row.png')
        art = artwork.read_bytes()
        case = cd_case_pixmap(art, 'Example')
        case.save('build/plastic-case-preview.png')
        assert hashlib.sha256(artwork.read_bytes()).hexdigest() == checksum
        album = window.albums[0]
        window.queue = [(track, album) for track in album.tracks]
        window.play_index(0, autoplay=False)
        wait_until(lambda: window.player.duration() > 0)
        released = Event()
        class HoldingReader(DiscReader):
            def run(self):
                while not self.isInterruptionRequested():
                    time.sleep(.005)
                time.sleep(.06)
                released.set()
        reader = HoldingReader(replace(album.tracks[0], cd_source=str(root / 'Disc')), window)
        window.scanners.add(reader)
        reader.finished.connect(lambda: window.scanner_finished(reader))
        reader.start()
        def ejected(drive):
            assert drive == str(root / 'Disc')
            assert window.player.source().isEmpty()
            assert released.is_set(), 'Ejected before the disc reader released the drive'
        with patch('optical_discs.eject_disc', side_effect=ejected) as eject, \
                patch.object(window.player, 'pause', wraps=window.player.pause) as paused:
            QTest.mouseClick(button, Qt.LeftButton)
            paused.assert_called_once()
            wait_until(lambda: window.pending_eject is None and not window.scanners)
            eject.assert_called_once_with(str(root / 'Disc'))
        assert not window.optical_discs
        assert not window.queue
        wait_until(lambda: not window.disc_panel.isVisible())
        assert window.albums[0].folder == root / 'Library/Album'

        # A failed eject retains the row and reports the OS error.
        window.update_optical_discs([disc])
        window.disc_list.setCurrentRow(0)
        wait_until(lambda: not window.scanners and window.albums[0].folder == root / 'Disc/Album')
        album = window.albums[0]
        window.queue = [(track, album) for track in album.tracks]
        window.play_index(0, autoplay=False)
        wait_until(lambda: window.player.duration() > 0)
        with patch('optical_discs.eject_disc', side_effect=OSError('Drive busy')):
            window.eject_optical_disc(str(root / 'Disc'))
            wait_until(lambda: window.pending_eject is None and not window.scanners)
        assert window.optical_discs
        assert 'Drive busy' in window.statusBar().currentMessage()
        assert window.disc_list.buttons[str(root / 'Disc')].isEnabled()
        assert not window.player.source().isEmpty()
        # Keep the outgoing row intact until the panel has fully slid away.
        window.disc_panel.animation.setCurrentTime(280)
        window.update_optical_discs([])
        window.disc_panel.animation.pause()
        full_height = window.disc_panel.animation.startValue()
        assert full_height >= window.disc_panel.content_height
        assert window.disc_list.count() == 1
        assert not window.disc_list.isEnabled()
        assert window.disc_panel.height() == full_height
        window.disc_panel.animation.setCurrentTime(140)
        assert 0 < window.disc_panel.height() < full_height
        assert window.disc_list.y() < 0
        assert window.disc_list.item(0).text().startswith('Disc Drive')
        # Reinsertion reverses the slide from its current position.
        halfway = window.disc_panel.height()
        window.update_optical_discs([disc])
        assert window.disc_panel.height() == halfway
        assert window.disc_list.isEnabled()
        window.disc_panel.animation.setCurrentTime(280)
        window.update_optical_discs([])
        window.disc_panel.animation.pause()
        assert window.disc_list.count() == 1
        window.disc_panel.animation.setCurrentTime(280)
        assert not window.disc_panel.isVisible()
        assert window.disc_list.count() == 0
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()
print('PASS: drive alignment, slide-in, eject button and playback release, failure handling, unchanged artwork')
