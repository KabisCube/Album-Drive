import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QHBoxLayout, QTableWidgetItem, QWidget
from main import PlayerWindow
from open_case import AlbumPresentation


app = QApplication([])
window = QWidget()
layout = QHBoxLayout(window)
sidebar = QWidget()
sidebar.setFixedWidth(300)
layout.addWidget(sidebar)
presentation = AlbumPresentation()
layout.addWidget(presentation)
presentation.table.setRowCount(100)
for row in range(100):
    presentation.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
    presentation.table.setItem(row, 1, QTableWidgetItem(f'Track {row + 1}'))
window.show()
for width, height in ((1200, 800), (900, 1100), (900, 900), (860, 1300), (1400, 900)):
    window.resize(width, height)
    app.processEvents()
    presentation.layout_animation.setCurrentTime(presentation.layout_animation.duration())
    frame = window.frameGeometry()
    portrait = frame.width() < frame.height() * 1.1
    for progress in (0, .25, .5, 1):
        presentation.advance(progress)
        app.processEvents()
        front = presentation.front.geometry()
        paper = presentation.booklet.geometry()
        if progress == 0:
            assert presentation.booklet.isHidden()
        if progress == 1:
            assert presentation.rect().contains(front)
            assert presentation.rect().contains(paper)
            assert not presentation.booklet.isHidden()
            if portrait:
                case_face, paper_face = presentation.visible_faces()
                assert paper_face.top() > case_face.bottom()
                assert abs(paper.center().x() - front.center().x()) <= 1
            else:
                assert paper.left() > front.center().x()
                assert paper.top() < front.bottom()
        if portrait:
            assert paper.width() >= front.width()
    presentation.table.selectRow(45)
    presentation.table.scrollToItem(presentation.table.item(45, 1))
    app.processEvents()
    assert presentation.table.currentRow() == 45
    assert presentation.table.rowCount() == 100
window.close()

with TemporaryDirectory() as directory:
    settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('welcome_complete', True)
    player = PlayerWindow(settings)
    try:
        player.show()
        app.processEvents()
        player.album_page.show()
        player.library_pages.setCurrentWidget(player.album_page)
        player.album_presentation.finish()
        app.processEvents()
        extra_width = player.frameGeometry().width() - player.width()
        extra_height = player.frameGeometry().height() - player.height()
        boundary = 1100 - extra_width
        for width in (boundary + 1, boundary, boundary - 1, boundary, boundary + 1):
            player.resize(width, 1000 - extra_height)
            app.processEvents()
            transition = player.album_presentation.layout_animation
            transition.setCurrentTime(transition.duration())
            front = player.album_presentation.front.geometry()
            paper = player.album_presentation.booklet.geometry()
            if width < boundary:
                case_face, paper_face = player.album_presentation.visible_faces()
                assert paper_face.top() > case_face.bottom(), (width, boundary)
            else:
                assert paper.left() > front.center().x(), (width, boundary)
        view = player.album_presentation
        player.resize(boundary - 1, 1000 - extra_height)
        app.processEvents()
        transition.pause()
        transition.setCurrentTime(0)
        assert view.portrait_mix == 0, (view.portrait_mix, transition.startValue(), transition.endValue())
        start = (view.front.geometry(), view.booklet.geometry())
        transition.setCurrentTime(transition.duration() // 2)
        assert 0 < view.portrait_mix < 1
        middle = (view.front.geometry(), view.booklet.geometry())
        assert all(first != second for first, second in zip(start, middle))
        mixture = view.portrait_mix
        player.resize(boundary + 1, 1000 - extra_height)
        app.processEvents()
        transition.pause()
        transition.setCurrentTime(0)
        assert view.portrait_mix == mixture
        assert view.portrait_target == 0
        transition.setCurrentTime(transition.duration())
        assert view.portrait_mix == 0
        player.resize(boundary - 1, 1000 - extra_height)
        app.processEvents()
        transition.setCurrentTime(transition.duration())
        assert view.portrait_mix == 1
        case_face, paper_face = view.visible_faces()
        assert paper_face.top() > case_face.bottom()
    finally:
        player.close()
        for scanner in list(player.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()
print('PASS: window aspect ratio switches track layouts, animation fits both orientations, and tracks stay accessible')
