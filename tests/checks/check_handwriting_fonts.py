import runpy
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import font_support
from main import PlayerWindow, load_app_font
from PySide6.QtCore import QSettings


root = Path(__file__).resolve().parents[2]
app = QApplication([])
with tempfile.TemporaryDirectory() as directory:
    portable = Path(directory)
    with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(portable / 'AlbumDrive.exe')):
        paths = runpy.run_path(str(root / 'src' / 'app_paths.py'))
    assert paths['HANDWRITING_FONTS_DIR'] == portable / 'fonts' / 'handwriting'
    folder = paths['HANDWRITING_FONTS_DIR']
    folder.mkdir(parents=True)
    with patch.object(font_support, 'HANDWRITING_FONTS_DIR', folder):
        load_app_font()
        assert app.property('handwritingFonts') == []
        assert not any(font['id'].startswith('handwriting/') for font in app.property('availableFonts'))
        assert app.property('handwritingFamily') == app.property('trackListFamily')
        nested = folder / 'custom'
        nested.mkdir()
        first = nested / 'MyFont.TTF'
        shutil.copy2(root / 'assets' / 'fonts' / 'handwriting' / 'AlbumMarker02-Regular.ttf', first)
        (folder / 'invalid.ttf').write_text('invalid font', encoding='utf-8')
        app.setProperty('playerFontLoaded', False)
        load_app_font()
        fonts = app.property('handwritingFonts')
        assert len(fonts) == 1
        assert fonts[0]['id'] == 'custom/MyFont.TTF'
        assert fonts[0]['family'] == 'Album Marker 02'
        assert [font['id'] for font in app.property('availableFonts') if font['id'].startswith('handwriting/')] == ['handwriting/custom/MyFont.TTF']
        settings = QSettings(str(portable / 'settings.ini'), QSettings.IniFormat)
        controller = type('Controller', (), {'settings': settings})()
        selected = PlayerWindow.artist_handwriting(controller, portable / 'artist')
        assert selected.family() == 'Album Marker 02'
        first.unlink()
        shutil.copy2(root / 'assets' / 'fonts' / 'handwriting' / 'AlbumMarker04-Regular.ttf', folder / 'Replacement.ttf')
        app.setProperty('playerFontLoaded', False)
        load_app_font()
        fonts = app.property('handwritingFonts')
        assert len(fonts) == 1 and fonts[0]['family'] == 'Album Marker 04'
        selected = PlayerWindow.artist_handwriting(controller, portable / 'artist')
        assert selected.family() == 'Album Marker 04'

print('PASS: portable font path, empty folder, added/removed fonts, invalid fonts, font picker, and saved artist reassignment')
