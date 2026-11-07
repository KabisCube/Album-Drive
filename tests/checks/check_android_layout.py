import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

Path('build').mkdir(exist_ok=True)
SCREEN = Path('build/android-phone-screen.json')
SCREEN.write_text(json.dumps({'screens': [{'name': 'phone', 'x': 0, 'y': 0, 'width': 360, 'height': 740,
                                           'logicalDpi': 96, 'dpr': 1}]}))
os.environ['QT_QPA_PLATFORM'] = f'offscreen:configfile={SCREEN.as_posix()}'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QAbstractScrollArea, QApplication, QLabel

app = QApplication([])
QApplication.platformName = staticmethod(lambda: 'android')

from color_picker import ColorPickerDialog
from first_run import FirstRunDialog
from main import PlayerWindow
from metadata_editor import MetadataEditor, TagValueDialog
from music_folders import MusicFolderDialog
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

        window.edit_theme_settings()
        dialog = window.settings_dialog
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
        for step in range(4):
            guide.set_step(step)
            QTest.qWait(60)
            for label in guide.scroll.widget().findChildren(QLabel):
                if label.wordWrap() and label.isVisibleTo(guide) and label.text():
                    assert label.height() >= label.heightForWidth(label.width()), (step, label.text())
        guide.set_step(0)
        QTest.qWait(60)
        assert guide.scroll.widget().height() == guide.scroll.viewport().height()
        guide.set_step(3)
        assert 'beside Settings' in guide.instructions_label.text()
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
