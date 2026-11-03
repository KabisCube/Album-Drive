from color_rules import slider_rail, timeline_colors
"""Offscreen checks for session restoration and timeline theme colors."""

import os
import tempfile
import time
import wave
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider

from main import PlayerWindow


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition(), 'Session check timed out'


def make_track(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(bytes(8000 * 2 * 6))


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    album = root / 'Music' / 'Artist' / 'Album'
    make_track(album / '1.wav')
    make_track(album / '2.wav')
    make_track(root / 'Other library' / 'Other album' / '1.wav')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 1 and not window.scanners)
    window.open_album(window.grid.item(0))
    window.play_album(window.albums[0], 1)
    wait_until(lambda: window.player.duration() == 6000 and window.player.isSeekable())
    window.player.pause()
    window.player.setPosition(2350)
    window.close()
    wait_until(lambda: not window.scanners)
    settings.sync()
    assert int(settings.value('session/position')) == 2350

    # The playing album is restored even if another library was browsed last.
    settings.setValue('folder', str(root / 'Other library'))
    settings.setValue('browser_root', str(root / 'Other library'))
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    restored.show()
    wait_until(lambda: restored.queue_index == 1 and restored.resume_position is None
               and restored.player.duration() == 6000 and not restored.scanners)
    QTest.qWait(60)
    assert restored.player.playbackState() != QMediaPlayer.PlayingState
    assert restored.player.position() == 2350
    assert restored.album_table.currentRow() == 1
    assert restored.current_folder == root / 'Other library'
    assert restored.viewed_album.folder == album
    # A restored track's cover opens its album across library boundaries.
    restored.show_albums()
    QTest.mouseClick(restored.cover, Qt.LeftButton, pos=restored.cover.image_rect().center().toPoint())
    assert restored.viewed_album.folder == album and restored.current_folder == root / 'Other library'
    assert restored.album_table.currentRow() == 1 and restored.player.position() == 2350
    restored.play.click()
    wait_until(lambda: restored.player.playbackState() == QMediaPlayer.PlayingState)
    assert restored.player.position() >= 2350
    restored.player.pause()

    # Elapsed fill follows the knob, which matches the buttons.
    settings.setValue('theme_highlight_color', '#27ad78')
    settings.setValue('theme_button_fill', '#f3cc99')
    settings.setValue('theme_timeline_color', '#a58bd6')
    restored.set_theme('chunky')
    rail, fill, filled_text, unfilled_text = timeline_colors(
        app.property('themeBackground'), app.property('themeAccent'))
    restored.seek.setValue(1500)
    image = restored.seek.grab().toImage()
    middle = image.height() // 2
    assert image.pixelColor(40, middle).name() == fill.name()
    assert image.pixelColor(image.width() - 40, middle).name() == slider_rail(app.property('themeBackground')).name()
    option = QStyleOptionSlider()
    restored.seek.initStyleOption(option)
    handle = restored.seek.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, restored.seek)
    assert image.pixelColor(handle.center()).name() == '#27ad78'

    # There is no timestamp pill; padding is exactly the underlying groove color.
    def timestamp_padding_color():
        image = restored.seek.grab().toImage()
        bounds = restored.seek.timestamp_path().boundingRect()
        return image.pixelColor(round(bounds.left() - 4), round(bounds.center().y())).name()

    background_color = slider_rail(app.property('themeBackground')).name()
    assert timestamp_padding_color() == background_color
    bounds = restored.seek.timestamp_path().boundingRect().toAlignedRect()
    assert any(image.pixelColor(x, y).name() == unfilled_text.name()
               for x in range(bounds.left(), bounds.right()) for y in range(bounds.top(), bounds.bottom()))
    restored.seek.setValue(4500)
    assert timestamp_padding_color() == fill.name()
    image = restored.seek.grab().toImage()
    assert any(image.pixelColor(x, y).name() == filled_text.name()
               for x in range(bounds.left(), bounds.right()) for y in range(bounds.top(), bounds.bottom()))

    # Background clicks seek the actual media immediately, even before release.
    target = QPoint(round(restored.seek.width() * .75), middle)
    QTest.mousePress(restored.seek, Qt.LeftButton, pos=target)
    assert 4200 < restored.seek.value() < 4800
    assert restored.player.position() == restored.seek.value()
    QTest.mouseRelease(restored.seek, Qt.LeftButton, pos=target)
    assert restored.player.position() == restored.seek.value()
    # Dragging and both endpoints still work.
    QTest.mousePress(restored.seek, Qt.LeftButton, pos=target)
    QTest.mouseMove(restored.seek, QPoint(0, middle))
    QTest.mouseRelease(restored.seek, Qt.LeftButton, pos=QPoint(0, middle))
    assert restored.seek.value() == restored.player.position() == 0
    image = restored.seek.grab().toImage()
    assert image.pixelColor(80, middle).name() == slider_rail(app.property('themeBackground')).name()
    QTest.mouseClick(restored.seek, Qt.LeftButton, pos=QPoint(restored.seek.width() - 1, middle))
    assert restored.seek.value() == restored.player.position() == 6000
    restored.player.setPosition(1000)
    restored.player.play()
    wait_until(lambda: restored.player.playbackState() == QMediaPlayer.PlayingState)
    QTest.mouseClick(restored.seek, Qt.LeftButton, pos=target)
    assert 4200 < restored.player.position() < 4800
    assert restored.player.playbackState() == QMediaPlayer.PlayingState
    restored.player.pause()
    restored.close()
    wait_until(lambda: not restored.scanners)

    settings.setValue('session/track', str(album / 'missing.wav'))
    missing = PlayerWindow(settings)
    missing.show()
    wait_until(lambda: len(missing.albums) == 1 and not missing.scanners)
    assert not missing.queue and not missing.play.isEnabled()
    missing.close()

print('PASS: session restore, Play resumes, independent library, missing files, timeline fill/knob colors and click/drag seeking while paused or playing')
