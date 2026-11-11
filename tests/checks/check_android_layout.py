import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

Path('build').mkdir(exist_ok=True)
SCREEN = Path('build/android-phone-screen.json')
SCREEN.write_text(json.dumps({'screens': [{'name': 'phone', 'x': 0, 'y': 0, 'width': 360, 'height': 740,
                                           'logicalDpi': 96, 'dpr': 1}]}))
os.environ['QT_QPA_PLATFORM'] = f'offscreen:configfile={SCREEN.as_posix()}'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QAbstractScrollArea, QApplication, QLabel


def finish_settings_build(window):
    """Phones build Settings a few steps per event-loop turn; wait for it to finish."""
    deadline = time.monotonic() + 10
    while window.settings_build is not None and time.monotonic() < deadline:
        QTest.qWait(5)
    return window.prepared_settings

app = QApplication([])
QApplication.platformName = staticmethod(lambda: 'android')

from color_picker import ColorPickerDialog
from first_run import FirstRunDialog
from main import PlayerWindow
from metadata_editor import MetadataEditor, TagValueDialog
from music_folders import MusicFolderDialog
from theme_transition import strip_theme_colors
from test_library import make_wave


def assert_fits(dialog):
    QTest.qWait(80)
    assert dialog.size() == app.primaryScreen().availableGeometry().size(), (dialog, dialog.size())
    for button in dialog.findChildren(QAbstractButton):
        if button.isVisibleTo(dialog) and button.text():
            assert button.height() >= 30, (button.text(), button.height())


