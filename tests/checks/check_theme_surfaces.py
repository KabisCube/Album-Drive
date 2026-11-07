"""Pixel checks for live track-list backdrop, shared knobs and logo panel."""
import os
import tempfile
import time
from pathlib import Path
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PIL import Image
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider
from main import PlayerWindow
from themes import THEME_FADE_MS
from test_library import make_wave

app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    make_wave(root / 'Music/Album/1.wav')
    Image.new('RGB', (64, 64), '#203040').save(root / 'Music/Album/cover.png')
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('browser_root', str(root / 'Music'))
    settings.setValue('artwork_theme_enabled', False)
    settings.setValue('theme_background_color', '#304050')
    settings.setValue('theme_button_fill', '#e3d2c1')
    window = PlayerWindow(settings)
    window.show()
    deadline = time.monotonic() + 8
    while (not window.albums or window.scanners) and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert window.albums
    folder_index = window.files.index(str(root / 'Music/Album'))
    deadline = time.monotonic() + 8
    while not window.tree.visualRect(folder_index).isValid() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    album = window.albums[0]
    album.tracks *= 80
    window.show_album(album, play_sound=False)
    window.album_presentation.animation.stop()
    window.album_presentation.finish()
    app.processEvents()
    bar = window.album_table.verticalScrollBar()
    assert bar.isVisible()

    def check_surfaces():
        app.processEvents()
        folder_rect = window.tree.visualRect(folder_index).intersected(window.tree.viewport().rect())
        assert folder_rect.isValid()
        browser = window.tree.viewport().grab().toImage()
        text = QColor(app.property('textColor'))
        assert any(browser.pixelColor(x, y) == text
                   for x in range(folder_rect.left(), folder_rect.right())
                   for y in range(folder_rect.top(), folder_rect.bottom())), 'Folder text disappeared during theme fade'
        background = QColor(app.property('themeBackground'))
        assert app.property('brandLineColor') == background.darker(110).name()
        assert browser.pixelColor(browser.width() - 3, browser.height() - 3).name() == background.darker(110).name()
        option = QStyleOptionSlider()
        bar.initStyleOption(option)
        handle = bar.style().subControlRect(QStyle.CC_ScrollBar, option, QStyle.SC_ScrollBarSlider, bar)
        knob = bar.grab().toImage().pixelColor(handle.center()).name()
        assert knob == app.property('themeAccent'), (knob, app.property('themeAccent'))
        backdrop = window.library_pages.grab().toImage()
        color = backdrop.pixelColor(backdrop.width() - 3, backdrop.height() - 3).name()
        assert color == background.name(), ('backdrop', color, background.name())

    check_surfaces()
    settings.setValue('theme_background_color', '#d0b090')
    settings.setValue('theme_button_fill', '#362a20')
    window.apply_settings()
    animation = window.theme_fade
    assert animation is not None
    animation.pause()
    for elapsed in (0, 1, THEME_FADE_MS // 4, THEME_FADE_MS // 2, THEME_FADE_MS - 1, THEME_FADE_MS):
        if window.theme_fade is not None:
            animation.setCurrentTime(elapsed)
        check_surfaces()
        if elapsed == 2000:
            choice = window.sort_albums
            choice.showPopup()
            app.processEvents()
            animation.setCurrentTime(2100)
            app.processEvents()
            point = choice.view().viewport().mapTo(choice.popup, QPoint(2, 10))
            assert choice.popup.grab().toImage().pixelColor(point).name() == app.property('buttonFill')
            choice.hidePopup()
    # An interrupted fade starts from the colors already on screen.
    settings.setValue('theme_background_color', '#203070')
    window.apply_settings()
    window.theme_fade.pause()
    window.theme_fade.setCurrentTime(THEME_FADE_MS // 2)
    check_surfaces()
    before = app.property('themeBackground')
    settings.setValue('theme_background_color', '#503020')
    window.apply_settings()
    assert app.property('themeBackground') == before
    window.theme_fade.setCurrentTime(THEME_FADE_MS)
    check_surfaces()
    window.close()
    for scanner in list(window.scanners):
        scanner.requestInterruption()
        scanner.wait()
    app.processEvents()
print('PASS: track-list backdrop and knob pixels, matching logo panel, continuous and interrupted theme fades')
