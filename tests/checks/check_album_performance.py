import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRectF, QSettings, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from case_finish import paint_case_finish, scratch_overlay
from library import Album
from main import PlayerWindow, cd_case_image


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    (root / 'Music').mkdir()
    settings.setValue('folder', str(root / 'Music'))
    settings.setValue('button_sound_volume', 0)
    window = PlayerWindow(settings)
    window.resize(1200, 800)
    window.show()
    QTest.qWait(50)
    deadline = time.monotonic() + 5
    while window.scanners and time.monotonic() < deadline:
        QTest.qWait(20)
    assert not window.scanners
    window.albums = [Album(root / f'Album {index:04}', f'Album {index}', 'Artist', []) for index in range(2000)]
    start = time.perf_counter()
    window.apply_album_sort()
    window.grid.doItemsLayout()
    layout_ms = (time.perf_counter() - start) * 1000
    window.case_prefetch_timer.stop()
    window.clear_case_cache()
    with patch('main.cd_case_image', wraps=cd_case_image) as render:
        renders = lambda: sum(1 for call in render.call_args_list if call.args[1] == 'Album 0')
        window.album_icon(0)
        deadline = time.monotonic() + 5
        while 0 not in window.case_source_cache and time.monotonic() < deadline:
            QTest.qWait(20)
        assert 0 in window.case_source_cache
        assert renders() == 1
        for percent in (60, 85, 125, 150, 50):
            window.album_size.setValue(percent)
            window.grid.finish_reflow()
            window.album_icon(0)
            assert 0 in window.case_icon_cache
            assert renders() == 1
            bar = window.grid.verticalScrollBar()
            bar.setValue(bar.maximum())
            last = window.grid.visualItemRect(window.grid.item(window.grid.count() - 1))
            gap = window.grid.viewport().height() - last.bottom() - 1
            assert 0 <= gap <= 5, (percent, gap)
    window.album_size.setSliderDown(True)
    with patch.object(window.grid, 'set_album_scale', wraps=window.grid.set_album_scale) as layout:
        for percent in range(51, 151):
            window.album_size.setValue(percent)
        assert layout.call_count == 0
        deadline = time.monotonic() + 2
        while not layout.call_count and time.monotonic() < deadline:
            QTest.qWait(20)
        assert layout.call_count == 1, layout.call_count
        window.album_size.setValue(149)
        window.album_size.setSliderDown(False)
        assert window.grid.iconSize().width() == round(328 * 149 / 100)
    assert all(size <= 48 * 1024 * 1024 for size in window.case_cache_bytes.values())
    scratch_overlay.cache_clear()
    window.grid.finish_reflow()
    window.grid.verticalScrollBar().setValue(0)
    target = QPixmap(800, 600)
    target.fill(Qt.transparent)
    painter = QPainter(target)
    rect = QRectF(0, 0, 328, 300)
    paint_case_finish(painter, rect, 0, 'Album 0')
    misses = scratch_overlay.cache_info().misses
    paint_case_finish(painter, rect, 0, 'Album 0')
    painter.end()
    assert misses > 0 and scratch_overlay.cache_info().misses == misses
    window.close()
    deadline = time.monotonic() + 5
    while window.scanners and time.monotonic() < deadline:
        QTest.qWait(20)
    assert not window.scanners
    QTest.qWait(100)
print(f'PASS: 2000 albums laid out in {layout_ms:.1f} ms, zoom reuses sources, drag coalesced, bounded caches and bottom scroll')