with TemporaryDirectory(ignore_cleanup_errors=True) as directory:
    root = Path(directory)
    make_wave(root / 'Music' / 'Album' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('welcome_complete', True)
    window = PlayerWindow(settings)
    try:
        window.setGeometry(app.primaryScreen().availableGeometry())
        window.show()
        deadline = time.monotonic() + 10
        while (not window.albums or window.scanners) and time.monotonic() < deadline:
            QTest.qWait(20)
            time.sleep(.005)
        assert window.albums
        window.show_compact_library()
        window.workspace.page_animation.setCurrentTime(window.workspace.page_animation.duration())
        QTest.qWait(150)
        assert not window.album_scale_control.isVisible() and not window.refresh_button.isVisible()
        header = window.album_header
        assert not header.scroll_left.isVisible() and not header.scroll_right.isVisible()
        for button in (window.sort_albums, window.save_theme_button, window.settings_button):
            assert button.isVisible() and header.rect().contains(button.mapTo(header, button.rect().bottomRight()))
        assert window.sort_albums.width() >= 96
        assert window.transport.isVisible() and window.transport.geometry().top() > window.grid.mapTo(window, window.grid.rect().topLeft()).y()
        assert window.browser_splitter.handleWidth() == 0
        assert window.grid.baked_cases is not None
        played = []
        window.play_album = lambda album, row: played.append(row)
        window.show_album(window.albums[0], play_sound=False)
        window.album_table.cellClicked.emit(0, 1)
        assert played == [0], 'one tap plays a track on Android'
        window.album_presentation.animation.setCurrentTime(window.album_presentation.animation.duration())
        QTest.qWait(120)
        assert not window.settings_button.isEnabled() and not window.save_theme_button.isEnabled()
        header_bottom = window.album_header.mapTo(window, window.album_header.rect().bottomLeft()).y()
        assert window.album_artwork.mapTo(window, window.album_artwork.rect().topLeft()).y() < header_bottom
        window.show_albums()
        QTest.qWait(40)
        assert window.settings_button.isEnabled()
        grid_top = window.grid.mapTo(window, window.grid.rect().topLeft()).y()
        assert grid_top >= header_bottom, 'albums stay below the header'

        window.prepare_settings()
        prepared = finish_settings_build(window)
        assert prepared is not None and not prepared.isVisible() and not prepared.color_preview_timer.isActive()
        settings.setValue('album_sort', 'oldest')
        assert window.take_prepared_settings() is None, 'a changed setting must not reuse a stale Settings window'
        settings.setValue('album_sort', 'newest')
        window.prepare_settings()
        prepared = finish_settings_build(window)
        settings.setValue('session/position', 1234)
        settings.setValue('volume', 50)
        window.edit_theme_settings()
        dialog = window.settings_dialog
        assert dialog is prepared and window.prepared_settings is None, 'playback changes keep the prepared window'
        assert dialog.original_settings['session/position'] in (1234, '1234')
        assert dialog.color_preview_timer.isActive()
        assert_fits(dialog)
        assert [button.text() for button in dialog.action_buttons] == ['Reset defaults', 'OK']
        assert dialog.action_buttons[0].y() == dialog.action_buttons[1].y()
        assert 'Cancel' not in [button.text() for button in dialog.findChildren(QAbstractButton)]
        for index in range(dialog.tabs.count()):
            dialog.tabs.setCurrentIndex(index)
            QTest.qWait(60)
            area = dialog.tabs.currentWidget()
            assert not area.verticalScrollBar().isVisible() and not area.horizontalScrollBar().isVisible()
            assert area.widget().width() >= area.viewport().width() - 1
        original = dialog.rounding_slider.value()
        dialog.rounding_slider.setValue(original + 10)
        QTest.qWait(120)
        QTest.keyClick(dialog, Qt.Key_Back)
        QTest.qWait(80)
        assert window.settings_dialog is None
        assert settings.value('corner_roundness', original, type=int) == original, 'Back cancels Settings'

        guide = FirstRunDialog(settings, window)
        guide.show()
        assert_fits(guide)
        for step in range(3):
            guide.set_step(step)
            QTest.qWait(60)
            for label in guide.scroll.widget().findChildren(QLabel):
                if label.wordWrap() and label.isVisibleTo(guide) and label.text():
                    assert label.height() >= label.heightForWidth(label.width()), (step, label.text())
        guide.set_step(0)
        QTest.qWait(60)
        assert guide.scroll.widget().height() == guide.scroll.viewport().height()
        guide.reject()

        picker = ColorPickerDialog('#3366aa', window)
        picker.show()
        assert_fits(picker)
        picker.reject()
        editor = MetadataEditor(window.albums[0], None, window)
        editor.show()
        deadline = time.monotonic() + 8
        while editor.job is not None and time.monotonic() < deadline:
            QTest.qWait(20)
            time.sleep(.005)
        for index in range(editor.tabs.count()):
            editor.tabs.setCurrentIndex(index)
            assert_fits(editor)
        tag = TagValueDialog('TXXX:Custom', None, editor)
        tag.show()
        assert_fits(tag)
        tag.reject()
        editor.reject()
        folders = MusicFolderDialog(window, 'Choose music library root', root / 'Music')
        folders.show()
        assert_fits(folders)
        folders.reject()

        assert not hasattr(app, '_album_drive_scrollbars'), 'Android must not inspect every event for scrollbars'
        assert window.live_theme and window.theme_renderer is not None
        style = app.styleSheet()
        assert strip_theme_colors(style) == style, 'Android keeps its stylesheet free of theme colors'
        reloads = []
        with patch.object(QApplication, 'setStyleSheet', lambda *args: reloads.append(args)):
            colors = dict(window.saved_theme_colors(), themeBackground='#335b70', themeAccent='#86948d')
            with patch.object(window, 'saved_theme_colors', lambda: dict(colors)):
                window.theme_from_now_playing()
                QTest.qWait(30)
                assert window.theme_fade is not None, 'a color change must fade'
                window.theme_fade.setCurrentTime(window.theme_fade.duration())
                QTest.qWait(30)
            assert window.theme_renderer is not None and app.property('themeBackground') == '#335b70'
        assert not reloads, 'a theme fade must not reload the whole stylesheet'
        renderer = window.theme_renderer
        window.set_theme(str(settings.value('theme', 'chunky')))
        assert window.theme_renderer is not None and window.theme_renderer is not renderer, 'full restyles return to live colors'
        window.show_compact_library()
        QTest.qWait(450)
        window.grid.viewport().repaint()
        cached = set(window.grid.baked_cases)
        assert cached
        window.freeze_case_theme((app.property('themeBackground'), 'frozen'))
        window.grid.viewport().repaint()
        frozen = set(window.grid.baked_cases) - cached
        original_background = app.property('themeBackground')
        app.setProperty('themeBackground', '#123456')
        window.grid.viewport().repaint()
        assert set(window.grid.baked_cases) - cached == frozen, 'a color step must not rebuild cached cases'
        app.setProperty('themeBackground', original_background)
        window.freeze_case_theme(None)
        window.workspace.set_page('browser', animate=False)
        window.update_now_playing_cover(window.albums[0])
        window.now_playing.animation.setCurrentTime(window.now_playing.animation.duration())
        QTest.qWait(120)
        height = window.now_playing.height()
        window.drag_now_playing(10)
        window.drag_now_playing(10)
        assert window.now_playing.height() == height and window.cover.resizing, 'swipes apply once per frame'
        QTest.qWait(40)
        assert window.now_playing.height() == height - 20
        window.settle_now_playing(0)
        assert not window.cover.resizing
        portrait = window.geometry()
        window.setGeometry(0, 0, 740, 360)
        QTest.qWait(500)
        assert not window.compact_mode and window.now_playing.resizable, 'landscape can resize Now Playing too'
        window.now_playing.animation.setCurrentTime(window.now_playing.animation.duration())
        QTest.qWait(60)
        minimum, maximum = window.now_playing_limits()
        window.set_now_playing_height(maximum)
        QTest.qWait(40)
        before = window.cover.height()
        assert before > 0
        window.drag_now_playing(window.height())
        window.settle_now_playing(0)
        QTest.qWait(60)
        assert window.now_playing.height() == minimum, (window.now_playing.height(), minimum)
        assert window.cover.height() < before, 'swiping down hides the album in landscape'
        window.settle_now_playing(-2000)
        window.split_animation.setCurrentTime(window.split_animation.duration())
        QTest.qWait(60)
        assert window.now_playing.height() == maximum, 'a flick up brings it back'
        window.setGeometry(portrait)
        QTest.qWait(500)
        window.now_playing.animation.setCurrentTime(window.now_playing.animation.duration())
        assert window.compact_mode
        QTest.qWait(60)
        assert not window.cover.baked_case.isNull()
        assert abs(window.cover.baked_width - window.cover.image_rect().width()) <= .5, 'a sharp case returns after a swipe'

        for area in window.findChildren(QAbstractScrollArea):
            if area.isVisible():
                assert area.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()

print('PASS: Android hides header extras, Cancel and scrollbars, and every window fills a phone screen without crushed controls')
