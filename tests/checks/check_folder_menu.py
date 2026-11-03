import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PlayerWindow
from themes import button_paint_rect, control_face


app = QApplication([])
app.setStyle('Fusion')
with TemporaryDirectory() as directory:
    root = Path(directory)
    music = root / 'Music'
    first = music / 'First folder'
    second = music / 'Second folder'
    first.mkdir(parents=True)
    second.mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(music))
    window = PlayerWindow(settings)
    window.show()
    for _ in range(100):
        QTest.qWait(20)
        index = window.files.index(str(second))
        if index.isValid() and not window.scanners and window.tree.visualRect(index).isValid():
            break
    assert index.isValid()
    generation = window.generation
    selected = window.current_folder
    position = window.tree.visualRect(index).center()
    QTest.mouseClick(window.tree.viewport(), Qt.RightButton, pos=position)
    app.sendEvent(window.tree.viewport(), QContextMenuEvent(
        QContextMenuEvent.Mouse, position, window.tree.viewport().mapToGlobal(position)))
    app.processEvents()
    menu = window.folder_menu
    assert menu.isVisible()
    assert window.folder_menu_path == second
    assert window.current_folder == selected and window.generation == generation
    action = window.open_folder_action
    assert action.text() == ('Open in Windows Explorer' if sys.platform == 'win32' else 'Open in file manager')
    image = menu.grab().toImage()
    face = control_face(button_paint_rect(menu), widget=menu)
    assert image.pixelColor(round(face.left() + 3), round(face.center().y())).name() == QColor(app.property('themeBackground')).darker(110).name()
    assert image.pixelColor(0, 0).alpha() == 0
    menu.grab().save('build/debug/folder-context-menu.png')
    with patch('main.subprocess.Popen') as launch, patch('main.QDesktopServices.openUrl', return_value=True) as open_url:
        QTest.keyClick(menu, Qt.Key_Down)
        QTest.keyClick(menu, Qt.Key_Return)
        if sys.platform == 'win32':
            launch.assert_called_once_with(['explorer.exe', str(second)])
        else:
            assert open_url.call_args.args[0].toLocalFile() == str(second)
    assert not menu.isVisible()
    assert window.current_folder == selected and window.generation == generation
    window.show_folder_menu(window.tree.viewport().rect().bottomRight())
    assert not menu.isVisible()
    if sys.platform == 'win32':
        with patch('main.subprocess.Popen', side_effect=OSError('Explorer unavailable')):
            window.open_folder_in_explorer()
        assert 'Explorer unavailable' in window.statusBar().currentMessage()
        assert window.statusBar().message_timer.interval() == 15000
    window.close()
    while window.scanners:
        QTest.qWait(10)
print('PASS: styled folder context menu, correct Explorer target, keyboard activation, unchanged selection, empty-space exclusion and fading errors')
