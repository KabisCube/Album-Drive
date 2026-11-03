"""Native one-file builds. Run PyInstaller on the target operating system."""

from pathlib import Path
import sys

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'src' / 'main.py')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=[(str(root / 'assets'), 'assets')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
              'PySide6.QtQuick', 'PySide6.QtPdf', 'tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='AlbumDrive', debug=False, strip=False, upx=False, console=False,
    icon=str(root / 'assets' / 'icons' / 'album-drive.ico') if sys.platform == 'win32' else None,
)
