import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QAbstractAnimation, QSettings
from PySide6.QtWidgets import QApplication
from library import Album
from main import PlayerWindow


app = QApplication([])


def settle(window):
    for _ in range(4):
        app.processEvents()
        for animation in (window.workspace.mode_animation, window.now_playing.animation):
            if animation.state() != QAbstractAnimation.Stopped:
                animation.setCurrentTime(animation.duration())
    app.processEvents()


with TemporaryDirectory() as directory:
    root = Path(directory)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'missing'))
    settings.setValue('browser_root', str(root / 'missing'))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    try:
        window.show()
        app.processEvents()
        window.update_now_playing_cover(Album(root, 'Album', 'Artist', []))
        settle(window)
        window.workspace.sidebar_width = 385
        window.resize(500, 1200)
        settle(window)
        panel = window.now_playing
        splitter = window.browser_splitter
        splitter.setSizes([1, 100000])
        settle(window)
        natural = panel.content.layout().sizeHint().height()
        assert panel.height() <= natural, (panel.height(), natural)
        assert abs(panel.geometry().bottom() - splitter.contentsRect().bottom()) <= 1, (
            panel.geometry(), splitter.contentsRect(), splitter.sizes())
        cover_height = window.cover.height()
        panel_height = panel.height()
        splitter.moveSplitter(0, 1)
        settle(window)
        assert panel.height() == panel_height
        assert window.cover.height() == cover_height
        for sizes in ((650, 100), (100, 650), (400, 300)):
            window.resize(500, 1000)
            settle(window)
            assert abs(panel.geometry().bottom() - splitter.contentsRect().bottom()) <= 1, (
                sizes, panel.geometry(), splitter.contentsRect(), splitter.sizes())
            window.browser_splitter.setSizes(sizes)
            app.processEvents()
            window.resize(1032, 1165)
            settle(window)
            panel = window.now_playing
            splitter = window.browser_splitter
            assert not panel.resizable
            assert abs(panel.geometry().bottom() - splitter.contentsRect().bottom()) <= 1, (
                sizes, panel.geometry(), splitter.contentsRect(), splitter.sizes())
            assert panel.height() == panel.content.height()
            window.resize(1200, 800)
            settle(window)
            assert abs(panel.geometry().bottom() - splitter.contentsRect().bottom()) <= 1
        for width, height in ((500, 1200), (1200, 800), (480, 1280), (1100, 1000)):
            window.resize(width, height)
            app.processEvents()
            animation = window.workspace.mode_animation
            animation.pause()
            for fraction in (0, .25, .5, .75, 1):
                animation.setCurrentTime(round(animation.duration() * fraction))
                app.processEvents()
                app.processEvents()
                assert abs(panel.geometry().bottom() - splitter.contentsRect().bottom()) <= 1, (
                    width, height, fraction, panel.geometry(), splitter.contentsRect(), panel.resizable,
                    window.cover.height(), panel.content.layout().sizeHint(), panel.content.geometry())
            settle(window)
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()
print('PASS: resizing the compact cover restores a bottom-aligned desktop panel without touching the splitter')
