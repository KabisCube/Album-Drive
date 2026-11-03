import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from mutagen.wave import WAVE
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from metadata_editor import TagValueDialog
from test_library import make_wave


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


def context_menu(view, position):
    QTest.mouseClick(view.viewport(), Qt.RightButton, pos=position)
    app.sendEvent(view.viewport(), QContextMenuEvent(
        QContextMenuEvent.Mouse, position, view.viewport().mapToGlobal(position)))
    app.processEvents()


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    folder = root / 'Music' / 'Album'
    make_wave(folder / '1.wav', 'First song', 1)
    make_wave(folder / '2.wav', 'Second song', 2)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 1 and not window.scanners)
    window.grid.doItemsLayout()
    context_menu(window.grid, window.grid.visualItemRect(window.grid.item(0)).center())
    assert window.viewed_album is None
    assert window.metadata_menu.isVisible()
    assert window.metadata_action.text() == 'View metadata'
    QTest.keyClick(window.metadata_menu, Qt.Key_Down)
    QTest.keyClick(window.metadata_menu, Qt.Key_Return)
    editor = window.metadata_dialog
    wait_until(lambda: editor.job is None)
    assert len(editor.documents) == 2
    assert 'all 2 tracks' in editor.scope_label.text()
    assert 'Mixed' in editor.fields['title'].placeholderText()
    assert 'Mixed' in editor.fields['tracknumber'].placeholderText()
    assert not editor.save_button.isEnabled()
    editor.fields['artist'].setText('Updated artist')
    editor.fields['album'].setText('Updated album')
    assert editor.dirty_fields == {'artist', 'album'}
    assert WAVE(folder / '1.wav').tags['TPE1'].text == ['Test Artist']
    def add_custom_tag():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, TagValueDialog)
        dialog.key.setText('TXXX:Custom')
        dialog.value.setPlainText(json.dumps(['Custom value']))
        dialog.accept()
    QTimer.singleShot(30, add_custom_tag)
    editor.edit_tag()
    QTest.qWait(30)
    editor.grab().save('build/debug/metadata-album-editor.png')
    editor.save_button.click()
    wait_until(lambda: window.metadata_dialog is None or editor.job is None)
    assert window.metadata_dialog is None, editor.status.text()
    assert window.albums[0].title == 'Updated album'
    assert [track.title for track in window.albums[0].tracks] == ['First song', 'Second song']
    assert [track.number for track in window.albums[0].tracks] == [1, 2]
    for path in (folder / '1.wav', folder / '2.wav'):
        tags = WAVE(path).tags
        assert tags['TPE1'].text == ['Updated artist']
        assert tags['TXXX:Custom'].text == ['Custom value']
    album = window.albums[0]
    window.show_album(album)
    window.album_presentation.animation.setCurrentTime(window.album_presentation.animation.duration())
    app.processEvents()
    window.queue = [(track, album) for track in album.tracks]
    window.play_index(0, autoplay=False, position=250)
    wait_until(lambda: window.player.duration() > 0)
    context_menu(window.album_table, window.album_table.visualItemRect(window.album_table.item(0, 1)).center())
    assert window.metadata_target[1] is album.tracks[0]
    window.metadata_menu.hide()
    window.open_metadata_editor()
    editor = window.metadata_dialog
    wait_until(lambda: editor.job is None)
    assert len(editor.documents) == 1
    assert 'all 2 tracks' not in editor.scope_label.text()
    editor.fields['title'].setText('Edited first song')
    editor.fields['tracknumber'].setText('3')
    editor.save_button.click()
    wait_until(lambda: window.metadata_dialog is None or editor.job is None)
    assert window.metadata_dialog is None, editor.status.text()
    assert WAVE(folder / '1.wav').tags['TIT2'].text == ['Edited first song']
    assert WAVE(folder / '2.wav').tags['TIT2'].text == ['Second song']
    assert window.album_table.item(1, 1).text() == 'Edited first song'
    assert window.queue_index == 1
    assert window.queue[window.queue_index][0].title == 'Edited first song'
    assert window.track_title.text() == 'Edited first song'
    assert not window.player.source().isEmpty()
    window.metadata_target = album, next(track for track in album.tracks if track.path.name == '1.wav')
    window.open_metadata_editor()
    editor = window.metadata_dialog
    wait_until(lambda: editor.job is None)
    editor.fields['title'].setText('Discard this')
    editor.cancel_button.click()
    assert window.metadata_dialog is None
    assert WAVE(folder / '1.wav').tags['TIT2'].text == ['Edited first song']
    window.open_metadata_editor()
    editor = window.metadata_dialog
    wait_until(lambda: editor.job is None)
    editor.native_changes['NOT_A_VALID_ID3_TAG'] = '"Invalid"'
    editor.update_save_state()
    editor.save_button.click()
    wait_until(lambda: editor.job is None)
    assert window.metadata_dialog is editor
    assert 'Unknown ID3 frame' in editor.status.text()
    assert not window.player.source().isEmpty()
    assert WAVE(folder / '1.wav').tags['TIT2'].text == ['Edited first song']
    editor.cancel_button.click()
    window.close()
    wait_until(lambda: not window.scanners)
    QTest.qWait(100)
print('PASS: styled album/track menus, explicit batch scope, mixed-value preservation, custom tags, Save/Cancel, queue refresh and playback-source restoration')
