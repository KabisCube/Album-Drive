"""Offscreen integration check using generated WAV files; no user music required."""
import os
import tempfile
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase, QPainterPath
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QApplication

from main import PlayerWindow, STYLE, cd_case_pixmap, handwritten_title_path
from case_geometry import CASE_WIDTH, CASE_HEIGHT
from open_case import PLAYING_ROLE
from theme_settings import ThemeSettingsDialog
from themes import ChunkyCheckBox, ThemeSlider, corner_radius
from test_library import make_wave


def wait_until(condition, timeout=8):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(0.005)
    assert condition(), f'Timed out: folder={window.current_folder}, albums={len(window.albums)}, workers={len(window.scanners)}, state={window.count_label.text()}'


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(root / 'music'))
    settings.setValue('button_font_size', 15)
    settings.setValue('corner_roundness', 100)
    settings.setValue('track_list_vertical_spacing', 0)
    for number in range(12):
        make_wave(root / 'music' / f'Album {number + 1:02}' / '01.wav')
        make_wave(root / 'music' / f'Album {number + 1:02}' / '02.wav')
    app = QApplication([])
    # Windows' offscreen plugin does not enumerate system fonts.
    if os.name == 'nt':
        QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / 'segoeui.ttf'))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = PlayerWindow(settings=settings)
    sleeve_area = QRectF(33, 16, 130, 130)
    for info in app.property('handwritingFonts') or []:
        font = QFont(info['family'])
        font.setStyleName(info['style'])
        for title in ('Agjpqy Tall Strokes & Descenders',
                      '1994 - Example Album Volume II (2 discs)',
                      'Supercalifragilisticexpialidocious' * 3):
            ink = handwritten_title_path(title, font, sleeve_area)
            assert not ink.isEmpty()
            assert sleeve_area.adjusted(-0.01, -0.01, 0.01, 0.01).contains(ink.boundingRect())
        # Overlapping outlines must accumulate ink rather than cancel it out.
        ink = handwritten_title_path('OO', font, sleeve_area)
        point = next(QPointF(x, y) for x in range(34, 162, 2) for y in range(17, 145, 2)
                     if ink.contains(QPointF(x, y)))
        overlap = QPainterPath(ink)
        overlap.addPath(ink)
        assert overlap.contains(point)
    # Missing/unreadable artwork gets handwriting even with a tagged title.
    for artwork in (b'', b'corrupt image'):
        assert cd_case_pixmap(artwork, 'Tagged Album').toImage() == cd_case_pixmap(
            b'', 'Tagged Album').toImage()
    assert window.windowTitle() == 'Album Drive'
    assert not window.track_title.text() and not hasattr(window, 'track_artist')
    assert not hasattr(window, 'search') and not hasattr(window, 'folder_label')
    window.show()
    wait_until(lambda: len(window.albums) == 12 and not window.scanners)
    assert window.grid.count() == 12
    assert len(window.case_icon_cache) < window.grid.count()
    assert not hasattr(window, 'now_playing_splitter')
    assert abs(window.cover.height() - (window.cover.width() - 20) * CASE_HEIGHT / CASE_WIDTH) <= 1
    settings.setValue('i_like_cleaning', True)
    settings.setValue('hover_rotation', 360)
    window.set_theme('chunky')
    dialog = ThemeSettingsDialog(settings, window)
    assert dialog.numbers['hover_rotation'].maximum() == 45
    assert dialog.numbers['button_font_size'].value() == settings.value('button_font_scale', type=int)
    assert dialog.rounding_slider.maximum() == 100
    assert isinstance(dialog.rounding_slider, ThemeSlider)
    assert isinstance(dialog.cleaning, ChunkyCheckBox)
    assert not dialog.findChildren(QAbstractSpinBox)
    assert all(isinstance(number.slider, ThemeSlider) for number in dialog.numbers.values())
    assert corner_radius(12, 100, 40) == 20
    dialog.applied.connect(lambda: window.set_theme('chunky'))
    dialog.show()
    window.grid.set_hover(0)
    QTest.qWait(220)
    dialog.cleaning.setChecked(False)
    dialog.apply()
    assert not window.grid.cleaning_enabled
    dialog.accept()
    window.grid.set_hover(-1)
    wait_until(lambda: not window.grid.tilts and not window.grid.tilt_animations)
    window.grid.set_hover(1)
    QTest.qWait(220)
    assert 1 in window.grid.tilts
    window.grid.set_hover(-1)
    wait_until(lambda: not window.grid.tilts and not window.grid.tilt_animations)
    window.grid.refresh_hover()
    assert not window.grid.tilts and not window.grid.tilt_animations
    assert not window.tidy_button.isVisible()
    assert window.play.x() < window.previous.x() < window.seek.x() < window.next.x() < window.volume.x()
    assert Path(window.files.filePath(window.tree.rootIndex())) == (root / 'music').resolve()
    assert window.files.data(window.files.index(str(root / 'music' / 'Album 01')), Qt.DecorationRole) is None
    window.tree.setCurrentIndex(window.files.index(str(root / 'music' / 'Album 02')))
    wait_until(lambda: not window.scanners and len(window.albums) == 1)
    assert Path(window.files.filePath(window.tree.rootIndex())) == (root / 'music').resolve()
    assert Path(settings.value('browser_root')) == (root / 'music').resolve()
    window.select_folder(root / 'music' / 'Album 01')
    wait_until(lambda: not window.scanners and len(window.albums) == 1)
    assert Path(window.files.filePath(window.tree.rootIndex())) == (root / 'music' / 'Album 01').resolve()
    window.select_folder(root / 'music')
    wait_until(lambda: not window.scanners and len(window.albums) == 12)
    window.grid.setCurrentRow(0)
    QTest.mouseClick(window.grid.viewport(), Qt.LeftButton,
                     pos=window.grid.visualItemRect(window.grid.item(0)).center())
    QTest.qWait(460)
    assert window.library_pages.currentWidget() == window.album_page
    assert QApplication.activeModalWidget() is None
    assert window.album_presentation.booklet.layout().count() == 2  # Album title and tracks.
    assert window.album_table.rowCount() == 2
    assert window.album_table.columnCount() == 2
    assert window.album_table.horizontalHeader().isHidden()
    assert not window.album_presentation.booklet.mask().contains(window.album_presentation.booklet.rect().topLeft())
    assert window.album_artwork.width() >= 250
    assert window.album_artwork.isVisible() and window.album_table.isVisible()
    assert window.tree.isVisible() and window.play.isVisible()
    assert window.album_presentation.booklet.x() > window.album_artwork.x()
    assert not window.album_table.alternatingRowColors()
    wait_until(lambda: window.album_presentation.progress == 1.0)
    case_face, paper_face = window.album_presentation.visible_faces()
    assert abs(case_face.top() - paper_face.top()) <= 2 and abs(case_face.bottom() - paper_face.bottom()) <= 2, (case_face, paper_face)
    assert not hasattr(window, 'play_album_button')
    assert not window.album_artwork.pixmap.isNull()
    assert window.grid.isVisible() and window.library_opacity.opacity() == .2
    assert all(effect.opacity() == .2 for effect in window.album_header_opacities)
    assert window.settings_button.graphicsEffect() is None
    assert window.settings_button.isEnabled()
    assert not hasattr(window, 'back_to_albums')
    assert window.grid.suppressed_album == window.grid.item(0).data(Qt.UserRole)
    assert window.grid.count() == 12
    assert window.settings_button.font().pixelSize() == 15
    assert window.album_table.font().family() == app.property('uiFontFamily')
    assert window.album_table.font().weight() == QFont.Normal
    assert window.album_table.verticalHeader().defaultSectionSize() >= window.album_table.fontMetrics().height() + 10
    # Clicking the case must stay open; empty space above/below dismisses it.
    QTest.mouseClick(window.album_artwork, Qt.LeftButton, pos=window.album_artwork.rect().center())
    assert window.library_pages.currentWidget() == window.album_page
    for point in (QPoint(20, 2), QPoint(20, window.album_presentation.height() - 2)):
        QTest.mouseClick(window.album_presentation, Qt.LeftButton, pos=point)
        assert window.library_pages.currentIndex() == 0
        assert window.library_opacity.opacity() == 1
        assert all(effect.opacity() == 1 for effect in window.album_header_opacities)
        window.open_album(window.grid.item(0))
        QTest.qWait(460)
    window.grab().save(str(Path('build/previews/album-preview.png')))
    window.show_albums()
    assert window.library_pages.currentIndex() == 0
    assert window.grid.currentRow() == 0
    assert window.grid.suppressed_album is None
    errors = []
    window.player.errorOccurred.connect(lambda error, text: errors.append(text))
    window.open_album(window.grid.item(0))
    window.album_table.cellDoubleClicked.emit(0, 1)
    wait_until(lambda: window.player.duration() > 0)
    wait_until(lambda: bool(window.album_table.item(0, 0).data(PLAYING_ROLE)))
    window.player.pause()
    assert not window.album_table.item(0, 0).data(PLAYING_ROLE)
    assert window.queue_index == 0
    assert window.track_title.text() and window.windowTitle().startswith('Album Drive — ')
    logical_size = window.cover.pixmap().deviceIndependentSize()
    assert abs(logical_size.width() - CASE_WIDTH) < .01
    assert abs(logical_size.height() - CASE_HEIGHT) < .01
    target = window.cover.image_rect()
    assert window.cover.contentsRect().contains(target.toAlignedRect())
    assert abs(target.width() / target.height() - CASE_WIDTH / CASE_HEIGHT) < .001
    assert window.cover.pixmap().width() > window.cover.pixmap().height()
    assert window.cover.pixmap().toImage().pixelColor(0, 0).alpha() == 0
    title = window.track_title.text()
    height = window.track_title.height()
    window.track_title.setText('A very long title that needs to scroll slowly across the available space ' * 3)
    QTest.qWait(1550)
    assert window.track_title.timer.isActive() and window.track_title.offset > 0
    assert window.track_title.height() == height
    window.track_title.setText(title)
    assert not window.track_title.timer.isActive() and window.track_title.offset == 0
    source = window.player.source()
    window.show_albums()
    window.open_album(window.grid.item(1))
    assert window.player.source() == source
    # The sidebar opens the playing album, even while viewing another album.
    QTest.mouseClick(window.cover, Qt.LeftButton, pos=window.cover.image_rect().center().toPoint())
    assert window.viewed_album.folder == window.queue[window.queue_index][1].folder
    assert window.album_table.currentRow() == window.queue_index
    assert window.player.source() == source and window.player.playbackState() == QMediaPlayer.PausedState
    wait_until(lambda: window.album_presentation.progress == 1.0)
    window.resize(860, 600)
    QTest.qWait(50)
    assert window.album_artwork.isVisible() and window.album_table.isVisible()
    assert window.tree.isVisible() and window.play.isVisible()
    window.resize(1400, 900)
    window.open_album(window.grid.item(0))
    window.player.play()
    wait_until(lambda: window.queue_index == 1)
    window.player.pause()
    window.previous_track()
    window.player.pause()
    assert window.queue_index == 0
    window.album_table.cellDoubleClicked.emit(1, 1)
    assert window.queue_index == 1
    assert window.album_table.currentRow() == 1
    window.previous_track()
    window.player.pause()
    window.next_track()
    assert window.queue_index == 1
    window.player.pause()
    window.previous_track()
    assert window.queue_index == 0
    window.player.pause()
    assert not errors, errors
    window.show_albums()
    QTest.qWait(50)
    window.grab().save(str(Path('build/previews/preview.png')))
    window.open_album(window.grid.item(0))
    window.scan(root / 'music')
    assert window.library_pages.currentIndex() == 0
    window.scan(root / 'music' / 'Album 02')
    wait_until(lambda: not window.scanners)
    assert len(window.albums) == 1
    assert window.albums[0].folder.name == 'Album 02'
    window.scan(root / 'music')
    window.close()
    wait_until(lambda: not window.scanners)
    QTest.qWait(100)
    print('PASS: Album Drive branding, blank idle labels, simplified album view, navigation, artwork/metadata, persistent browser/controls, track activation, WAV playback, queue, stale scans and close during scan')
