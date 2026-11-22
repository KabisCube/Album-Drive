"""Opening an album starts its track list at the top, unless its playing track needs scrolling into view."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication([])

from main import PlayerWindow


def album(name, count):
	return SimpleNamespace(folder=Path('/albums') / name,
						tracks=[SimpleNamespace(number=index + 1, title=f'Track {index + 1}') for index in range(count)])


with TemporaryDirectory() as directory:
	root = Path(directory)
	(root / 'Music').mkdir()
	settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
	settings.setValue('folder', str(root / 'Music'))
	settings.setValue('welcome_complete', True)
	window = PlayerWindow(settings)
	window.resize(1000, 700)
	window.show()
	QTest.qWait(300)  # Let startup finish choosing its page first, or it switches back to the album grid.
	window.album_page.show()
	window.library_pages.setCurrentWidget(window.album_page)
	QTest.qWait(200)
	table = window.album_table
	bar = table.verticalScrollBar()

	window.populate_album_tracks(album('long', 40))
	QTest.qWait(50)
	fitting = table.viewport().height() // table.rowHeight(0)
	bar.setValue(bar.maximum())
	QTest.qWait(50)
	assert table.isVisible() and bar.value() > 0, 'the long album must be scrolled down to start from'

	# One track more than fits leaves a scroll range under a row; the old position used to clamp to its bottom.
	window.populate_album_tracks(album('one over', fitting + 1))
	QTest.qWait(400)
	assert bar.maximum() > 0, 'the album must overflow by one track for this check'
	assert bar.value() == 0, f'new album opened scrolled to {bar.value()} of {bar.maximum()}'

	# Its playing track is still brought into view.
	playing = album('playing', fitting + 1)
	window.queue = [(track, playing) for track in playing.tracks]
	window.queue_index = len(playing.tracks) - 1
	window.populate_album_tracks(playing)
	QTest.qWait(400)
	last = table.visualItemRect(table.item(window.queue_index, 1))
	assert table.viewport().rect().contains(last), 'the playing last track must be visible'
	window.queue, window.queue_index = [], -1
	window.close()
	while window.scanners:
		QTest.qWait(10)
print('PASS: a newly opened album starts at the top, and its playing track still scrolls into view')
