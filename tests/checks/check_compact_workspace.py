import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QAbstractAnimation, QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from test_library import make_wave


app = QApplication([])


def settle(window):
    for _ in range(3):
        app.processEvents()
        for animation in (window.workspace.mode_animation, window.workspace.page_animation,
                          window.now_playing.animation, window.album_presentation.animation,
                          window.album_presentation.layout_animation):
            if animation.state() != QAbstractAnimation.Stopped:
                animation.setCurrentTime(animation.duration())
    app.processEvents()


with TemporaryDirectory() as directory:
    root = Path(directory)
    for name, color in (('First album', '#335b70'), ('Second album', '#704536')):
        folder = root / 'Music' / name
        make_wave(folder / '1.wav')
        image = Image.new('RGB', (400, 400), color)
        image.paste('#ead7ae', (30, 160, 370, 240))
        image.save(folder / 'cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    try:
        window.show()
        deadline = time.monotonic() + 10
        while (len(window.albums) != 2 or window.scanners) and time.monotonic() < deadline:
            QTest.qWait(20)
            time.sleep(.005)
        assert len(window.albums) == 2
        album = window.albums[0]
        album.tracks *= 13
        window.queue = [(track, album) for track in album.tracks]
        window.queue_index = 0
        window.track_title.setText('A test track')
        window.update_now_playing_cover(album)
        settle(window)
        frame = window.frameGeometry()
        extra_width = frame.width() - window.width()
        extra_height = frame.height() - window.height()
        window.resize(641 - extra_width, 960 - extra_height)
        settle(window)
        assert not window.compact_mode
        window.resize(640 - extra_width, 960 - extra_height)
        app.processEvents()
        animation = window.workspace.mode_animation
        assert window.compact_mode
        animation.pause()
        animation.setCurrentTime(0)
        start = window.workspace.panes[0].geometry()
        animation.setCurrentTime(animation.duration() // 2)
        assert 0 < window.workspace.mode_mix < 1
        assert window.workspace.panes[0].geometry() != start
        mixture = window.workspace.mode_mix
        window.resize(641 - extra_width, 960 - extra_height)
        app.processEvents()
        animation.pause()
        animation.setCurrentTime(0)
        assert window.workspace.mode_mix == mixture
        window.resize(640 - extra_width, 960 - extra_height)
        app.processEvents()
        settle(window)
        assert window.workspace.page == 'browser'
        assert window.workspace.panes[1].isHidden()
        assert window.workspace.panes[0].width() == window.workspace.width()
        assert not window.back_button.isVisible()
        assert window.transport.isVisible()
        if window.volume.isVisible():
            assert window.volume.geometry().left() > window.next.geometry().right()
            assert window.volume.geometry().right() < window.transport.width()
            assert abs(window.volume.geometry().center().y() - window.play.geometry().center().y()) <= 2
        assert window.seek.y() < window.play.y()
        assert window.previous.x() < window.play.x() < window.next.x()
        assert window.browser_splitter.handleWidth() == 8
        assert window.now_playing.resizable
        assert window.now_playing.height() > 0
        window.grab().save('build/previews/compact-browser.png')
        before = window.tree.height()
        window.browser_splitter.moveSplitter(window.browser_splitter.height(), 1)
        app.processEvents()
        assert window.tree.height() > before
        window.grab().save('build/previews/compact-browser-expanded.png')
        window.browser_splitter.setSizes([300, 500])
        index = window.files.index(str(root / 'Music'))
        assert index.isValid()
        window.tree.clicked.emit(index)
        settle(window)
        assert window.workspace.page == 'library'
        assert window.workspace.panes[0].isHidden()
        assert window.back_button.isVisible() and window.transport.isVisible()
        back, previous = window.back_button.geometry(), window.previous.geometry()
        assert back.right() < previous.left() and back.left() >= 0
        assert abs(back.center().y() - previous.center().y()) <= 1
        window.grid.finish_reflow()
        window.grab().save('build/previews/compact-albums.png')
        window.show_album(album, play_sound=False)
        settle(window)
        assert window.album_table.rowCount() == 13
        assert window.album_presentation.booklet.y() > window.album_presentation.front.geometry().bottom()
        window.grab().save('build/previews/compact-tracks.png')
        window.back_button.click()
        assert window.viewed_album is None and window.workspace.page == 'library'
        window.back_button.click()
        animation = window.workspace.page_animation
        animation.pause()
        animation.setCurrentTime(animation.duration() // 2)
        mixture = window.workspace.page_mix
        assert 0 < mixture < 1
        window.show_compact_library()
        assert window.workspace.page_mix == mixture
        settle(window)
        window.show_compact_browser()
        settle(window)
        assert window.workspace.page == 'browser'
        window.open_now_playing_album()
        settle(window)
        assert window.workspace.page == 'library'
        window.is_android = True
        window.update_compact_navigation()
        assert not window.back_button.isVisible() and window.back_action.isEnabled()
        QTest.keyClick(window.album_table, Qt.Key_Back)
        settle(window)
        assert window.viewed_album is None and window.workspace.page == 'library'
        QTest.keyClick(window.grid, Qt.Key_Back)
        settle(window)
        assert window.workspace.page == 'browser'
        assert not window.back_action.isEnabled()
        window.update_now_playing_cover()
        settle(window)
        assert window.now_playing.isHidden()
        window.update_now_playing_cover(album)
        settle(window)
        assert window.now_playing.isVisible() and window.now_playing.height() > 0
        window.is_android = False
        window.resize(320, 640)
        settle(window)
        assert window.width() == 320 and window.compact_mode
        for widget in (window.play, window.previous, window.next, window.seek):
            assert window.transport.rect().contains(widget.geometry())
        window.browser_splitter.moveSplitter(window.browser_splitter.height(), 1)
        app.processEvents()
        window.resize(1200, 800)
        settle(window)
        assert not window.compact_mode
        assert all(pane.isVisible() for pane in window.workspace.panes)
        assert window.volume.isVisible() and not window.back_button.isVisible()
        assert not window.now_playing.resizable
        assert window.now_playing.height() > 0
        handle = window.workspace.handle
        before = window.workspace.sidebar_width
        center = handle.rect().center()
        QTest.mousePress(handle, Qt.LeftButton, pos=center)
        QTest.mouseMove(handle, center + QPoint(40, 0))
        QTest.mouseRelease(handle, Qt.LeftButton, pos=center)
        app.processEvents()
        assert window.workspace.sidebar_width > before
        assert window.queue_index == 0 and window.queue[0][1] is album
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()
print('PASS: 2:3 breakpoint, animated panes, resizable browser, navigation, Android Back, narrow transport and playback preservation')
