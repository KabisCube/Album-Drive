"""Check source and packaged startup using temporary music and preferences."""

import argparse
import json
from pathlib import Path
import tempfile
import time
import wave

from PIL import Image
from app_paths import ASSETS_DIR

from PySide6.QtCore import QSettings, QTimer
from settings_store import create_app_settings, write_theme_files
from themes import COLOR_SETTINGS


def run_smoke(app, window_type):
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--smoke-report', type=Path, required=True)
    arguments = parser.parse_args()
    report = {'ok': False, 'frozen': bool(getattr(__import__('sys'), 'frozen', False))}
    with tempfile.TemporaryDirectory(prefix='album-drive-smoke-') as directory:
        root = Path(directory)
        album = root / 'Music' / 'Test album'
        album.mkdir(parents=True)
        with wave.open(str(album / '1.wav'), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22050)
            audio.writeframes(b'\0\0' * 22050)
        Image.new('RGB', (64, 64), '#162b47').save(album / 'cover.png')
        settings = create_app_settings(root / 'Portable app', QSettings(str(root / 'legacy.ini'), QSettings.IniFormat))
        settings.setValue('folder', str(root / 'Music'))
        settings.setValue('browser_root', str(root / 'Music'))
        window = window_type(settings)
        window.show()
        started = time.monotonic()
        loaded = False
        timer = QTimer(window)

        def finish(error=None):
            timer.stop()
            if error:
                report['error'] = str(error)
            else:
                report.update(ok=True, icon=not app.windowIcon().isNull(),
                              font=bool(app.property('playerFontLoaded')),
                              albums=len(window.albums), duration_ms=window.player.duration())
            arguments.smoke_report.parent.mkdir(parents=True, exist_ok=True)
            arguments.smoke_report.write_text(json.dumps(report, indent=2), encoding='utf-8')
            window.close()
            QTimer.singleShot(200, app.quit)

        def poll():
            nonlocal loaded
            try:
                if time.monotonic() - started > 20:
                    raise RuntimeError(f'Packaged scan/audio load timed out: {window.player.errorString()}')
                if not loaded and len(window.albums) == 1 and not window.scanners:
                    if app.windowIcon().isNull() or not app.property('playerFontLoaded'):
                        raise RuntimeError('Bundled icon or fonts are missing')
                    sounds = ASSETS_DIR / 'sounds'
                    report['button_sounds'] = all((sounds / f'button-{depth:02}.wav').is_file() for depth in range(1, 13))
                    if not report['button_sounds']:
                        raise RuntimeError('Bundled button sounds are missing')
                    report['case_sounds'] = all((sounds / f'case-{action}.wav').is_file() for action in ('open', 'close'))
                    if not report['case_sounds']:
                        raise RuntimeError('Bundled CD-case sounds are missing')
                    from first_run import FirstRunDialog
                    guide = FirstRunDialog(settings, window)
                    guide.advance()
                    guide.advance()
                    guide.advance()
                    report['welcome_guide'] = (guide.pages.count() == 4 and len(guide.choices) == 4
                                               and not guide.save_preview.image.isNull())
                    guide.reject()
                    guide.deleteLater()
                    if not report['welcome_guide']:
                        raise RuntimeError('Welcome guide previews are missing')
                    entry = window.albums[0]
                    window.show_album(entry)
                    if window.album_artwork.pixmap.isNull():
                        raise RuntimeError('Album artwork could not be rendered')
                    window.queue = [(track, entry) for track in entry.tracks]
                    window.play_index(0, autoplay=False)
                    if window.theme_fade is not None:
                        window.theme_fade.setCurrentTime(4000)
                    write_theme_files(settings, [dict(id='smoke-theme', name='Test album',
                                      colors={key: str(app.property(prop) or default) for _, _, key, prop, default in COLOR_SETTINGS})])
                    folder = root / 'Portable app' / 'themes'
                    report['portable_settings'] = (folder / 'settings.ini').is_file()
                    report['theme_ini'] = len(list(folder.glob('theme-*.ini'))) == 1
                    loaded = True
                if loaded and window.player.duration() > 0 and window.player.isSeekable():
                    window.player.setPosition(250)
                    finish()
            except Exception as error:
                finish(error)

        timer.timeout.connect(poll)
        timer.start(50)
        app.exec()
        # A timed-out scanner must finish before destroying its QThread.
        for scanner in list(window.scanners):
            scanner.requestInterruption()
            scanner.wait()
        app.processEvents()
    return 0 if report['ok'] else 1
