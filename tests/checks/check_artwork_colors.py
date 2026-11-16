"""Cover-derived paper colors, text contrast and missing-art fallbacks."""

import os
import tempfile
import time
from io import BytesIO
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QRectF, QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider, QTableWidgetItem

from main import PlayerWindow
from open_case import color_contrast
from test_library import make_wave
from themes import GROOVE_SHADE, control_face


def image_bytes(image):
	output = BytesIO()
	image.save(output, format='PNG')
	return output.getvalue()


def wait_until(condition):
	deadline = time.monotonic() + 8
	while not condition() and time.monotonic() < deadline:
		QTest.qWait(20)
		time.sleep(.005)
	assert condition()


app = QApplication([])
app.setStyle('Fusion')
dark = image_bytes(Image.new('RGB', (64, 64), '#162b47'))
light = image_bytes(Image.new('RGB', (64, 64), '#e7c977'))

with tempfile.TemporaryDirectory() as directory:
	root = Path(directory)
	for index in range(3):
		make_wave(root / 'Music' / f'Album {index}' / '1.wav')
	settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
	settings.setValue('folder', str(root / 'Music'))
	window = PlayerWindow(settings)
	window.show()
	wait_until(lambda: len(window.albums) == 3 and not window.scanners)
	for album, artwork in zip(window.albums, (dark, light, b'')):
		album.artwork = artwork
		expected = window.album_paper_colors(artwork)['paperBackgroundColor']
		window.show_album(album)
		QTest.qWait(460)
		table = window.album_table
		table.setRowCount(60)
		for row in range(1, 60):
			table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
			table.setItem(row, 1, QTableWidgetItem(f'Track {row + 1}'))
		QTest.qWait(30)
		background = QColor(table.property('paperBackgroundColor'))
		foreground = QColor(table.property('paperForegroundColor'))
		assert background.name() == expected
		assert table.palette().color(QPalette.Base) == background
		assert table.palette().color(QPalette.Text) == foreground
		assert table.viewport().grab().toImage().pixelColor(3, table.viewport().height() - 3) == background
		assert color_contrast(background, foreground) >= 4, (background.name(), foreground.name())
		bar = table.verticalScrollBar()
		assert bar.isVisible()
		if artwork:
			accent = QColor(window.album_paper_colors(artwork)['themeAccent'])
			option = QStyleOptionSlider()
			bar.initStyleOption(option)
			handle = bar.style().subControlRect(QStyle.CC_ScrollBar, option, QStyle.SC_ScrollBarSlider, bar)
			bar_image = bar.grab().toImage()
			face = control_face(QRectF(handle), widget=bar)
			assert bar_image.pixelColor(face.center().toPoint()).name() == accent.name()
			assert bar_image.pixelColor(bar.width() // 2, bar.height() - 30).name() == accent.darker(GROOVE_SHADE).name()
		table.selectRow(0)
		image = table.viewport().grab().toImage()
		cell = table.visualRect(table.model().index(0, 0))
		assert image.pixelColor(cell.left() + 1, cell.top() + 1) == background
		assert any(image.pixelColor(x, y) == foreground
				for x in range(cell.left(), cell.right()) for y in range(cell.top(), cell.bottom()))
		window.set_theme('chunky')
		assert table.property('paperBackgroundColor') == expected
		if artwork == dark:
			assert foreground.lightness() > background.lightness()
		if artwork == light:
			assert foreground.lightness() < 100
	window.close()

print('PASS: dominant cover colors, transparency, contrasting text, paper/delegate/viewport colors and missing-art fallback')
