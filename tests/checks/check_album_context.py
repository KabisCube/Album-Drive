import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main
from color_rules import disabled_text_color
from main import FILE_MANAGER_LABEL, PlayerWindow
from test_library import make_wave

app = QApplication([])

with TemporaryDirectory(ignore_cleanup_errors=True) as directory:
    root = Path(directory)
    make_wave(root / 'Music' / 'Long album name' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    try:
        window.resize(1400, 900)
        window.show()
        deadline = time.monotonic() + 10
        while (not window.albums or window.scanners) and time.monotonic() < deadline:
            QTest.qWait(20)
            time.sleep(.005)
        album = window.albums[0]
        track = album.tracks[0]

        window.show_metadata_menu(album, track, window.mapToGlobal(window.rect().center()))
        QTest.qWait(40)
        assert [action.text() for action in window.metadata_menu.actions()] == ['View metadata', FILE_MANAGER_LABEL]
        window.metadata_menu.close()
        with patch.object(main.subprocess, 'Popen') as popen, patch.object(main.sys, 'platform', 'win32'):
            window.metadata_folder_action.trigger()
            assert popen.call_args.args[0] == f'explorer.exe /select,"{track.path}"', popen.call_args
            window.metadata_target = album, None
            window.metadata_folder_action.trigger()
            assert popen.call_args.args[0] == ['explorer.exe', str(album.folder)], popen.call_args

        window.show_album(album, play_sound=False)
        window.album_presentation.animation.setCurrentTime(window.album_presentation.animation.duration())
        QTest.qWait(100)
        title = window.album_presentation.album_title
        assert title.isVisible() and title.text() == album.title
        assert title.alignment() & main.Qt.AlignHCenter
        assert title.font().pixelSize() == window.album_table.font().pixelSize() + 2
        assert title.geometry().bottom() <= window.album_table.geometry().top()

        assert not album.artwork
        saved = window.saved_theme_colors()
        assert window.album_presentation.paper_background.name() == saved['themeBackground'], 'no art uses the default theme'
        assert window.album_table.property('paperForegroundColor') == saved['textColor']
        with patch.object(window, 'theme_from_now_playing'), patch.object(
                window, 'album_paper_colors', return_value={'paperBackgroundColor': '#123456', 'textColor': '#fefefe'}):
            settings.setValue('artwork_theme_mode', 'dark')
            window.apply_settings()
            fade = window.album_presentation.paper_fade
            if fade.state() == fade.State.Running:
                assert window.album_presentation.paper_background.name() != '#123456', 'Brightness fades the open track list'
                fade.setCurrentTime(fade.duration())
            assert window.album_presentation.paper_background.name() == '#123456', 'Brightness refreshes an open track list'
            settings.setValue('artwork_theme_mode', 'any')
            window.apply_settings()

        calls = []
        with patch.object(main, 'artwork_theme_colors', lambda artwork, mode: calls.append(mode) or {'textColor': '#111111'}):
            first = window.cached_theme_colors(b'art', 'any')
            first['textColor'] = 'changed'
            assert window.cached_theme_colors(b'art', 'any') == {'textColor': '#111111'}
            assert calls == ['any'], 'album colors are worked out once and callers cannot alter the saved copy'
            window.cached_theme_colors(b'art', 'dark')
            assert calls == ['any', 'dark']
            preparer = main.ThemePreparer([(b'next', 'any')], window)
            preparer.ready.connect(window.store_theme_colors)
            preparer.start()
            deadline = time.monotonic() + 5
            while (b'next', 'any') not in window.theme_colors and time.monotonic() < deadline:
                QTest.qWait(10)
            preparer.wait()
            assert (b'next', 'any') in window.theme_colors, 'colors are prepared off the main thread'

        from metadata_editor import MetadataEditor
        from theme_transition import strip_theme_colors
        assert 'placeholder-text-color' in app.styleSheet()
        assert 'placeholder-text-color' not in strip_theme_colors(app.styleSheet())
        editor = MetadataEditor(album, None, window)
        editor.show()
        deadline = time.monotonic() + 8
        while editor.job is not None and time.monotonic() < deadline:
            QTest.qWait(20)
            time.sleep(.005)
        field = editor.fields['title']
        field.clear()
        field.setPlaceholderText('Mixed values')
        QTest.qWait(60)
        image = field.grab().toImage()
        text_color = QColor(disabled_text_color(app.property('textColor'))).name()
        colors = {image.pixelColor(x, y).name() for x in range(0, image.width(), 2) for y in range(0, image.height(), 2)}
        assert text_color in colors, 'placeholder text is dimmed like disabled Settings text'
        assert image.pixelColor(0, image.height() // 2).name() == image.pixelColor(30, 4).name(), 'text fields have no outline'
        editor.reject()

        real_player = window.player
        message = 'Invalid data found when processing input'
        source = QUrl.fromLocalFile(str(track.path))
        window.player = SimpleNamespace(playbackState=lambda: QMediaPlayer.PlayingState, position=lambda: 5000,
                                        source=lambda: source)
        window.statusBar().clearMessage()
        window.playback_error(QMediaPlayer.FormatError, message)
        assert not window.statusBar().currentMessage(), 'a skipped damaged frame must stay quiet'
        window.report_playback_stall(source, 4000, message)
        assert not window.statusBar().currentMessage(), 'playback that moved on is not a stall'
        window.report_playback_stall(source, 5000, message)
        assert message in window.statusBar().currentMessage(), 'a real stall must be reported'
        window.statusBar().clearMessage()
        window.player = SimpleNamespace(playbackState=lambda: QMediaPlayer.StoppedState, position=lambda: 0, source=lambda: source)
        window.playback_error(QMediaPlayer.FormatError, message)
        assert message in window.statusBar().currentMessage(), 'a file that cannot start must be reported'
        window.player = real_player
        window.workspace.sidebar_width = 333
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()

    reopened = PlayerWindow(settings)
    assert reopened.workspace.sidebar_width == 333, 'the file browser keeps its width after a restart'
    reopened.close()
    for scanner in list(reopened.scanners):
        scanner.requestInterruption()
        scanner.wait()
    app.processEvents()

print('PASS: track and album menus open the file manager, the booklet shows the album name, and only real stalls report damaged audio')
