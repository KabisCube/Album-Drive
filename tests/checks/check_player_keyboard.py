import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout
from library import Album, Track
from main import PlayerWindow


app = QApplication([])
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
        shortcuts = {action.shortcut().toString() for action in window.actions() if not action.shortcut().isEmpty()}
        assert shortcuts == {'Space', 'Esc', 'Back'}, shortcuts
        with patch.object(window, 'previous_track') as previous, patch.object(window, 'next_track') as next_track, \
                patch.object(window, 'choose_folder') as folder, patch.object(window, 'edit_theme_settings') as settings_dialog:
            for key, modifiers in ((Qt.Key_Left, Qt.AltModifier), (Qt.Key_Right, Qt.AltModifier),
                                   (Qt.Key_O, Qt.ControlModifier), (Qt.Key_Comma, Qt.ControlModifier)):
                QTest.keyClick(window, key, modifiers)
            assert not any(callback.called for callback in (previous, next_track, folder, settings_dialog))
        window.volume.setFocus()
        value = window.volume.value()
        QTest.keyClick(window.volume, Qt.Key_Up)
        assert window.volume.value() == value
        focus = app.focusWidget()
        QTest.keyClick(window.volume, Qt.Key_Tab)
        assert app.focusWidget() is focus
        play = QSignalSpy(window.play_action.triggered)
        clicks = QSignalSpy(window.next.clicked)
        QTest.keyClick(window.next, Qt.Key_Space)
        assert play.count() == 1 and clicks.count() == 0
        album = Album(root, 'Test album', 'Test artist', [Track(root / f'{index}.wav', f'Track {index}') for index in range(3)])
        window.show_album(album, play_sound=False)
        window.album_table.selectRow(0)
        QTest.keyClick(window.album_table, Qt.Key_Down)
        assert window.album_table.currentRow() == 0
        QTest.keyClick(window.album_table, Qt.Key_Escape)
        assert window.viewed_album is None and window.library_pages.currentIndex() == 0
        assert window.isVisible() and not window.escape_action.isEnabled()
        window.resize(500, 1000)
        app.processEvents()
        window.workspace.mode_animation.setCurrentTime(350)
        window.show_album(album, play_sound=False)
        window.workspace.page_animation.setCurrentTime(350)
        QTest.keyClick(window.album_table, Qt.Key_Escape)
        assert window.viewed_album is None and window.workspace.page == 'library'
        QTest.keyClick(window.grid, Qt.Key_Escape)
        assert window.workspace.page == 'browser' and not window.escape_action.isEnabled()
        QTest.keyClick(window.tree, Qt.Key_Escape)
        assert window.isVisible()
        dialog = QDialog(window)
        editor = QLineEdit()
        QVBoxLayout(dialog).addWidget(editor)
        dialog.show()
        editor.setFocus()
        app.processEvents()
        QTest.keyClicks(editor, 'a b')
        assert editor.text() == 'a b'
        QTest.keyClick(editor, Qt.Key_Left)
        assert editor.cursorPosition() == 2
        QTest.keyClick(editor, Qt.Key_Escape)
        assert not dialog.isVisible() and window.workspace.page == 'browser'
    finally:
        window.close()
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()
print('PASS: only playback/back shortcuts remain, keyboard navigation is disabled, Escape steps back, and dialog editing still works')
